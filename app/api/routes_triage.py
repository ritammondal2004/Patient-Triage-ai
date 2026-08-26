"""Triage scoring endpoints."""

from fastapi import APIRouter, HTTPException

from app.api.deps import ApiKey, DbSession
from app.models.schemas import (
    AssessmentOut,
    ConfidenceOut,
    EngineInfoOut,
    PatientOut,   
    ReassessmentOut ,
    TriageResponse, 
    VisitIntakeRequest,
    VisitOut,
    VitalsOut,
    VitalsUpdateRequest,
)
from app.services import reassessment_service, triage_service

router = APIRouter(prefix="/triage", tags=["triage"])


def _confidence(assessment) -> ConfidenceOut:
    return ConfidenceOut(
        label=assessment.confidence_label,
        uncertainty_score=round(assessment.uncertainty_score, 4),
        reasons=list(assessment.confidence_reasons or []),
    )


@router.get("/engine", response_model=EngineInfoOut)
def engine_info():
    """Model provenance and the prototype disclaimer, for the UI footer."""
    return EngineInfoOut(**triage_service.engine_info())


@router.post("/intake", response_model=TriageResponse, status_code=201)
def intake(payload: VisitIntakeRequest, db: DbSession, _: ApiKey = None):
    try:
        result = triage_service.intake(db, payload)
    except triage_service.TriageEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return TriageResponse(
        visit=VisitOut.model_validate(result.visit),
        patient=PatientOut.model_validate(result.patient),
        assessment=AssessmentOut.model_validate(result.assessment),
        vitals=VitalsOut.model_validate(result.vitals),
        confidence=_confidence(result.assessment),
    )


@router.get("/visits/{visit_id}", response_model=list[AssessmentOut])
def visit_assessments(visit_id: int, db: DbSession, _: ApiKey = None):
    """Full scoring history for one visit, oldest first — shows every escalation."""
    if triage_service.get_visit(db, visit_id) is None:
        raise HTTPException(status_code=404, detail=f"visit {visit_id} not found")
    return triage_service.assessment_history(db, visit_id)


@router.post("/visits/{visit_id}/vitals", response_model=ReassessmentOut)
def submit_vitals(visit_id: int, payload: VitalsUpdateRequest, db: DbSession, _: ApiKey = None):
    """Record fresh vitals; worsening values trigger a reassessment."""
    try:
        result = reassessment_service.submit_vitals(db, visit_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    assessment = result.pop("assessment", None)
    result.pop("vitals_record_id", None)
    return ReassessmentOut(
        **result,
        assessment=AssessmentOut.model_validate(assessment) if assessment else None,
    )


@router.post("/visits/{visit_id}/rescore", response_model=AssessmentOut)
def rescore(visit_id: int, db: DbSession, _: ApiKey = None):
    try:
        return triage_service.rescore(db, visit_id, "manual_rescore")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except triage_service.TriageEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/visits/{visit_id}/reassessment", response_model=ReassessmentOut)
def reassessment_status(visit_id: int, db: DbSession, _: ApiKey = None):
    """Is this patient overdue? Read-only — does not rescore."""
    try:
        result = reassessment_service.check_visit(db, visit_id, rescore=False)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result.pop("assessment", None)
    return ReassessmentOut(**result, assessment=None)