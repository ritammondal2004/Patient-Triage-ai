
"""Surge-simulation endpoints.

Routes are deliberately sync: FastAPI runs sync handlers in a worker thread, so a
long simulation never blocks the event loop.
"""
       
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import ApiKey, DbSession
from app.models.schemas import SimulationRequest, SimulationResultOut
from app.services import simulation_service

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("/scenarios")
def scenarios(_: ApiKey = None):
    """Named scenarios the UI can offer, with the capacity each one assumes."""
    try:
        return {"scenarios": simulation_service.available_scenarios()}
    except simulation_service.SimulationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/run", response_model=SimulationResultOut, status_code=201)
def run(payload: SimulationRequest, db: DbSession, _: ApiKey = None):
    """Run one scenario. arrival_multiplier scales the scenario, it does not replace it."""
    try:
        return SimulationResultOut(**simulation_service.run(db, payload))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except simulation_service.SimulationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/runs", response_model=list[SimulationResultOut])
def runs(db: DbSession, scenario: str | None = None,
         limit: int = Query(20, ge=1, le=100), _: ApiKey = None):
    return simulation_service.history(db, scenario=scenario, limit=limit)


@router.get("/runs/{run_id}", response_model=SimulationResultOut)
def run_detail(run_id: int, db: DbSession, _: ApiKey = None):
    record = simulation_service.get_run(db, run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"simulation run {run_id} not found")
    return record


@router.post("/ablation")
def ablation(multiplier: float = Query(3.0, gt=0, le=10),
             seed: int = 42,
             hours: float = Query(24.0, gt=0, le=72),
             _: ApiKey = None):
    """Reassessment on versus off under the same seed -- the core evidence for the loop."""
    try:
        return simulation_service.reassessment_ablation(multiplier, seed, hours)
    except simulation_service.SimulationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/daynight")
def daynight(seed: int = 42, hours: float = Query(24.0, gt=0, le=72), _: ApiKey = None):
    """Day versus night acuity and waiting, from a single 24h run."""
    try:
        return simulation_service.daynight_contrast(seed, hours)
    except simulation_service.SimulationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc