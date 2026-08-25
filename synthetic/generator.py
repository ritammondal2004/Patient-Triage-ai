
"""Synthetic ED patient generator.
              
fetched from the risk-engine notebook so that seeded database records and simulated
arrivals follow the same distribution the production model was trained on. Vital norms
and the text-severity function are imported from risk_engine instead of copied, so the
two can never drift apart.
               
Labels produced here are SIMULATED triage decisions, not clinical ground truth. They
exist so the prototype can be evaluated end to end; they are never shown to a clinician
as a "correct answer". 
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

import numpy as np

from risk_engine.config import (
    ENGINE_CONFIG_PATH,
    GERIATRIC_MIN_AGE,
    PEDIATRIC_MAX_AGE,
    age_group_for,
    load_config,
)
from risk_engine.feature_engineering import text_severity_score

# Latent-severity cutoffs calibrated to a realistic ED acuity mix (high-risk ~20%,
# ESI-1 ~2%). Mirrored in engine_config.json as "label_esi_cutoffs" — the test suite
# cross-checks the two.
ESI_CUTOFFS = {1: 1.38, 2: 1.03, 3: 0.57, 4: 0.32}
                          
HIGH_RISK_ESI_MAX = 2  
           
# complaint -> (base severity weight 0-1, arrival share, text qualifiers)
CHIEF_COMPLAINTS: dict[str, tuple[float, float, list[str]]] = {
    "chest pain":         (0.85, 0.10, ["crushing", "sudden onset", "radiating to arm", "mild pressure"]),
    "difficulty breathing": (0.85, 0.09, ["severe shortness of breath", "wheezing", "mild breathlessness"]),
    "severe bleeding":     (0.90, 0.05, ["uncontrolled bleeding", "deep laceration"]),
    "head injury":          (0.70, 0.05, ["loss of consciousness", "minor bump", "confusion since injury"]),
    "stroke-like symptoms": (0.92, 0.04, ["facial drooping", "slurred speech", "sudden weakness one side"]),
    "abdominal pain":       (0.45, 0.10, ["severe cramping", "mild discomfort", "sudden sharp pain"]),
    "high fever":           (0.40, 0.08, ["persistent high fever", "mild fever", "fever with rash"]),
    "laceration":         (0.30, 0.08, ["deep cut", "minor cut"]),
    "back pain":            (0.20, 0.08, ["chronic ache", "sudden severe pain"]),
    "dizziness":            (0.35, 0.08, ["fainting episode", "mild lightheadedness"]),
    "allergic reaction":      (0.55, 0.05, ["facial swelling", "mild rash", "throat tightness"]),
    "fall / limb injury":   (0.35, 0.08, ["suspected fracture", "minor sprain"]),
    "psychiatric distress":  (0.50, 0.06, ["suicidal ideation", "acute anxiety episode"]),
    "sore throat / cold":   (0.10, 0.06, ["mild symptoms", "persistent cough"]),
    "vomiting / diarrhea":  (0.25, 0.06, ["severe dehydration signs", "mild nausea"]),
}                            
                               
# Complaints that occasionally deteriorate sharply regardless of presenting vitals.
VOLATILE_COMPLAINTS = (
    "stroke-like symptoms",
    "severe bleeding",
    "difficulty breathing",
    "chest pain",
    "allergic reaction",
)          

AGE_GROUPS = ("pediatric", "adult", "geriatric")
AGE_GROUP_SHARES = (0.15, 0.60, 0.25)
ARRIVAL_MODES = ("walk-in", "ambulance", "referred")
ARRIVAL_MODE_SHARES = (0.58, 0.27, 0.15)

# Raw fields the risk engine consumes. 
ENGINE_INPUT_FIELDS = (
    "age", "gender", "heart_rate", "resp_rate", "systolic_bp", "diastolic_bp",
    "temperature_c", "spo2", "pain_score", "chief_complaint", "symptom_text",
    "prior_conditions_count", "prior_ed_visits", "arrival_mode",
)


@dataclass
class SyntheticPatient:
    patient_id: str
    age: int  
    age_group: str
    gender: str
    heart_rate: float
    resp_rate: float
    systolic_bp: float
    diastolic_bp: float
    temperature_c: float
    spo2: float
    pain_score: int
    chief_complaint: str
    symptom_text: str
    has_prior_history: bool
    prior_conditions_count: int
    prior_ed_visits: int
    arrival_mode: str
    is_ambiguous_case: bool
    # Simulated reference labels — for evaluation only, never surfaced as truth.
    reference_esi_level: int
    reference_high_risk: int
    latent_severity: float
    note: str = ""

    def as_record(self) -> dict[str, Any]:
        """Engine-facing view: raw observations plus history, no labels."""
        record = {f: getattr(self, f) for f in ENGINE_INPUT_FIELDS}
        record["patient_id"] = self.patient_id
        record["has_prior_history"] = self.has_prior_history
        return record

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _complaint_distribution() -> tuple[list[str], np.ndarray]:
    names = list(CHIEF_COMPLAINTS)
    probs = np.array([CHIEF_COMPLAINTS[n][1] for n in names], dtype=float)
    return names, probs / probs.sum()


def _sample_age(age_group: str, rng: np.random.Generator) -> int:
    # Inclusive of the band boundaries — the notebook version could never produce
    # age 12 or 64, which left those ages outside every band.
    if age_group == "pediatric":
        return int(rng.integers(0, PEDIATRIC_MAX_AGE + 1))
    if age_group == "adult":
        return int(rng.integers(PEDIATRIC_MAX_AGE + 1, GERIATRIC_MIN_AGE))
    return int(rng.integers(GERIATRIC_MIN_AGE, 96))


def _sample_vital(
    norm_range: tuple[float, float],
    rng: np.random.Generator,
    abnormal_prob: float = 0.25,
    severe_abnormal_prob: float = 0.08,
) -> float:
    """Draw a vital: mostly in-band, sometimes mildly off, occasionally far off."""
    lo, hi = norm_range
    span = hi - lo
    r = rng.random()
    if r < severe_abnormal_prob:
        if rng.random() < 0.5:
            return lo - span * rng.uniform(1.2, 2.2)
        return hi + span * rng.uniform(0.8, 1.8)
    if r < abnormal_prob:
        if rng.random() < 0.5:
            return lo - span * rng.uniform(0.1, 0.4)
        return hi + span * rng.uniform(0.1, 0.4)
    return rng.uniform(lo, hi)


def _band_excess(value: float, norm_range: tuple[float, float]) -> float:
    """How far outside its normal band a vital sits, in band-widths."""
    lo, hi = norm_range
    width = max(hi - lo, 1)
    if value < lo:
        return (lo - value) / width
    if value > hi:
        return (value - hi) / width
    return 0.0


def _esi_from_severity(severity: float) -> int:
    for level in (1, 2, 3, 4):
        if severity >= ESI_CUTOFFS[level]:
            return level
    return 5


def _make_ambiguous(
    complaint: str,
    hr: float,
    spo2: float,
    norms: dict[str, tuple[float, float]],
    rng: np.random.Generator) -> tuple[str, str, float, float]: 
                              
    """Two ways a presentation goes ambiguous: worrying story with calm vitals, or
    a trivial-sounding story with vitals that are drifting."""  
                               
    if rng.random() < 0.5:      
        complaint = str(rng.choice(["chest pain", "dizziness", "abdominal pain"]))
        text = str(rng.choice([
            "Patient reports chest pain but symptoms are difficult to characterize.",
            "Patient reports dizziness with unclear onset and severity.",
            "Patient reports abdominal pain with unclear severity.",
        ]))
        hr = round(rng.uniform(*norms["hr"]), 0)
        spo2 = round(rng.uniform(norms["spo2"][0], 100), 0)
    else:
        complaint = str(rng.choice(["sore throat / cold", "back pain", "fall / limb injury"]))
        text = str(rng.choice([
            "Patient reports mild symptoms but appears uncomfortable.",
            "Patient reports chronic pain with sudden worsening.",
            "Patient reports a minor injury but symptoms are inconsistent.",
        ]))
        hr = float(np.clip(hr + rng.integers(20, 40), 40, 180))
        spo2 = float(np.clip(spo2 - rng.integers(2, 7), 75, 100))
    return complaint, text, hr, spo2


def generate_patients(
    n: int = 100,
    seed: int = 42,
    ambiguous_frac: float = 0.06,
    zero_history_frac: float = 0.5,
    id_prefix: str = "SIM",
    start_index: int = 0,
) -> list[SyntheticPatient]:
    """Generate n synthetic ED presentations.

    zero_history_frac defaults to 0.5 because the problem statement assumes roughly
    half of arrivals have no prior record. start_index lets a caller draw several
    batches (e.g. surge waves) without colliding patient IDs.
    """
    rng = np.random.default_rng(seed)
    cfg = load_config()
    complaint_names, complaint_probs = _complaint_distribution()
    patients: list[SyntheticPatient] = []

    for i in range(n):
        age_group = str(rng.choice(AGE_GROUPS, p=AGE_GROUP_SHARES))
        age = _sample_age(age_group, rng)
        norms = cfg.norms_for(age)
        gender = str(rng.choice(["male", "female"]))

        complaint = str(rng.choice(complaint_names, p=complaint_probs))
        base_weight, _, qualifiers = CHIEF_COMPLAINTS[complaint]
        qualifier = str(rng.choice(qualifiers))

        has_history = rng.random() > zero_history_frac
        prior_conditions = int(rng.poisson(1.2)) if has_history else 0
        prior_visits = int(rng.poisson(1.0)) if has_history else 0
        arrival_mode = str(rng.choice(ARRIVAL_MODES, p=ARRIVAL_MODE_SHARES))

        # Sicker patients get wider vital dispersion, so vitals and label stay coupled.
        severity = base_weight
        severity += 0.10 if arrival_mode == "ambulance" else 0.0
        severity += min(prior_conditions * 0.025, 0.10)
        severity += 0.04 if age < 2 or age >= 80 else 0.0

        hr = round(_sample_vital(norms["hr"], rng, 0.20 + 0.20 * severity, 0.04 + 0.08 * severity), 0)
        rr = round(_sample_vital(norms["rr"], rng, 0.18 + 0.18 * severity, 0.03 + 0.07 * severity), 0)
        sbp = round(_sample_vital(norms["sbp"], rng, 0.18 + 0.18 * severity, 0.03 + 0.07 * severity), 0)
        dbp = round(sbp * rng.uniform(0.55, 0.70), 0)
        temp = round(_sample_vital(norms["temp"], rng, 0.15 + 0.10 * severity, 0.02 + 0.05 * severity), 1)
        spo2 = round(float(np.clip(
            _sample_vital(norms["spo2"], rng, 0.15 + 0.25 * severity, 0.03 + 0.10 * severity), 70, 100)), 0)

        pain_score = int(np.clip(rng.normal(3.0 + 4.0 * base_weight, 2.0), 0, 10))
        symptom_text = f"Patient reports {complaint} described as {qualifier}."

        is_ambiguous = rng.random() < ambiguous_frac
        if is_ambiguous:
            complaint, symptom_text, hr, spo2 = _make_ambiguous(complaint, hr, spo2, norms, rng)
            base_weight = CHIEF_COMPLAINTS[complaint][0]

        text_sev = text_severity_score(symptom_text)

        vital_risk = float(np.mean([
            np.clip(_band_excess(hr, norms["hr"]), 0, 2),
            np.clip(_band_excess(rr, norms["rr"]), 0, 2),
            np.clip(_band_excess(sbp, norms["sbp"]), 0, 2),
            np.clip(_band_excess(temp, norms["temp"]), 0, 2),
            np.clip(max(0.0, (norms["spo2"][0] - spo2) / 8), 0, 2),
        ]))
        spo2_risk = float(np.clip(max(0.0, (norms["spo2"][0] - spo2) / 8), 0, 2))

        severity += 0.20 * np.clip(vital_risk, 0, 1)
        severity += 0.10 * np.clip(spo2_risk, 0, 1)
        severity += 0.08 * (pain_score / 10)
        severity += 0.07 * np.clip(text_sev + 0.25, 0, 1)
        severity += 0.08 if age < 2 or age >= 80 else 0.0
        severity += min(prior_conditions * 0.025, 0.10)

        if complaint in VOLATILE_COMPLAINTS and rng.random() < 0.35:
            severity += rng.uniform(0.08, 0.20)
        if is_ambiguous:
            severity += rng.normal(0, 0.15)

        severity += rng.normal(0, 0.10)
        severity = float(np.clip(severity, 0, 1.8))

        true_esi = _esi_from_severity(severity)

        # Simulated human triage noise: the recorded level is not always the latent one.
        observed = severity + rng.normal(0, 0.07)
        if rng.random() < 0.08:
            spread = 0.14 if true_esi == 1 else 0.10 if true_esi == 2 else 0.08
            observed += rng.uniform(-spread, spread)
        observed_esi = _esi_from_severity(observed)
        if rng.random() < 0.03:
            observed_esi = int(np.clip(observed_esi + rng.choice([-1, 1]), 1, 5))
                                                                 
        patients.append(SyntheticPatient(                         
            patient_id=f"{id_prefix}-{start_index + i:05d}",
            age=age,                          
            age_group=age_group_for(age),   
            gender=gender,              
            heart_rate=float(hr),  
            resp_rate=float(rr),
            systolic_bp=float(sbp),   
            diastolic_bp=float(dbp),
            temperature_c=float(temp),
            spo2=float(spo2),
            pain_score=pain_score,
            chief_complaint=complaint,
            symptom_text=symptom_text,
            has_prior_history=has_history,
            prior_conditions_count=prior_conditions,
            prior_ed_visits=prior_visits,
            arrival_mode=arrival_mode,
            is_ambiguous_case=is_ambiguous,
            reference_esi_level=observed_esi,
            reference_high_risk=int(observed_esi <= HIGH_RISK_ESI_MAX),
            latent_severity=round(severity, 4),
        ))

    return patients


def showcase_patients() -> list[SyntheticPatient]:
    """The edge cases the problem statement requires the demo to cover: one ambiguous
    presentation, one pediatric, one geriatric, and one zero-history patient."""
    specs = [
        dict(
            patient_id="DEMO-AMBIGUOUS-1", age=54, gender="male",
            heart_rate=88, resp_rate=18, systolic_bp=128, diastolic_bp=82,
            temperature_c=36.8, spo2=97, pain_score=7,
            chief_complaint="chest pain",
            symptom_text="Patient reports crushing chest pain with sudden onset radiating to arm.",
            has_prior_history=True, prior_conditions_count=1, prior_ed_visits=0,
            arrival_mode="walk-in", is_ambiguous_case=True,
            reference_esi_level=2,
            note="Vitals look reassuring, but the symptom description is classic high-risk "
                 "chest pain -- relying on vitals alone would under-triage this patient.",
        ),
        dict(
            patient_id="DEMO-PEDIATRIC-1", age=2, gender="female",
            heart_rate=165, resp_rate=42, systolic_bp=78, diastolic_bp=48,
            temperature_c=39.4, spo2=93, pain_score=5,
            chief_complaint="high fever",
            symptom_text="Patient reports high fever with severe shortness of breath.",
            has_prior_history=False, prior_conditions_count=0, prior_ed_visits=0,
            arrival_mode="ambulance", is_ambiguous_case=False,
            reference_esi_level=2,
            note="A HR of 165 and RR of 42 would be alarming in an adult but sit near the "
                 "danger edge -- not baseline -- for a 2-year-old. Age-adjusted norms matter.",
        ),
        dict(
            patient_id="DEMO-GERIATRIC-1", age=81, gender="female",
            heart_rate=96, resp_rate=22, systolic_bp=104, diastolic_bp=68,
            temperature_c=37.6, spo2=91, pain_score=3,
            chief_complaint="dizziness",
            symptom_text="Patient reports dizziness with a fainting episode.",
            has_prior_history=True, prior_conditions_count=3, prior_ed_visits=2,
            arrival_mode="walk-in", is_ambiguous_case=False,
            reference_esi_level=3,
            note="Mild-sounding complaint, but an 81-year-old with SpO2 91 and a low-normal "
                 "SBP of 104 warrants more caution than the same numbers in a healthy 30-year-old.",
        ),
        dict(
            patient_id="DEMO-ZEROHISTORY-1", age=45, gender="male",
            heart_rate=118, resp_rate=24, systolic_bp=96, diastolic_bp=60,
            temperature_c=38.9, spo2=94, pain_score=8,
            chief_complaint="abdominal pain",
            symptom_text="Patient reports abdominal pain described as severe cramping.",
            has_prior_history=False, prior_conditions_count=0, prior_ed_visits=0,
            arrival_mode="ambulance", is_ambiguous_case=False,
            reference_esi_level=2,
            note="First-time patient with no record on file -- the engine has nothing to lean "
                 "on except what is observed right now.",
        ),
    ]

    patients = []
    for spec in specs:   
        esi = spec.pop("reference_esi_level")
        patients.append(SyntheticPatient(
            age_group=age_group_for(spec["age"]),
            reference_esi_level=esi,
            reference_high_risk=int(esi <= HIGH_RISK_ESI_MAX),
            latent_severity=float("nan"),  # hand-authored, not sampled
            **spec,
        ))
    return patients


def acuity_mix(patients: Iterable[SyntheticPatient]) -> dict[str, float]:
    """Share of each reference ESI level plus overall high-risk prevalence."""
    items = list(patients)
    if not items:
        return {}
    counts = Counter(p.reference_esi_level for p in items)
    mix = {f"esi{level}": counts.get(level, 0) / len(items) for level in range(1, 6)}
    mix["high_risk"] = sum(p.reference_high_risk for p in items) / len(items)
    return mix


def config_esi_cutoffs() -> dict[int, float] | None:
    """Cutoffs recorded in engine_config.json at training time, if present."""
    if not ENGINE_CONFIG_PATH.exists():
        return None
    raw = json.loads(ENGINE_CONFIG_PATH.read_text()).get("label_esi_cutoffs")
    return {int(k): float(v) for k, v in raw.items()} if raw else None