"""Append-only audit trail with a hash chain.

Every event hashes the previous event's hash, so deleting or editing a row breaks the
chain and shows up in verify_chain(). That is cheap tamper-evidence, which is the part
of a DPDP audit obligation a prototype can actually demonstrate.

Nothing in this module ever updates or deletes an AuditEvent.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any  

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.orm import AuditEvent

# Fields we deliberately do not copy into the audit payload. The audit trail records
# that an event happened and on what basis, not a second copy of the clinical record 
REDACTED_KEYS = {"symptom_text", "patient_name", "phone", "email", "address"}
MAX_TEXT_LENGTH = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _redact(payload: Any) -> Any:
    """Drop sensitive keys and truncate long free text, recursively."""
    if isinstance(payload, dict):
        clean = {}
        for key, value in payload.items():
            if key in REDACTED_KEYS:
                clean[key] = "[redacted]"
            else:
                clean[key] = _redact(value)
        return clean
    if isinstance(payload, (list, tuple)):
        return [_redact(item) for item in payload]
    if isinstance(payload, str) and len(payload) > MAX_TEXT_LENGTH:
        return payload[:MAX_TEXT_LENGTH] + "...[truncated]"
    return payload


def _canonical(data: dict) -> str:
    """Stable serialisation — the hash must not depend on key order."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _compute_hash(
    prev_hash: str | None,
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor: str,
    purpose: str,
    payload: dict,
    created_at: datetime,
) -> str:
    material = _canonical(
        {
            "prev": prev_hash or "",
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor": actor,
            "purpose": purpose,
            "payload": payload,
            "created_at": created_at.isoformat(),
         }  
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _last_event(db: Session) -> AuditEvent | None:
    return db.execute(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
    ).scalar_one_or_none()


def record_event(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str | int,
    actor: str = "system",
    purpose: str = "clinical_triage",
    payload: dict | None = None,
    commit: bool = False,
) -> AuditEvent | None:
    """Append one event. Returns None on failure — auditing must never take down the
    request that triggered it, but the failure is surfaced on stdout."""
    safe_payload = _redact(payload or {})
    created_at = _now()

    try:
        previous = _last_event(db)
        prev_hash = previous.event_hash if previous else None

        event = AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
            actor=actor,
            purpose=purpose,
            payload=safe_payload,
            prev_hash=prev_hash,
            event_hash=_compute_hash(
                prev_hash, event_type, entity_type, str(entity_id),
                actor, purpose, safe_payload, created_at,
            ),
            created_at=created_at,
        )
        db.add(event)
        db.flush()
        if commit:
            db.commit()
        return event
    except SQLAlchemyError as exc:
        print(f"[warn] audit write failed for {event_type}: {exc}")
        if commit:
            db.rollback()
        return None


def list_events(
    db: Session, *,
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    limit: int = 100) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(max(1, min(limit, 1000)))
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == str(entity_id))
    return list(db.execute(stmt).scalars())


def verify_chain(db: Session) -> tuple[int, bool, int | None]:
    """Recompute every hash in order. Returns (count, intact, first_broken_id)."""
    events = list(db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars())
    prev_hash: str | None = None

    for event in events:
        expected = _compute_hash(
            prev_hash,
            event.event_type,
            event.entity_type,
            event.entity_id,
            event.actor,
            event.purpose,
            event.payload or {},
            event.created_at,
        )
        if event.prev_hash != prev_hash or event.event_hash != expected:
            return len(events), False, event.id
        prev_hash = event.event_hash

    return len(events), True, None

          
def event_count(db: Session) -> int:
    return int(db.execute(select(func.count(AuditEvent.id))).scalar() or 0)