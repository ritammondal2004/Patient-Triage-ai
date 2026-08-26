
"""Triage orchestration: register a patient, open a visit, record vitals, score, persist.

This is the only place that talks to the risk engine. Routes stay thin, and the engine
stays framework-free. Derived model features are never stored — every score recomputes
them from the raw vitals row it is attached to. 
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.orm import Hospital, Patient, TriageAssessment, Visit, VitalsRecord
from app.models.schemas import PatientIn, VisitIntakeRequest, VitalsIn
from app.services import audit_service
from risk_engine.config import load_config
from risk_engine.predictor import score as engine_score

settings = get_settings()

_FALLBACK_LABELS = {1: "CRITICAL", 2: "URGENT", 3: "MODERATE", 4: "LOW RISK", 5: "NON-URGENT"}

VITALS_FIELDS = (
    "heart_rate", "resp_rate", "systolic_bp", "diastolic_bp",
    "temperature_c", "spo2", "pain_score",
)


class TriageEngineError(RuntimeError):
    """Raised when the risk engine cannot produce a decision. Never swallowed — a
    silent failure here would mean a patient with no score and no confidence flag."""


# ---------------------------------------------------------------- time helpers
# SQLite hands back naive datetimes; Postgres gives aware ones. Normalise both.

def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def minutes_since(value: datetime | None, now: datetime | None = None) -> float:
    start = as_utc(value)
    if start is None:
        return 0.0
    reference = as_utc(now) or datetime.now(timezone.utc)
    return max(0.0, (reference - start).total_seconds() / 60.0)


def priority_label(level: int) -> str:
    """Prefer the label the notebook saved; fall back to a local map."""
    try:
        labels = getattr(load_config(), "esi_labels", None) or {}
        found = labels.get(int(level)) or labels.get(str(level))
        if found:
            return str(found)
    except Exception:
        pass
    return _FALLBACK_LABELS.get(int(level), f"P{level}")


# ----- get-or-create

def get_or_create_hospital(db: Session, hospital_id: int | None = None) -> Hospital:
    """Resolve the target site, creating the demo hospital on first use."""
    if hospital_id is not None:
        hospital = db.get(Hospital, hospital_id)
        if hospital:
            return hospital

    hospital = db.execute(
        select(Hospital).where(Hospital.name == settings.default_hospital_name)
    ).scalar_one_or_none()
    if hospital:
        return hospital

    hospital = Hospital(
        name=settings.default_hospital_name,
        capacity_doctors=settings.default_doctors,
        capacity_beds=settings.default_beds,
        avg_daily_visits=settings.default_daily_visits,
    )
    db.add(hospital)
    db.flush()
    return hospital


def get_or_create_patient(db: Session, payload: PatientIn) -> Patient:
    """Repeat visitors keep their patient_code; history counts are refreshed."""
    code = (payload.patient_code or "").strip() or f"PT-{uuid.uuid4().hex[:8].upper()}"

    patient = db.execute(
        select(Patient).where(Patient.patient_code == code)
    ).scalar_one_or_none()

    if patient is None:
        patient = Patient(
            patient_code=code,
            age=payload.age,
            gender=payload.gender,
            has_prior_history=payload.has_prior_history,
            prior_conditions_count=payload.prior_conditions_count,
            prior_ed_visits=payload.prior_ed_visits,
        )
        db.add(patient)
        db.flush()
        audit_service.record_event(
            db, event_type="patient_registered", entity_type="patient",
            entity_id=patient.id, payload={"patient_code": code, "age": payload.age},
        )
        return patient

    # Existing patient: age and history may have moved on since the last visit.
    patient.age = payload.age 
    patient.gender = payload.gender
    patient.prior_conditions_count = max(patient.prior_conditions_count, payload.prior_conditions_count)
    patient.prior_ed_visits = max(patient.prior_ed_visits, payload.prior_ed_visits)
    patient.has_prior_history = bool(
        patient.has_prior_history or payload.has_prior_history
        or patient.prior_conditions_count or patient.prior_ed_visits
    ) 
    db.flush()
    return patient


def create_visit(db: Session, patient: Patient, hospital: Hospital, request: VisitIntakeRequest) -> Visit:
    arrived = datetime.now(timezone.utc)
    visit = Visit(
        patient_id=patient.id,
        hospital_id=hospital.id,
        chief_complaint=request.chief_complaint,
        symptom_text=request.symptom_text or "",
        arrival_mode=request.arrival_mode,
        is_ambiguous_case=request.is_ambiguous_case,
        status="waiting",
        arrived_at=arrived,
        reference_esi_level=request.reference_esi_level,
        retention_until=arrived + timedelta(days=settings.retention_days),
    )
    db.add(visit)
    db.flush()
    audit_service.record_event(
        db, event_type="visit_created", entity_type="visit", entity_id=visit.id,
        payload={
            "patient_code": patient.patient_code,
            "chief_complaint": visit.chief_complaint,
            "arrival_mode": visit.arrival_mode,
            "retention_until": visit.retention_until,
        },
    )
    return visit


def record_vitals(db: Session, visit: Visit, vitals: VitalsIn) -> VitalsRecord:
    """Always writes a row, even if every field is None — unrecorded vitals are a real
    intake state that must be visible to the engine, not hidden by skipping the insert."""
    record = VitalsRecord(visit_id=visit.id, source=vitals.source, recorded_at=datetime.now(timezone.utc))
    for field in VITALS_FIELDS:
        setattr(record, field, getattr(vitals, field, None))
    db.add(record)
    db.flush()

    recorded = vitals.recorded_fields()
    audit_service.record_event(
        db, event_type="vitals_recorded", entity_type="visit", entity_id=visit.id,
        actor=vitals.source,
        payload={
            "vitals_record_id": record.id,
            "fields_recorded": sorted(recorded.keys()),
            "fields_missing": sorted(set(VITALS_FIELDS) - set(recorded.keys())),
        },
    )
    return record


# ---------------------------------------------------------------- scoring

def vitals_as_dict(record: VitalsRecord | None) -> dict:
    if record is None:
        return {}
    return {field: getattr(record, field, None) for field in VITALS_FIELDS}


def build_engine_record(patient: Patient, visit: Visit, vitals: VitalsRecord | None) -> dict:
    """Raw observations only. Age adjustment and deviations are the engine's job."""
    record = {
        "patient_id": patient.patient_code,
        "age": patient.age,
        "gender": patient.gender,
        "chief_complaint": visit.chief_complaint,
        "symptom_text": visit.symptom_text or "",
        "arrival_mode": visit.arrival_mode,
        "prior_conditions_count": patient.prior_conditions_count,
        "prior_ed_visits": patient.prior_ed_visits,
        "has_prior_history": patient.has_prior_history,
    }
    record.update(vitals_as_dict(vitals))
    return record


