"""What-if surge simulation, exposed to the API.

The simulation is a pure CPU job. It builds its own synthetic cohort, scores it with the
same risk engine the live endpoints use, and never reads or writes the patient tables --
only the summarised metrics are persisted. That keeps a capacity-planning feature clear of
the clinical data path entirely.

Runs are deterministic in their seed, so identical parameters are served from a small
in-process cache rather than recomputed: a demo audience clicking the same button twice
should not wait twice.
"""

from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.orm import SimulationRun
from app.models.schemas import SimulationRequest
from app.services import audit_service


class SimulationError(RuntimeError):
    """The simulation could not run at all -- missing dependency or a broken engine."""


MAX_HOURS = 72.0
_CACHE_LIMIT = 24

_cache: dict[tuple, dict] = {}
_cache_order: list[tuple] = []
_cache_lock = threading.Lock()
# One simulation at a time. Serialising is cheap because results are cached, and it stops
# a demo audience hammering the button from pinning every worker thread.
_compute_lock = threading.Lock()


def _scenarios():
    """Imported lazily: simpy and the model artifact must not be required to boot the API."""
    try:
        from simulation import scenarios
    except Exception as exc:
        raise SimulationError(f"simulation package unavailable: {exc}") from exc
    return scenarios


def _json_safe(value: Any) -> Any:
    """Coerce numpy scalars and non-string keys so the JSON columns can store the result."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return str(value)


def available_scenarios() -> list[dict[str, Any]]:
    """Scenario catalogue for the UI dropdown."""
    settings = get_settings()
    mod = _scenarios()
    out = []
    for name, spec in mod.SCENARIOS.items():
        out.append({
            "name": name,
            "label": spec.get("label", name),
            "arrival_multiplier": spec.get("multiplier", 1.0),
            "doctors": spec.get("doctors", settings.default_doctors),
            "beds": spec.get("beds", settings.default_beds),
            "reassessment_enabled": spec.get("reassessment_enabled", True),
        })
    return out


def _plan(request: SimulationRequest) -> tuple[dict[str, Any], tuple]:
    """Turn a request into run_scenario overrides plus its cache key."""
    mod = _scenarios()
    if request.scenario not in mod.SCENARIOS:
        raise KeyError(
            f"unknown scenario '{request.scenario}'; choose from {sorted(mod.SCENARIOS)}"
        )

    hours = min(max(float(request.hours), 0.5), MAX_HOURS)
    base = float(mod.SCENARIOS[request.scenario].get("multiplier", 1.0))
    # arrival_multiplier scales the scenario instead of replacing it, so scenario="surge"
    # with multiplier 2 means "twice the surge" rather than silently cancelling the 3x.
    effective = round(base * float(request.arrival_multiplier), 4)

    overrides: dict[str, Any] = {
        "multiplier": effective,
        "horizon_hours": hours,
        "seed": int(request.seed),
    }
    if request.doctors is not None:
        overrides["doctors"] = int(request.doctors)
    if request.beds is not None:
        overrides["beds"] = int(request.beds)

    key = (request.scenario, effective, hours, overrides["seed"],
           overrides.get("doctors"), overrides.get("beds"))
    return overrides, key


def _cache_get(key: tuple) -> dict | None:
    with _cache_lock:
        hit = _cache.get(key)
    return dict(hit) if hit is not None else None


def _cache_put(key: tuple, result: dict) -> None:
    with _cache_lock:
        _cache[key] = result
        if key not in _cache_order:
            _cache_order.append(key)
        while len(_cache_order) > _CACHE_LIMIT:
            _cache.pop(_cache_order.pop(0), None)


def clear_cache() -> int:
    """Drop cached runs -- call after swapping the model artifact."""
    with _cache_lock:
        count = len(_cache)
        _cache.clear()
        _cache_order.clear()
    return count


def simulate(request: SimulationRequest) -> dict:
    """Run (or serve from cache) one scenario. No database access."""
    mod = _scenarios()
    overrides, key = _plan(request)

    cached = _cache_get(key)
    if cached is not None:
        cached["cached"] = True
        return cached

    with _compute_lock:
        # Re-check: another thread may have computed this while we waited.
        cached = _cache_get(key)
        if cached is not None:
            cached["cached"] = True
            return cached
        try:
            result = mod.run_scenario(request.scenario, **overrides)
        except KeyError:
            raise
        except Exception as exc:
            raise SimulationError(f"simulation failed: {exc}") from exc
        result = _json_safe(result)
        _cache_put(key, result)

    out = dict(result)
    out["cached"] = False
    return out


def as_output(result: dict, run: SimulationRun | None = None) -> dict[str, Any]:
    """Split the flat simulation result into the params/metrics shape the API returns."""
    params = result.get("scenario_params") or {}
    metrics = {k: v for k, v in result.items() if k != "scenario_params"}
    return {
        "id": run.id if run is not None else None,
        "scenario": str(result.get("scenario", "custom")),
        "arrival_multiplier": float(params.get("surge_multiplier", 1.0) or 1.0),
        "params": params,
        "metrics": metrics,
        "created_at": run.created_at if run is not None else None,
    }


def persist(db: Session, result: dict) -> SimulationRun | None:
    """Store the summary. Failure here must not lose the caller their result."""
    payload = as_output(result)
    try:
        run = SimulationRun(
            scenario=payload["scenario"][:40],
            arrival_multiplier=payload["arrival_multiplier"],
            params=payload["params"],
            metrics=payload["metrics"],
        )
        db.add(run)
        db.flush()
        # Synthetic cohort only, so the audit purpose is capacity planning, not clinical care.
        audit_service.record_event(
            db,
            event_type="simulation_run",
            entity_type="simulation_run",
            entity_id=run.id,
            purpose="capacity_planning",
            payload={
                "scenario": run.scenario,
                "arrival_multiplier": run.arrival_multiplier,
                "arrivals": payload["metrics"].get("arrivals"),
                "mean_wait_minutes": payload["metrics"].get("mean_wait_minutes"),
                "offered_load_rho": payload["metrics"].get("offered_load_rho"),
                "caught_by_reassessment": payload["metrics"].get("caught_by_reassessment"),
            },
        )
        db.commit()
        db.refresh(run)
        return run
    except SQLAlchemyError as exc:
        db.rollback()
        print(f"[warn] simulation run not persisted: {exc}")
        return None


def run(db: Session | None, request: SimulationRequest) -> dict[str, Any]:
    """Simulate, optionally persist, and return the API-shaped payload."""
    result = simulate(request)
    saved = None
    if request.persist and db is not None:
        saved = persist(db, result)
    return as_output(result, saved)


def history(db: Session, scenario: str | None = None, limit: int = 20) -> list[SimulationRun]:
    stmt = select(SimulationRun).order_by(SimulationRun.id.desc()).limit(max(1, min(limit, 100)))
    if scenario:
        stmt = stmt.where(SimulationRun.scenario == scenario)
    try:
        return list(db.execute(stmt).scalars())
    except SQLAlchemyError as exc:
        print(f"[warn] simulation history unavailable: {exc}")
        return []


def get_run(db: Session, run_id: int) -> SimulationRun | None:
    try:
        return db.get(SimulationRun, run_id)
    except SQLAlchemyError:
        return None


def reassessment_ablation(multiplier: float = 3.0, seed: int = 42,
                          hours: float = 24.0) -> dict[str, Any]:
    """The headline claim: same arrivals, same staff, reassessment on versus off."""
    mod = _scenarios()
    with _compute_lock:
        try:
            result = mod.reassessment_ablation(
                multiplier=float(multiplier), seed=int(seed),
                horizon_hours=min(float(hours), MAX_HOURS),
            )
        except Exception as exc:
            raise SimulationError(f"ablation failed: {exc}") from exc
    return _json_safe(result)


def daynight_contrast(seed: int = 42, hours: float = 24.0) -> dict[str, Any]:
    """Does the night-acuity assumption actually change outcomes, or is it decoration?"""
    mod = _scenarios()
    with _compute_lock:
        try:
            result = mod.daynight_contrast(
                seed=int(seed), horizon_hours=min(float(hours), MAX_HOURS)
            )
        except Exception as exc:
            raise SimulationError(f"day/night contrast failed: {exc}") from exc
    return _json_safe(result)