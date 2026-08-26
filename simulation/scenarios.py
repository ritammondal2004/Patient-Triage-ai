
"""Named scenarios, plus the two ablations worth putting on a slide."""

from simulation.ed_simulation import run_simulation

SCENARIOS = {
    "normal": {
        "multiplier": 1.0, "doctors": 4, "beds": 12,
        "label": "Typical day, ~204 arrivals, rho ~0.77",
    },
    "busy": {       
        "multiplier": 1.5, "doctors": 4, "beds": 12,
        "label": "Busy day, 1.5x arrivals, rho ~1.16",
    },
    "surge": {
        "multiplier": 3.0, "doctors": 4, "beds": 12,
        "label": "Mass-casualty surge, 3x arrivals, same staff, rho ~2.3",
    },
    "surge_no_reassessment": {
        "multiplier": 3.0, "doctors": 4, "beds": 12, "reassessment_enabled": False,
        "label": "Surge with static triage, no reassessment loop",
    },
    "surge_staffed": {
        "multiplier": 3.0, "doctors": 10, "beds": 26,
        "label": "Surge with surge staffing, rho ~0.93",
    },
    "flat_arrivals": {
        "multiplier": 1.0, "doctors": 4, "beds": 12,
        "use_diurnal": False, "use_night_acuity": False,
        "label": "Same daily volume, no time-of-day effect (control)",
    },
}


def run_scenario(name: str, **overrides) -> dict:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario '{name}'; choose from {sorted(SCENARIOS)}")
    params = {k: v for k, v in SCENARIOS[name].items() if k != "label"}
    params.update(overrides)
    result = run_simulation(**params)
    result["scenario"] = name
    result["label"] = SCENARIOS[name]["label"]
    return result


def compare(names: list[str] | None = None, **overrides) -> list[dict]:
    return [run_scenario(name, **overrides) for name in (names or list(SCENARIOS))]


def reassessment_ablation(multiplier: float = 3.0, seed: int =42, **overrides) -> dict:
    """Same arrivals, same staff, same seed -- reassessment on versus off.
    """
    shared = {"multiplier": multiplier, "seed": seed, **overrides}
    with_loop = run_simulation(reassessment_enabled=True, **shared)
    without_loop = run_simulation(reassessment_enabled=False, **shared)
    return {
        "with_reassessment": with_loop,
        "without_reassessment": without_loop,
        "delta": {
            "caught_by_reassessment": with_loop["caught_by_reassessment"],
            "under_triaged_at_treatment_avoided": (
                without_loop["high_risk_low_priority_at_treatment"]
                - with_loop["high_risk_low_priority_at_treatment"]
            ),
            "mean_wait_change": round(
                with_loop["mean_wait_minutes"] - without_loop["mean_wait_minutes"], 1
            ),
            "escalations": with_loop["escalations"],
        },
    }


def daynight_contrast(seed: int = 42, **overrides) -> dict:
    """Does the night-acuity effect actually show up in the outcomes?"""
    result = run_simulation(seed=seed, **overrides)
    day, night = result["by_daypart"]["day"], result["by_daypart"]["night"]
    return {
        "day": day,
        "night": night,
        "delta": {
            "high_risk_share": round(night.get("high_risk_share", 0)
                                     - day.get("high_risk_share", 0), 3),
            "mean_wait": round(night.get("mean_wait", 0) - day.get("mean_wait", 0), 1),
        },
    }