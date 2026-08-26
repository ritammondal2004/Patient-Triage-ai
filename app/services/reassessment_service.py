
"""Live reassessment monitor.

The problem statement requires the running system to watch patients who are already
waiting, not just the simulation. Two triggers: the wait exceeding the safe target for
the patient's severity, or vitals re-recorded as worsening. The decision itself comes
from risk_engine.reassessment so the API and the SimPy loop cannot disagree.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.orm import TriageAssessment, Visit
from app.models.schemas import VitalsUpdateRequest
from app.services import audit_service, queue_service, triage_service
from risk_engine import reassessment as policy


def _signal_for(db: Session, visit: Visit, now: datetime | None = None):
    assessment = triage_service.latest_assessment(db, visit.id)
    priority = triage_service.effective_priority(assessment) if assessment else None
    return assessment, policy.evaluate(
        priority=priority,
        waited_minutes=triage_service.minutes_since(visit.arrived_at, now),
        age=visit.patient.age if visit.patient else None,
        previous_vitals=triage_service.vitals_as_dict(triage_service.previous_vitals(db, visit.id)),
        latest_vitals=triage_service.vitals_as_dict(triage_service.latest_vitals(db, visit.id)),
        minutes_since_last_assessment=(
            triage_service.minutes_since(assessment.created_at, now) if assessment else None
        ),
    )


def check_visit(db: Session, visit_id: int, rescore: bool = False) -> dict:
    """Evaluate one waiting patient. With rescore=True, actually re-run the engine."""
    visit = triage_service.get_visit(db, visit_id)
    if visit is None:
        raise LookupError(f"visit {visit_id} not found")

    assessment, signal = _signal_for(db, visit)
    result = {
        "visit_id": visit.id,
        "due": signal.due,
        "trigger": signal.trigger,
        "urgency": signal.urgency,
        "reasons": signal.reasons,
        "previous_priority": triage_service.effective_priority(assessment) if assessment else None,
        "new_priority": None,
        "assessment": None,
    }

    if not (signal.due and rescore):
        return result

    if visit.status != "waiting":
        result["reasons"] = result["reasons"] + [f"Not rescored: visit is {visit.status}"]
        return result

    new_assessment = _rescore(db, visit, signal)
    if new_assessment is not None:
        result["new_priority"] = triage_service.effective_priority(new_assessment)
        result["assessment"] = new_assessment
    return result


def _rescore(db: Session, visit: Visit, signal) -> TriageAssessment | None:
    trigger = signal.trigger or "manual_rescore"
    try:
        assessment = triage_service.score_and_persist(
            db, visit, triage_service.latest_vitals(db, visit.id), trigger
        )
        audit_service.record_event(
            db, event_type="reassessment_triggered", entity_type="visit", entity_id=visit.id,
            actor="reassessment_monitor",
            payload={
                "trigger": trigger,
                "urgency": signal.urgency,
                "reasons": signal.reasons,
                "waited_minutes": round(signal.waited_minutes, 1),
                "max_wait_minutes": signal.max_wait_minutes,
                "new_priority": assessment.final_priority,
                "assessment_id": assessment.id,
            },
        )
        db.commit()
        return assessment
    except triage_service.TriageEngineError as exc:
        db.rollback()
        print(f"[warn] reassessment scoring failed for visit {visit.id}: {exc}")
        return None
    except SQLAlchemyError as exc:
        db.rollback()
        print(f"[warn] reassessment persist failed for visit {visit.id}: {exc}")
        return None


def sweep(db: Session, hospital_id: int | None = None, rescore: bool = True) -> dict:
    """Scan the whole waiting room. This is what a scheduler would call every minute."""
    now = datetime.now(timezone.utc)
    checked, due, rescored, escalated = 0, 0, 0, 0
    details: list[dict] = []

    for visit in queue_service.waiting_visits(db, hospital_id):
        checked += 1
        assessment, signal = _signal_for(db, visit, now)
        if not signal.due:
            continue

        due += 1
        before = triage_service.effective_priority(assessment) if assessment else None
        entry = {
            "visit_id": visit.id,
            "trigger":  signal.trigger,
            "urgency": signal.urgency,
            "reasons": signal.reasons,
            "previous_priority": before,
            "new_priority":before,
        }

        if rescore:
            new_assessment = _rescore(db, visit, signal)
            if new_assessment is not None:
                rescored += 1
                after = triage_service.effective_priority(new_assessment)
                entry["new_priority"] = after
                if before is not None and after < before:
                    escalated += 1

        details.append(entry)

    return {
        "checked": checked,
        "due": due,
        "rescored": rescored,
        "escalated": escalated,
        "details": details,
    }


def submit_vitals(db: Session, visit_id: int, payload: VitalsUpdateRequest) -> dict:
    """Record a fresh set of vitals, then check whether they represent deterioration.

    This is the second PS trigger. The vitals row is committed even if the rescore fails,
    so an observation is never lost because the model was unavailable.
    """
    visit = triage_service.get_visit(db, visit_id)
    if visit is None:
        raise LookupError(f"visit {visit_id} not found")

    try:
        record = triage_service.record_vitals(db, visit, payload.vitals)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"could not record vitals for visit {visit_id}: {exc}") from exc

    assessment, signal = _signal_for(db, visit)
    result = {
        "visit_id": visit.id,
        "vitals_record_id": record.id,
        "due": signal.due,
        "trigger": signal.trigger,
        "urgency": signal.urgency,
        "reasons": signal.reasons,
        "previous_priority": triage_service.effective_priority(assessment) if assessment else None,
        "new_priority": None,
        "assessment": None,
    }

    # New vitals always justify a rescore if requested — the model's last score was computed on stale observations.
    if payload.rescore and visit.status == "waiting":
        trigger = signal.trigger or "manual_rescore"
        try:
            new_assessment = triage_service.score_and_persist(db, visit, record, trigger)
            if signal.due:
                audit_service.record_event(
                    db, event_type="reassessment_triggered", entity_type="visit",
                    entity_id=visit.id, actor=payload.recorded_by,
                    payload={"trigger": trigger, "reasons": signal.reasons,
                             "assessment_id": new_assessment.id},
                )
            db.commit()
            result["new_priority"] = triage_service.effective_priority(new_assessment)
            result["assessment"] = new_assessment
        except (triage_service.TriageEngineError, SQLAlchemyError) as exc:
            db.rollback()
            result["reasons"] = result["reasons"] + [f"Rescore failed: {exc}"]

    return result  