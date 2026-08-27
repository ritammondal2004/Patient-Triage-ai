
"""Deterministic red-flag rules that sit alongside the model.

These can only ever escalate a patient, never downgrade one. Every rule is
named and carries a human-readable detail string so any escalation can be
explained to a clinician and reproduced in an audit.

Thresholds are illustrative prototype values, not validated clinical guidance.
"""
                   
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .config import DEFAULT_SAFETY_MODE, VITAL_NORM_KEYS, load_config
                                                     
SEVERITY_RANK = {"critical": 1, "urgent": 2}        
                                     
# Vitals whose absence should escalate rather than quietly disable a rule.
ESCALATING_MISSING_FIELDS = ("spo2", "heart_rate", "resp_rate", "systolic_bp")

STROKE_CUES = ("facial drooping", "slurred speech", "sudden weakness")
BLEEDING_CUES = ("uncontrolled bleeding", "deep laceration", "deep cut")
CHEST_PAIN_CUES = ("crushing", "radiating to arm", "sudden onset")

                            
@dataclass(frozen=True)
class SafetyFlag:
    name: str
    severity: str
    detail: str

    @property
    def rank(self) -> int:
        return SEVERITY_RANK[self.severity]


def _mode_params(mode: str) -> dict[str, float]:
    """Only the noisiest urgent rules are relaxed. Critical rules never move."""
    if mode == "balanced":
        return {"low_spo2_offset": 4.0, "extreme_pain_min": 10.0}
    if mode == "conservative":
        return {"low_spo2_offset": 3.0, "extreme_pain_min": 9.0}
    raise ValueError(f"unknown safety mode '{mode}'")


def apply_safety_rules(
    row: Mapping[str, Any],
    missing_fields: Sequence[str] = (),
    mode: str = DEFAULT_SAFETY_MODE,
) -> list[SafetyFlag]:
    cfg = load_config()
    params = _mode_params(mode)
    missing = set(missing_fields)
    norms = cfg.norms_for(row["age_group"])

    hr_lo, hr_hi = norms["hr"]
    rr_lo, rr_hi = norms["rr"]
    sbp_lo, _ = norms["sbp"]
    spo2_lo, _ = norms["spo2"]
             
    age = float(row["age"])
    hr = float(row["heart_rate"])
    rr = float(row["resp_rate"])
    sbp = float(row["systolic_bp"])
    temp = float(row["temperature_c"])
    spo2 = float(row["spo2"])
    pain = float(row["pain_score"])
    complaint = str(row["chief_complaint"])
    text = str(row.get("symptom_text", "")).lower()

    flags: list[SafetyFlag] = []

    def fire(name: str, severity: str, detail: str) -> None:
        flags.append(SafetyFlag(name, severity, detail))

    def available(*fields: str) -> bool:
        return not missing.intersection(fields)

    if available("spo2"):
        if spo2 <= spo2_lo - 6:
            fire("critical_low_spo2", "critical",
                 f"SpO2 {spo2:.0f}% is far below the {row['age_group']} floor of {spo2_lo:.0f}%")
        elif spo2 <= spo2_lo - params["low_spo2_offset"]:
            fire("low_spo2", "urgent",
                 f"SpO2 {spo2:.0f}% is below the {row['age_group']} floor of {spo2_lo:.0f}%")

    if available("systolic_bp") and sbp < sbp_lo - 20:
        fire("severe_hypotension", "critical",
             f"Systolic BP {sbp:.0f} mmHg against an age-band floor of {sbp_lo:.0f}")

    if available("heart_rate") and (hr > hr_hi * 1.4 or hr < hr_lo * 0.6):
        fire("extreme_heart_rate", "critical",
             f"Heart rate {hr:.0f} bpm is outside the {row['age_group']} range "
             f"{hr_lo:.0f}-{hr_hi:.0f}")

    if available("resp_rate") and (rr > rr_hi * 1.5 or rr < rr_lo * 0.5):
        fire("extreme_resp_rate", "critical",
             f"Respiratory rate {rr:.0f}/min is outside the {row['age_group']} range "
             f"{rr_lo:.0f}-{rr_hi:.0f}")

    if row["age_group"] == "pediatric" and age < 3 and temp >= 39.0:
        fire("high_fever_infant", "urgent",
             f"Temperature {temp:.1f} C in a child aged {age:.0f}")

    if complaint == "stroke-like symptoms" and any(cue in text for cue in STROKE_CUES):
        fire("stroke_red_flag", "critical", "Stroke cues present in the symptom description")

    if complaint == "severe bleeding" and any(cue in text for cue in BLEEDING_CUES):
        fire("severe_bleeding_red_flag", "critical", "Uncontrolled or deep bleeding described")

    if complaint == "difficulty breathing" and (
        (available("spo2") and spo2 <= spo2_lo - 3)
        or (available("resp_rate") and rr > rr_hi * 1.3)
        or "severe shortness of breath" in text): 
           
        fire("respiratory_distress", "critical",
             f"Breathing complaint with SpO2 {spo2:.0f}% and RR {rr:.0f}/min")

    if complaint == "chest pain" and any(cue in text for cue in CHEST_PAIN_CUES) and (
        hr > hr_hi * 1.2 or sbp < sbp_lo or spo2 <= spo2_lo-2 or pain >= 8):
        fire("chest_pain_red_flag", "urgent",
             "High-risk chest pain description with at least one supporting abnormality")
                  
    if complaint == "allergic reaction" and (
        "throat tightness" in text or "facial swelling" in text
        or (available("spo2") and spo2 <= spo2_lo - 3)
    ):
        fire("airway_allergic_reaction", "critical", "Possible airway involvement")

    if complaint == "psychiatric distress" and "suicidal ideation" in text:
        fire("suicidal_ideation", "critical", "Suicidal ideation reported at intake")

    if available("pain_score") and pain >= params["extreme_pain_min"]:
        fire("extreme_pain_score", "urgent", f"Reported pain {pain:.0f}/10")

    # Missing vitals must not silently disable the rules above, so an incomplete
    # intake escalates on its own. This is the PS's escalate-under-uncertainty
    # requirement applied to data quality rather than model output.  
    blocked = sorted(missing.intersection(ESCALATING_MISSING_FIELDS))
    if blocked:
        fire("incomplete_vitals_at_intake", "urgent",
             f"Not recorded at intake: {', '.join(blocked)}")

    return flags


def priority_floor(flags: Iterable[SafetyFlag]) -> int:
    """Most urgent level the fired rules demand. 5 means no rule fired."""
    ranks = [flag.rank for flag in flags]
    return min(ranks) if ranks else 5


def flag_names(flags: Iterable[SafetyFlag]) -> list[str]:
    return [flag.name for flag in flags]