def _decision_field(decision, name: str, default):
    value = getattr(decision, name, None)
    return default if value is None else value


def score_and_persist(
    db: Session,
    visit: Visit,
    vitals: VitalsRecord | None,
    trigger: str = "intake",
    safety_mode: str | None = None,
) -> TriageAssessment:
    patient = visit.patient or db.get(Patient, visit.patient_id)
    record = build_engine_record(patient, visit, vitals)
    mode = safety_mode or settings.safety_mode

    try:
        decision = engine_score(record, safety_mode=mode)  
    except Exception as exc:  # artifact missing, feature mismatch, unpickling error
        raise TriageEngineError(f"risk engine failed to score visit {visit.id}: {exc}") from exc

    level = int(_decision_field(decision, "final_priority", 2))
    assessment = TriageAssessment(
        visit_id=visit.id,
        vitals_record_id=vitals.id if vitals else None,
        trigger=trigger,
        final_priority=level,
        priority_label=str(_decision_field(decision, "priority_label", priority_label(level))),
        ml_only_priority=int(_decision_field(decision, "ml_only_priority", level)),
        risk_probability=float(_decision_field(decision, "risk_probability", 0.0)),
        confidence_label=str(_decision_field(decision, "confidence_label", "Low")),
        uncertainty_score=float(_decision_field(decision, "uncertainty_score", 1.0)),
        confidence_reasons=list(_decision_field(decision, "confidence_reasons", [])),
        safety_rules_triggered=list(_decision_field(decision, "safety_rules_triggered", [])),
        safety_rule_details=list(_decision_field(decision, "safety_rule_details", [])),
        rule_priority_floor=int(_decision_field(decision, "rule_priority_floor", 5)),
        escalated_by_rules=bool(_decision_field(decision, "escalated_by_rules", False)),
        escalated_by_uncertainty=bool(_decision_field(decision, "escalated_by_uncertainty", False)),
        risk_indicators=list(_decision_field(decision, "risk_indicators", [])),
        missing_fields=list(_decision_field(decision, "missing_fields", [])),
        unknown_categories=list(_decision_field(decision, "unknown_categories", [])),
        model_version=str(_decision_field(decision, "model_version", "unknown")),
        operating_threshold=float(_decision_field(decision, "operating_threshold", 0.0)),
        safety_mode=str(_decision_field(decision, "safety_mode", mode)),
    )
    db.add(assessment)
    db.flush()

    audit_service.record_event(
        db, event_type="triage_scored", entity_type="visit", entity_id=visit.id,
        actor="risk_engine",
        payload={
            "assessment_id": assessment.id,
            "trigger": trigger,
            "final_priority": assessment.final_priority,
            "ml_only_priority": assessment.ml_only_priority,
            "risk_probability": round(assessment.risk_probability, 4),
            "confidence_label": assessment.confidence_label,
            "safety_rules_triggered": assessment.safety_rules_triggered,
            "escalated_by_rules": assessment.escalated_by_rules,
            "escalated_by_uncertainty": assessment.escalated_by_uncertainty,
            "model_version": assessment.model_version,
            "operating_threshold": assessment.operating_threshold,
        },
    )
    return assessment


