"""Engine tests.

The pure-logic tests always run. Anything that needs the trained artifact is
skipped when it is absent, so the suite still passes on a fresh clone and in CI
before artifacts are wired in.

Assertions on the artifact deliberately check direction and invariants rather
than exact probabilities, because the model is due to be retrained on a
recalibrated acuity mix.
"""

from __future__ import annotations

import pytest   

from risk_engine import predictor, uncertainty
from risk_engine.config import (
    MAX_WAIT_MINUTES,
    PRODUCTION_MODEL_PATH,
    age_group_for,
    load_config,
)
from risk_engine.feature_engineering import engineer, text_severity_score
from risk_engine.safety_rules import apply_safety_rules, flag_names, priority_floor

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

requires_artifact = pytest.mark.skipif(
    not PRODUCTION_MODEL_PATH.exists(),
    reason="trained pipeline not present in risk_engine/artifacts/",
)


def base_patient(**overrides):
    patient = {
        "patient_id": "TEST-001",
        "age": 40,
        "gender": "female",
        "heart_rate": 80,
        "resp_rate": 16,
        "systolic_bp": 118,
        "diastolic_bp": 75,
        "temperature_c": 37.0,
        "spo2": 98,
        "pain_score": 3,
        "chief_complaint": "back pain",
        "symptom_text": "Patient reports back pain described as chronic ache.",
        "has_prior_history": True,
        "prior_conditions_count": 1,
        "prior_ed_visits": 1,
        "arrival_mode": "walk-in",
    }
    patient.update(overrides)
    return patient


# --- config -----------------------------------------------------------------

def test_config_loads_with_a_tuned_threshold():
    cfg = load_config()
    assert 0.0 < cfg.operating_threshold < 1.0
    assert cfg.operating_threshold != 0.5, "threshold looks like the notebook fallback"
    assert len(cfg.numeric_features) == 20
    assert len(cfg.categorical_features) == 3
    assert set(cfg.vital_norms) == {"pediatric", "adult", "geriatric"}


@pytest.mark.parametrize("age,expected", [
    (0, "pediatric"), (11, "pediatric"), (12, "pediatric"),
    (13, "adult"), (64, "adult"),
    (65, "geriatric"), (94, "geriatric"),
])
def test_age_banding_covers_the_boundaries(age, expected):
    assert age_group_for(age) == expected


def test_wait_targets_get_stricter_with_urgency():
    values = [MAX_WAIT_MINUTES[p] for p in sorted(MAX_WAIT_MINUTES)]
    assert values == sorted(values)
      

# --- feature engineering ----------------------------------------------------

def test_text_severity_stays_in_range_and_ranks_sensibly():
    severe = text_severity_score("crushing chest pain of sudden onset")
    mild = text_severity_score("mild minor chronic discomfort")
    assert severe > 0 > mild
    assert -0.3 <= mild <= severe <= 1.0
    assert text_severity_score(None) == 0.0


def test_same_vitals_deviate_differently_by_age_band():
    child = engineer(base_patient(age=2, heart_rate=130)).row(0)
    adult = engineer(base_patient(age=40, heart_rate=130)).row(0)
    assert child["hr_deviation"] < adult["hr_deviation"]
    assert child["is_pediatric"] == 1 and adult["is_pediatric"] == 0


def test_deviation_is_zero_at_the_midpoint_of_the_band():
    lo, hi = load_config().norms_for("adult")["hr"]
    row = engineer(base_patient(heart_rate=(lo + hi) / 2)).row(0)
    assert row["hr_deviation"] == pytest.approx(0.0)


def test_missing_vitals_are_imputed_and_reported():
    patient = base_patient()
    patient.pop("spo2")
    batch = engineer(patient)
    assert "spo2" in batch.missing_fields[0]
    assert batch.row(0)["spo2"] > 0  # imputed so the pipeline can still run


def test_unknown_category_is_recorded_not_swallowed():
    batch = engineer(base_patient(chief_complaint="alien abduction"))
    assert "chief_complaint" in batch.unknown_categories[0]


def test_missing_history_sets_the_zero_history_flag():
    patient = base_patient(has_prior_history=False, prior_conditions_count=0,
                           prior_ed_visits=0)
    assert engineer(patient).row(0)["zero_history_flag"] == 1


def test_age_is_required():
    patient = base_patient()
    patient.pop("age")
    with pytest.raises(ValueError):
        engineer(patient)


def test_critical_desaturation_fires_critical():
    row = engineer(base_patient(spo2=85)).row(0)
    flags = apply_safety_rules(row)
    assert "critical_low_spo2" in flag_names(flags)
    assert priority_floor(flags) == 1


