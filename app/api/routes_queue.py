

"""Live waiting queue and the reassessment sweep."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import ApiKey, DbSession
from app.models.schemas import QueueEntryOut
from app.services import queue_service, reassessment_service

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("", response_model=list[QueueEntryOut])
def get_queue(db: DbSession, _: ApiKey = None, hospital_id: int | None = Query(None)):
    return [QueueEntryOut(**entry) for entry in queue_service.build_queue(db, hospital_id)]


@router.get("/summary")
def get_summary(db: DbSession, _: ApiKey = None, hospital_id: int | None = Query(None)):
    return queue_service.queue_summary(db, hospital_id)


@router.post("/next")
def call_next(db: DbSession, _: ApiKey = None, hospital_id: int | None = Query(None)):
    entry = queue_service.call_next(db, hospital_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="queue is empty")
    return entry


@router.post("/visits/{visit_id}/close")
def close_visit(visit_id: int, db: DbSession, _: ApiKey = None, status: str = "discharged"):
    visit = queue_service.close_visit(db, visit_id, status)
    if visit is None:
        raise HTTPException(status_code=404, detail=f"visit {visit_id} not found")
    return {"visit_id": visit.id, "status": visit.status, "closed_at": visit.closed_at}


@router.post("/reassess")
def reassess_all(db: DbSession, _: ApiKey = None, hospital_id: int | None = Query(None),
                 rescore: bool = True):
    """Sweep every waiting patient for wait breaches and worsening vitals."""
    return reassessment_service.sweep(db, hospital_id, rescore=rescore)