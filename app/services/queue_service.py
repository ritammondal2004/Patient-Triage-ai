
"""Dynamic waiting queue, derived from visit status plus each visit's latest assessment.

There is no queue table on purpose: a stored queue can drift out of sync with the triage
decisions that define it. Ordering is priority first, then longest wait within a tier, so
a patient who has been waiting is never overtaken by a same-priority new arrival.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.orm import Visit
from app.services import audit_service, triage_service
from risk_engine import reassessment as policy

ACTIVE_STATUSES = ("waiting",)


def waiting_visits(db: Session, hospital_id: int | None = None) -> list[Visit]:
    stmt = (
        select(Visit)
        .where(Visit.status.in_(ACTIVE_STATUSES))
        .options(selectinload(Visit.patient))
        .order_by(Visit.arrived_at)
    )
    if hospital_id is not None:
        stmt = stmt.where(Visit.hospital_id == hospital_id)
    return list(db.execute(stmt).scalars())


def _entry(db: Session, visit: Visit, now: datetime) -> dict | None:
    """Build one queue row. Visits with no assessment yet are skipped rather than shown
    without a priority — an unscored patient in a priority queue is worse than absent."""
    assessment = triage_service.latest_assessment(db, visit.id)
    if assessment is None:
        return None

    priority = triage_service.effective_priority(assessment)
    waited = triage_service.minutes_since(visit.arrived_at, now)

    signal = policy.evaluate(
        priority=priority,
        waited_minutes=waited,
        age=visit.patient.age if visit.patient else None,
        previous_vitals=triage_service.vitals_as_dict(triage_service.previous_vitals(db, visit.id)),
        latest_vitals=triage_service.vitals_as_dict(triage_service.latest_vitals(db, visit.id)),
        minutes_since_last_assessment=triage_service.minutes_since(assessment.created_at, now),
    )

    return {
        "visit_id": visit.id,
        "patient_code": visit.patient.patient_code if visit.patient else "unknown",
        "age": visit.patient.age if visit.patient else 0,
        "chief_complaint": visit.chief_complaint,
        "arrival_mode": visit.arrival_mode,
        "final_priority": priority,
        "priority_label": triage_service.priority_label(priority),
        "confidence_label": assessment.confidence_label,
        "risk_probability": round(assessment.risk_probability, 4),
        "escalated_by_rules": assessment.escalated_by_rules,
        "escalated_by_uncertainty": assessment.escalated_by_uncertainty,
        "safety_rules_triggered": list(assessment.safety_rules_triggered or []),
        "arrived_at": visit.arrived_at,
        "waited_minutes": round(waited, 1),
        "max_wait_minutes": signal.max_wait_minutes,
        "wait_breached": signal.wait_breached,
        "reassessment_due": signal.due,
        "reassessment_reasons": signal.reasons,
        "last_assessed_at": assessment.created_at,
        "override_applied": getattr(assessment, "override", None) is not None,
    }


def build_queue(db: Session, hospital_id: int | None = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    entries = [e for v in waiting_visits(db, hospital_id) if (e := _entry(db, v, now))]
    entries.sort(key=lambda e: (e["final_priority"], -e["waited_minutes"]))
    for position, entry in enumerate(entries, start=1):
        entry["queue_position"] = position
    return entries


def queue_summary(db: Session, hospital_id: int | None = None) -> dict:
    entries = build_queue(db, hospital_id)
    if not entries:
        return {
            "waiting": 0, "by_priority": {}, "wait_breaches": 0,
            "reassessments_due": 0, "longest_wait_minutes": 0.0,
            "average_wait_minutes": 0.0, "low_confidence": 0,
        }

    by_priority: dict[int, int] = {}
    for entry in entries:
        by_priority[entry["final_priority"]] = by_priority.get(entry["final_priority"], 0) + 1

    waits = [e["waited_minutes"] for e in entries]
    return {
        "waiting": len(entries),
        "by_priority": dict(sorted(by_priority.items())),
        "wait_breaches": sum(1 for e in entries if e["wait_breached"]),
        "reassessments_due": sum(1 for e in entries if e["reassessment_due"]),
        "longest_wait_minutes": round(max(waits), 1),
        "average_wait_minutes": round(sum(waits) / len(waits), 1),
        "low_confidence": sum(1 for e in entries if e["confidence_label"] == "Low"),
    }


def call_next(db: Session, hospital_id: int | None = None) -> dict | None:
    """Pull the head of the queue into treatment."""
    queue = build_queue(db, hospital_id)
    if not queue:
        return None

    head = queue[0]
    visit = db.get(Visit, head["visit_id"])
    if visit is None:
        return None

    try:
        visit.status = "in_treatment"
        visit.treatment_started_at = datetime.now(timezone.utc)
        audit_service.record_event(
            db, event_type="visit_created", entity_type="visit", entity_id=visit.id,
            actor="queue", payload={
                "action": "called_for_treatment",
                "priority": head["final_priority"],
                "waited_minutes": head["waited_minutes"],
                "wait_breached": head["wait_breached"],
            },
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"could not call next patient: {exc}") from exc

    head["status"] = visit.status
    return head


def close_visit(db: Session, visit_id: int, status: str = "discharged") -> Visit | None:
    visit = db.get(Visit, visit_id)
    if visit is None:
        return None
    try:
        visit.status = status
        visit.closed_at = datetime.now(timezone.utc)
        audit_service.record_event(
            db, event_type="visit_created", entity_type="visit", entity_id=visit.id,
            actor="queue", payload={"action": "closed", "status": status},
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"could not close visit {visit_id}: {exc}") from exc
    return visit  