#  public flows

@dataclass
class IntakeResult:
    patient: Patient
    visit: Visit
    vitals: VitalsRecord
    assessment: TriageAssessment


def intake(db: Session, request: VisitIntakeRequest) -> IntakeResult:
    """Register, open a visit, record vitals and score in one transaction."""
    try:
        hospital = get_or_create_hospital(db, request.hospital_id)
        patient = get_or_create_patient(db, request.patient)
        visit = create_visit(db, patient, hospital, request)
        vitals = record_vitals(db, visit, request.vitals)
        assessment = score_and_persist(db, visit, vitals, "intake", request.safety_mode)
        db.commit()  
    except TriageEngineError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"intake failed: {exc}") from exc

    db.refresh(visit)
    return IntakeResult(patient=patient, visit=visit, vitals=vitals, assessment=assessment)


def rescore(db: Session, visit_id: int, trigger: str = "manual_rescore") -> TriageAssessment:
    visit = get_visit(db, visit_id)
    if visit is None:
        raise LookupError(f"visit {visit_id} not found")
    try:
        assessment = score_and_persist(db, visit, latest_vitals(db, visit_id), trigger)
        db.commit()
        return assessment
    except TriageEngineError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"rescore failed: {exc}") from exc


#  lookups

def get_visit(db: Session, visit_id: int) -> Visit | None:
    return db.execute(
        select(Visit)
        .where(Visit.id == visit_id)
        .options(selectinload(Visit.patient))
    ).scalar_one_or_none()


def latest_vitals(db: Session, visit_id: int) -> VitalsRecord | None:
    return db.execute(
        select(VitalsRecord)
        .where(VitalsRecord.visit_id == visit_id)
        .order_by(VitalsRecord.recorded_at.desc(), VitalsRecord.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def previous_vitals(db: Session, visit_id: int) -> VitalsRecord | None:
    """Second-newest row — the baseline a worsening check compares against."""
    rows = list(db.execute(
        select(VitalsRecord)
        .where(VitalsRecord.visit_id == visit_id)
        .order_by(VitalsRecord.recorded_at.desc(), VitalsRecord.id.desc())
        .limit(2)
    ).scalars())
    return rows[1] if len(rows) > 1 else None


def latest_assessment(db: Session, visit_id: int) -> TriageAssessment | None:
    return db.execute(
        select(TriageAssessment)
        .where(TriageAssessment.visit_id == visit_id)
        .order_by(TriageAssessment.created_at.desc(), TriageAssessment.id.desc())
        .options(selectinload(TriageAssessment.override))
        .limit(1)
    ).scalar_one_or_none()


def assessment_history(db: Session, visit_id: int) -> list[TriageAssessment]:
    return list(db.execute(
        select(TriageAssessment)
        .where(TriageAssessment.visit_id == visit_id)
        .order_by(TriageAssessment.created_at, TriageAssessment.id)
        .options(selectinload(TriageAssessment.override))
    ).scalars())

      
def effective_priority(assessment: TriageAssessment | None) -> int:
    """The clinician's override always wins — the model never has the last word."""
    if assessment is None:
        return 3
    override = getattr(assessment, "override", None)
    if override is not None:
        return int(override.override_priority)
    return int(assessment.final_priority)


def engine_info() -> dict:
    info = {
        "model_version": "unknown",
        "production_model": "xgboost",
        "operating_threshold": 0.0,
        "safety_mode": settings.safety_mode,
        "jurisdiction": settings.jurisdiction,
    }
    try:
        cfg = load_config()
        for key, attr in (
            ("model_version", "model_version"),
            ("production_model", "production_model"),
            ("operating_threshold", "operating_threshold"),
        ):
            value = getattr(cfg, attr, None)
            if value is not None:
                info[key] = value
    except Exception as exc:
        info["error"] = f"engine config unavailable: {exc}"
    return info