def test_stroke_cues_fire_regardless_of_normal_vitals():
    row = engineer(base_patient(
        chief_complaint="stroke-like symptoms",
        symptom_text="Patient reports stroke-like symptoms described as facial drooping.",
    )).row(0)
    assert "stroke_red_flag" in flag_names(apply_safety_rules(row))


def test_pediatric_heart_rate_normal_for_age_does_not_fire():
    row = engineer(base_patient(age=2, heart_rate=120, resp_rate=26,
                                systolic_bp=90, spo2=98)).row(0)
    assert "extreme_heart_rate" not in flag_names(apply_safety_rules(row))


def test_missing_vitals_escalate_instead_of_silently_skipping():
    patient = base_patient()
    patient.pop("spo2")
    batch = engineer(patient)
    flags = apply_safety_rules(batch.row(0), missing_fields=batch.missing_fields[0])
    assert "incomplete_vitals_at_intake" in flag_names(flags)
    assert priority_floor(flags) <= 2


def test_balanced_mode_never_fires_more_than_conservative():
    row = engineer(base_patient(spo2=92, pain_score=9)).row(0)
    conservative = set(flag_names(apply_safety_rules(row, mode="conservative")))
    balanced = set(flag_names(apply_safety_rules(row, mode="balanced")))
    assert balanced <= conservative


def test_no_rules_means_no_floor():
    assert priority_floor([]) == 5


# --- confidence

def test_probability_at_the_threshold_is_least_confident():
    cfg = load_config()
    at = uncertainty.assess(cfg.operating_threshold, cfg.operating_threshold)
    far = uncertainty.assess(0.99, cfg.operating_threshold)
    assert at.score == 1.0 and at.label == "Low"
    assert far.score == 0.0 and far.label == "High"


def test_penalties_only_ever_reduce_confidence():
    cfg = load_config()
    plain = uncertainty.assess(0.9, cfg.operating_threshold)
    penalised = uncertainty.assess(
        0.9, cfg.operating_threshold, zero_history=True, missing_fields=("spo2",)
    )
    assert penalised.score >= plain.score
    assert penalised.reasons


#  full engine 

@requires_artifact
def test_every_decision_carries_a_confidence_indicator():
    """The PS forbids returning a score without one."""
    decisions = predictor.score_batch([
        base_patient(),
        base_patient(age=2, heart_rate=165, resp_rate=42, spo2=93,
                     temperature_c=39.4, chief_complaint="high fever"),
        base_patient(age=81, spo2=93, systolic_bp=104, chief_complaint="dizziness"),
    ])
    for decision in decisions:
        assert decision.confidence_label in {"High", "Medium", "Low"}
        assert 0.0 <= decision.uncertainty_score <= 1.0
        assert decision.risk_indicators
        assert 1 <= decision.final_priority <= 5


@requires_artifact
def test_safety_layer_only_ever_escalates():
    calm = base_patient()
    critical = base_patient(spo2=84, systolic_bp=70)
    for decision in predictor.score_batch([calm, critical]):
        assert decision.final_priority <= decision.ml_only_priority


@requires_artifact
def test_critical_rule_forces_top_priority_even_on_a_low_probability():
    decision = predictor.score(base_patient(
        chief_complaint="psychiatric distress",
        symptom_text="Patient reports psychiatric distress described as suicidal ideation.",
    ))
    assert decision.final_priority == 1
    assert "suicidal_ideation" in decision.safety_rules_triggered
    assert decision.escalated_by_rules


@requires_artifact
def test_batch_and_single_scoring_agree():
    patients = [base_patient(patient_id="A"), base_patient(patient_id="B", spo2=90)]
    batched = predictor.score_batch(patients)
    singles = [predictor.score(p) for p in patients]
    assert [d.risk_probability for d in batched] == [d.risk_probability for d in singles]
    assert [d.final_priority for d in batched] == [d.final_priority for d in singles]


@requires_artifact
def test_ambiguous_chest_pain_is_not_under_triaged():
    """Reassuring vitals, classic high-risk description — the under-triage trap."""
    decision = predictor.score(base_patient(
        age=34, heart_rate=82, resp_rate=16, systolic_bp=118, spo2=98, pain_score=7,
        chief_complaint="chest pain",
        symptom_text="Patient reports chest pain described as sudden onset, radiating to arm.",
    ))
    assert decision.final_priority <= 2


@requires_artifact
def test_decision_serialises_for_the_api_layer():
    payload = predictor.score(base_patient()).to_dict()
    for key in ("final_priority", "confidence_label", "risk_probability",
                "safety_rules_triggered", "model_version"):
        assert key in payload