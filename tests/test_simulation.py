
"""Coverage for the discrete-event model.

Horizons are kept short on purpose: these are contract tests, not a study. The one
scenario-wide sweep is the slowest test here and still finishes in seconds.
"""

import json

import pytest

from risk_engine.config import DEFAULT_SAFETY_MODE, PRODUCTION_MODEL_PATH

simpy = pytest.importorskip("simpy", reason="simpy not installed")

from simulation.ed_simulation import SimConfig, SimulationFailure, run_simulation
from simulation.scenarios import SCENARIOS, reassessment_ablation, run_scenario

requires_artifact = pytest.mark.skipif(
    not PRODUCTION_MODEL_PATH.exists(),
    reason="production model artifact not present",
)

pytestmark = requires_artifact

      
@pytest.fixture(scope="module")
def baseline():
    return run_simulation(horizon_hours=8.0, multiplier=2.0, seed=42)


def test_safety_mode_resolves_instead_of_staying_none():
    # Regression: None reached the safety rules and failed on every patient.
    assert SimConfig().safety_mode == DEFAULT_SAFETY_MODE
    assert SimConfig(safety_mode="  Balanced ").safety_mode == "balanced"


def test_a_bad_safety_mode_fails_loudly_not_silently():
    with pytest.raises(SimulationFailure):
        run_simulation(horizon_hours=2.0, safety_mode="not-a-mode")


def test_the_cohort_actually_gets_scored(baseline):
    assert baseline["arrivals"] > 0, "no patient ever arrived"
    assert baseline["treated"] > 0, "no patient was ever treated"
    assert baseline["scoring_errors"] == 0, baseline["first_scoring_error"]
    assert baseline["first_scoring_error"] is None


def test_reported_mode_is_the_mode_used(baseline):
    assert baseline["scenario_params"]["safety_mode"] == DEFAULT_SAFETY_MODE


def test_metrics_survive_json_encoding(baseline):
    # The API stores these in a JSON column, so numpy scalars would break persistence.
    assert json.loads(json.dumps(baseline))["arrivals"] == baseline["arrivals"]


def test_same_seed_same_run():
    a = run_simulation(horizon_hours=6.0, seed=7)
    b = run_simulation(horizon_hours=6.0, seed=7)
    for key in ("arrivals", "treated", "mean_wait_minutes", "escalations"):
        assert a[key] == b[key]


def test_different_seeds_diverge():
    a = run_simulation(horizon_hours=6.0, seed=7)
    b = run_simulation(horizon_hours=6.0, seed=8)
    assert (a["arrivals"], a["mean_wait_minutes"]) != (b["arrivals"], b["mean_wait_minutes"])


def test_load_rises_with_the_arrival_multiplier():
    light = run_simulation(horizon_hours=8.0, multiplier=1.0, seed=42)
    heavy = run_simulation(horizon_hours=8.0, multiplier=4.0, seed=42)
    assert heavy["arrivals"] > light["arrivals"]
    assert heavy["offered_load_rho"] > light["offered_load_rho"]


def test_treated_patients_are_split_across_dayparts(baseline):
    parts = baseline["by_daypart"]
    assert parts["day"]["treated"] + parts["night"]["treated"] == baseline["treated"]


def test_priority_breakdown_covers_only_treated_patients(baseline):
    counted = sum(band["treated"] for band in baseline["by_priority"].values())
    assert counted == baseline["treated"]
    assert all(1 <= int(level) <= 5 for level in baseline["by_priority"])


def test_reassessment_can_only_help():
    result = reassessment_ablation(multiplier=3.0, seed=42, horizon_hours=8.0)
    assert result["with_reassessment"]["arrivals"] > 0
    assert result["delta"]["under_triaged_at_treatment_avoided"] >= 0
    # Escalation is one-way, so nobody may be treated at a lower priority than at intake.
    assert (result["with_reassessment"]["high_risk_low_priority_at_treatment"]
            <= result["with_reassessment"]["high_risk_low_priority_at_intake"])


def test_disabling_reassessment_stops_escalation():
    static = run_simulation(horizon_hours=8.0, multiplier=3.0, seed=42,
                            reassessment_enabled=False)
    assert static["reassessments"] == 0
    assert static["escalations"] == 0


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_every_named_scenario_runs(name):
    result = run_scenario(name, horizon_hours=4.0)
    assert result["scenario"] == name
    assert result["scoring_errors"] == 0, result["first_scoring_error"] 