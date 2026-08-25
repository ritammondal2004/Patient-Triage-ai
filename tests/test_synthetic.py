
import math

import pytest
      
from risk_engine.config import (
    GERIATRIC_MIN_AGE,
    KNOWN_ARRIVAL_MODES,
    KNOWN_CHIEF_COMPLAINTS,
    KNOWN_GENDERS,
    PEDIATRIC_MAX_AGE,
    PRODUCTION_MODEL_PATH,
)
from risk_engine.feature_engineering import engineer
from synthetic import (
    CHIEF_COMPLAINTS,
    ESI_CUTOFFS,
    acuity_mix,
    generate_patients,
    showcase_patients,
)
from synthetic.generator import config_esi_cutoffs

requires_artifact = pytest.mark.skipif(
    not PRODUCTION_MODEL_PATH.exists(),
    reason="production model artifact not present",
)


@pytest.fixture(scope="module")
def population():
    return generate_patients(n=4000, seed=7)


def test_generator_is_deterministic():
    a = generate_patients(n=25, seed=99)
    b = generate_patients(n=25, seed=99)
    assert [p.as_dict() for p in a] == [p.as_dict() for p in b]


def test_different_seeds_differ():
    a = generate_patients(n=50, seed=1)
    b = generate_patients(n=50, seed=2)
    assert [p.latent_severity for p in a] != [p.latent_severity for p in b]


def test_patient_ids_unique_and_offsettable():
    first = generate_patients(n=30, seed=3)
    second = generate_patients(n=30, seed=4, start_index=30)
    ids = [p.patient_id for p in first + second]
    assert len(set(ids)) == len(ids)


def test_acuity_mix_matches_calibration_target(population):
    mix = acuity_mix(population)
    assert 0.15 <= mix["high_risk"] <= 0.25
    assert 0.005 <= mix["esi1"] <= 0.05
    assert mix["esi3"] > mix["esi1"]


def test_all_five_esi_levels_are_produced(population):
    levels = {p.reference_esi_level for p in population}
    assert levels == {1, 2, 3, 4, 5}


def test_high_risk_flag_is_consistent(population):
    for p in population:
        assert p.reference_high_risk == int(p.reference_esi_level <= 2)


def test_roughly_half_have_no_prior_history(population):
    zero = sum(1 for p in population if not p.has_prior_history)
    assert 0.4 <= zero / len(population) <= 0.6


def test_zero_history_patients_have_no_counts(population):
    for p in population:
        if not p.has_prior_history:
            assert p.prior_conditions_count == 0 and p.prior_ed_visits == 0


def test_ambiguous_cases_are_present(population):
    assert sum(1 for p in population if p.is_ambiguous_case) >= 1


def test_age_bands_cover_their_boundaries(population):
    ages = {p.age for p in population}
    assert PEDIATRIC_MAX_AGE in ages, "age 12 must be reachable"
    assert GERIATRIC_MIN_AGE - 1 in ages, "age 64 must be reachable"
    assert all(0 <= p.age <= 95 for p in population)


def test_age_group_agrees_with_engine_banding(population):
    for p in population:
        if p.age <= PEDIATRIC_MAX_AGE:
            assert p.age_group == "pediatric"
        elif p.age >= GERIATRIC_MIN_AGE:
            assert p.age_group == "geriatric"
        else:
            assert p.age_group == "adult"


def test_vitals_are_physiologically_bounded(population):
    for p in population:
        assert 70 <= p.spo2 <= 100
        assert 0 <= p.pain_score <= 10
        assert p.heart_rate > 0 and p.resp_rate > 0 and p.systolic_bp > 0
        assert p.diastolic_bp < p.systolic_bp


def test_categoricals_stay_inside_the_engine_vocabulary(population):
    for p in population:
        assert p.chief_complaint in KNOWN_CHIEF_COMPLAINTS
        assert p.arrival_mode in KNOWN_ARRIVAL_MODES
        assert p.gender in KNOWN_GENDERS


def test_complaint_catalogue_matches_config():
    assert set(CHIEF_COMPLAINTS) == set(KNOWN_CHIEF_COMPLAINTS)


def test_records_feed_the_engine_without_gaps():
    records = [p.as_record() for p in generate_patients(n=200, seed=11)]
    batch = engineer(records)
    assert len(batch.frame) == 200
    assert not any(batch.missing_fields), "generator must not emit missing vitals"
    assert not any(batch.unknown_categories), "generator vocabulary drifted from config"


def test_records_carry_no_label_leakage():
    record = generate_patients(n=1, seed=5)[0].as_record()
    assert "reference_esi_level" not in record
    assert "reference_high_risk" not in record
    assert "latent_severity" not in record


def test_showcase_covers_the_required_edge_cases():
    cases = showcase_patients()
    assert len(cases) == 4
    assert any(c.is_ambiguous_case for c in cases)
    assert any(c.age_group == "pediatric" for c in cases)
    assert any(c.age_group == "geriatric" for c in cases)
    assert any(not c.has_prior_history for c in cases)
    assert all(c.note for c in cases)


def test_showcase_records_are_engine_ready():
    batch = engineer([c.as_record() for c in showcase_patients()])
    assert len(batch.frame) == 4
    assert not any(batch.missing_fields)


def test_esi_cutoffs_are_ordered():
    assert ESI_CUTOFFS[1] > ESI_CUTOFFS[2] > ESI_CUTOFFS[3] > ESI_CUTOFFS[4]


@requires_artifact
def test_esi_cutoffs_match_the_trained_artifact():
    saved = config_esi_cutoffs()
    if saved is None:
        pytest.skip("engine_config.json has no label_esi_cutoffs")
    assert saved == ESI_CUTOFFS, "generator drifted from the cutoffs used to train the model"


@requires_artifact
def test_every_generated_patient_gets_a_confidence_indicator():
    from risk_engine.predictor import score_batch

    records = [p.as_record() for p in generate_patients(n=60, seed=13)]
    for decision in score_batch(records):
        assert decision.confidence_label in {"High", "Medium", "Low"}
        assert 1 <= decision.final_priority <= 5


@requires_artifact
def test_geriatric_showcase_is_not_under_triaged():
    from risk_engine.predictor import score

    case = next(c for c in showcase_patients() if c.patient_id == "DEMO-GERIATRIC-1")
    decision = score(case.as_record())
    assert decision.final_priority <= 3, (
        "the geriatric demo case must not land in the lowest tiers -- its narrative "
        "claims extra caution is warranted"
    )