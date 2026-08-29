
"""Clinician override capture — the clinician always has the final say."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import ApiKey, DbSession, DemoHospital
from app.models.orm import ClinicianOverride, TriageAssessment, Visit
from app.models.schemas import OverrideOut, OverrideRequest
from app.services import audit_service
        
router = APIRouter(prefix="/overrides", tags=["overrides"])


@router.post("/assessments/{assessment_id}", response_model=OverrideOut, status_code=201)
def create_override(assessment_id: int, payload: OverrideRequest, db: DbSession, _: ApiKey = None):
    assessment = db.get(TriageAssessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"assessment {assessment_id} not found")

    existing = db.execute(
        select(ClinicianOverride).where(ClinicianOverride.assessment_id == assessment_id)
    ).scalar_one_or_none()
    if existing is not None:
        # One override per assessment. Overriding again means rescoring first, so the
        # trail stays a sequence of decisions rather than an edited record.
        raise HTTPException(
            status_code=409,
            detail=f"assessment {assessment_id} was already overridden (override {existing.id})",
        )

    ai_priority = int(assessment.final_priority)
    new_priority = int(payload.override_priority)
    if new_priority == ai_priority:
        raise HTTPException(
            status_code=400,
            detail="override_priority matches the AI priority; nothing to override",
        )

    override = ClinicianOverride(
        assessment_id=assessment_id,
        clinician_id=payload.clinician_id,
        clinician_role=payload.clinician_role,
        ai_priority=ai_priority,         
        override_priority=new_priority,  
        direction="escalated" if new_priority < ai_priority else "de-escalated",
        reason_code=payload.reason_code,
        reason_text=payload.reason_text,
        acknowledged_ai_recommendation=payload.acknowledged_ai_recommendation,
        created_at=datetime.now(timezone.utc),
    )

    try:
        db.add(override)
        db.flush()
        # Everything a DPDP audit needs: who, when, what the AI said, what they chose,
        # why, and the model version that produced the recommendation. 
        audit_service.record_event( 
            db, event_type="clinician_override", entity_type="assessment",
            entity_id=assessment_id, actor=payload.clinician_id,
            payload={
                "override_id": override.id,
                "visit_id": assessment.visit_id,
                "clinician_role": override.clinician_role,
                "ai_priority": ai_priority,
                "ai_confidence": assessment.confidence_label,
                "ai_risk_probability": round(assessment.risk_probability, 4),
                "ai_safety_rules": list(assessment.safety_rules_triggered or []),
                "override_priority": new_priority,
                "direction": override.direction,
                "reason_code": override.reason_code,
                "reason_text": override.reason_text,
                "acknowledged_ai_recommendation": override.acknowledged_ai_recommendation,
                "model_version": assessment.model_version,
                "operating_threshold": assessment.operating_threshold,
            },
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"could not record override: {exc}") from exc

    db.refresh(override)
    return override


@router.get("", response_model=list[OverrideOut])
def list_overrides(db: DbSession, hospital: DemoHospital, _: ApiKey = None, limit: int = Query(50, ge=1, le=500)):
    stmt = select(ClinicianOverride).join(TriageAssessment).join(Visit).where(Visit.hospital_id == hospital.id).order_by(ClinicianOverride.created_at.desc()).limit(limit)
    return list(db.execute(
        select(ClinicianOverride).order_by(ClinicianOverride.id.desc()).limit(limit)
    ).scalars())


@router.get("/{override_id}", response_model=OverrideOut)
def get_override(override_id: int, db: DbSession, _: ApiKey = None):
    override = db.get(ClinicianOverride, override_id)
    if override is None:
        raise HTTPException(status_code=404, detail=f"override {override_id} not found")
    return override


