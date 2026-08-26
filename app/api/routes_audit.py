
"""Audit trail read-back and integrity check."""

from fastapi import APIRouter, Query

from app.api.deps import ApiKey, DbSession
from app.core.config import get_settings
from app.models.schemas import AuditChainStatus, AuditEventOut
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventOut])
def list_events(
    db: DbSession,
    _: ApiKey = None,
    event_type: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000)):  
    return audit_service.list_events(
        db, event_type=event_type, entity_type=entity_type,
        entity_id=entity_id, limit=limit,
    )


@router.get("/verify", response_model=AuditChainStatus)
def verify_chain(db: DbSession, _: ApiKey = None):
    """Recompute the hash chain. A broken link means a row was edited or deleted."""
    count, intact, first_broken = audit_service.verify_chain(db)
    return AuditChainStatus(events=count, intact=intact, first_broken_id=first_broken)


@router.get("/policy")
def retention_policy(_: ApiKey = None):
    """The assumed regulatory position, stated explicitly as the PS requires."""
    settings = get_settings()
    return {
        "jurisdiction": settings.jurisdiction,
        "retention_days": settings.retention_days,
        "consent_notice_version": settings.consent_notice_version,
        "lawful_basis": "Consent for clinical triage; legitimate use for emergency care.",
        "purpose_limitation": "Data is used for triage decision support and quality audit only.",
        "audit_trail": "Append-only, hash-chained. Never updated or deleted by application code.",
        "override_record": "Every clinician override stores actor, role, reason, the AI "
                           "recommendation it replaced, and the model version.",
        "note": "Prototype on 100% synthetic data. No real personal data is processed.",
    }      