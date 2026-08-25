"""The hybrid triage engine: XGBoost probability, deterministic safety rules,
and a confidence score, combined into one reviewable recommendation.

Composition order matters and is deliberate:
  1. the model proposes a priority from its probability
  2. safety rules may raise it, never lower it
  3. low confidence raises it one further tier
A clinician always sees the model-only priority alongside the final one, so an
escalation is never invisible.

No FastAPI, SimPy or database imports belong in this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any, Mapping, Sequence

import joblib
import numpy as np

from . import uncertainty
from .config import PRODUCTION_MODEL_PATH, ConfigError, load_config
from .feature_engineering import EngineeredBatch, engineer, model_input
from .safety_rules import SafetyFlag, apply_safety_rules, flag_names, priority_floor
from .config import DEFAULT_SAFETY_MODE


@dataclass
class TriageDecision:
    patient_id: str | None
    final_priority: int
    priority_label: str
    risk_probability: float
    ml_only_priority: int
    confidence_label: str
    uncertainty_score: float
    confidence_reasons: list[str]
    safety_rules_triggered: list[str]
    safety_rule_details: list[str]
    rule_priority_floor: int
    escalated_by_rules: bool
    escalated_by_uncertainty: bool
    risk_indicators: list[str]
    missing_fields: list[str]
    unknown_categories: list[str]
    model_version: str
    operating_threshold: float
    safety_mode: str

    @property
    def is_high_risk(self) -> bool:
        return self.final_priority <= 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache(maxsize=1)
def load_pipeline():
    """Load the production XGBoost pipeline. Cached for the process lifetime."""
    if not PRODUCTION_MODEL_PATH.exists():
        raise ConfigError(
            f"Production model not found at {PRODUCTION_MODEL_PATH}. "
            "Export it from the training notebook into risk_engine/artifacts/."
        )
    return joblib.load(PRODUCTION_MODEL_PATH)


def _ml_priority(probability: float) -> int:
    bands = load_config().priority_thresholds
    if probability >= bands["esi1"]:
        return 1
    if probability >= bands["high_risk"]:
        return 2
    if probability >= bands["esi3"]:
        return 3
    if probability >= bands["esi4"]:
        return 4
    return 5


def _risk_indicators(
    row: Mapping[str, Any],
    flags: Sequence[SafetyFlag],
    confidence: uncertainty.Confidence,
) -> list[str]:
    """Short, scannable reasons a clinician can read in a couple of seconds."""
    cfg = load_config()
    spo2_floor = cfg.norms_for(row["age_group"])["spo2"][0]
    indicators: list[str] = []

    if row["spo2"] < spo2_floor - 3:
        indicators.append(f"Low SpO2 ({row['spo2']:.0f}%)")
    if abs(row["hr_deviation"]) > 1.0:
        indicators.append(f"Abnormal heart rate ({row['heart_rate']:.0f} bpm)")
    if row["pain_score"] >= 7:
        indicators.append(f"High pain score ({row['pain_score']:.0f}/10)")
    if row["symptom_text_severity"] > 0.3:
        indicators.append("Symptom description flagged as high-severity language")
    if row["zero_history_flag"]:
        indicators.append("No prior medical history on file")

    indicators.extend(f"Safety rule: {flag.detail}" for flag in flags)

    if confidence.is_low:
        indicators.append("Borderline model confidence - clinician review recommended")

    return indicators or ["No major red flags identified"]


def _decide(
    row,
    probability: float,
    missing: Sequence[str],
    unknown: Sequence[str],
    safety_mode: str,
) -> TriageDecision:
    cfg = load_config()

    confidence = uncertainty.assess(
        probability=probability,
        threshold=cfg.operating_threshold,
        zero_history=bool(row["zero_history_flag"]),
        missing_fields=tuple(missing),
        unknown_categories=tuple(unknown),
    )

    ml_priority = _ml_priority(probability)
    flags = apply_safety_rules(row, missing_fields=missing, mode=safety_mode)
    floor = priority_floor(flags)

    priority = ml_priority
    if floor == 1:
        priority = 1
    elif floor == 2:
        priority = min(priority, 2)
    escalated_by_rules = priority < ml_priority

    escalated_by_uncertainty = False
    if confidence.is_low and priority >= 3:
        priority -= 1
        escalated_by_uncertainty = True

    priority = int(np.clip(priority, 1, 5))
        
    return TriageDecision(
        patient_id=row.get("patient_id"),
        final_priority=priority,
        priority_label=cfg.esi_labels[priority],
        risk_probability=round(float(probability), 3),
        ml_only_priority=ml_priority,
        confidence_label=confidence.label,
        uncertainty_score=confidence.score,
        confidence_reasons=confidence.reasons,
        safety_rules_triggered=flag_names(flags),
        safety_rule_details=[f.detail for f in flags],
        rule_priority_floor=floor,
        escalated_by_rules=escalated_by_rules,
        escalated_by_uncertainty=escalated_by_uncertainty,
        risk_indicators=_risk_indicators(row, flags, confidence),
        missing_fields=list(missing),
        unknown_categories=list(unknown),
        model_version=cfg.model_version,
        operating_threshold=cfg.operating_threshold,
        safety_mode=safety_mode,
    )


def score_batch(
    records: Sequence[Mapping[str, Any]],
    safety_mode: str = DEFAULT_SAFETY_MODE,
) -> list[TriageDecision]:
    """Score many patients in one pass. The simulation relies on this — scoring
    row by row at 3x surge volume is far too slow."""
    batch: EngineeredBatch = engineer(list(records))
    probabilities = load_pipeline().predict_proba(model_input(batch))[:, 1]

    return [
        _decide(
            batch.row(i),
            float(probabilities[i]),
            batch.missing_fields[i],
            batch.unknown_categories[i],
            safety_mode,
        )
        for i in range(len(batch))
    ]
         

def score(record: Mapping[str, Any], safety_mode: str = DEFAULT_SAFETY_MODE) -> TriageDecision:
    return score_batch([record], safety_mode=safety_mode)[0]