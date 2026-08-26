
"""Patient and visit lookups."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import ApiKey, DbSession
from app.models.orm import Patient, Visit
from app.models.schemas import PatientOut, VisitOut

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientOut])
def list_patients(db: DbSession, _: ApiKey = None, limit: int = Query(50, ge=1, le=500)):
    stmt = select(Patient).order_by(Patient.id.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


@router.get("/{patient_code}", response_model=PatientOut)
def get_patient(patient_code: str, db: DbSession, _: ApiKey = None):
    patient = db.execute(
        select(Patient).where(Patient.patient_code == patient_code)
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=404, detail=f"patient '{patient_code}' not found")
    return patient


@router.get("/{patient_code}/visits", response_model=list[VisitOut])
def list_patient_visits(patient_code: str, db: DbSession, _: ApiKey = None):
    patient = db.execute(
        select(Patient).where(Patient.patient_code == patient_code)
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=404, detail=f"patient '{patient_code}' not found")
    return list(db.execute(
        select(Visit).where(Visit.patient_id == patient.id).order_by(Visit.arrived_at.desc())
    ).scalars())  