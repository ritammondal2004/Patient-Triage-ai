
"""Turns raw ED intake data into the feature frame the trained pipeline expects.

The saved joblib pipeline only contains scaling and one-hot encoding. The
age-adjusted features below are NOT inside it, so this module has to reproduce
the notebook's add_age_adjusted_features() exactly or every prediction is wrong.
                
Missing vitals are imputed to the age-band midpoint so the pipeline can run,
but every imputed field is reported back so the safety layer and the confidence
score can react to it instead of silently trusting a made-up number.
"""      
                      
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .config import (
    KNOWN_ARRIVAL_MODES,
    KNOWN_CHIEF_COMPLAINTS,
    KNOWN_GENDERS,
    VITAL_NORM_KEYS,
    age_group_for,
    load_config,
)

SEVERE_KEYWORDS = (
    "crushing", "severe", "sudden onset", "uncontrolled", "loss of consciousness",
    "facial drooping", "slurred speech", "sudden weakness", "suicidal ideation",
    "throat tightness", "severe dehydration", "deep laceration", "deep cut",
    "sudden sharp pain", "sudden severe pain", "high fever", "fainting episode",
)
MILD_KEYWORDS = ("mild", "minor", "chronic", "persistent cough")

VITAL_FIELDS = ("heart_rate", "resp_rate", "systolic_bp", "diastolic_bp",
                "temperature_c", "spo2")

# Fields with no clinical age norm, imputed to a neutral value when absent.
_NEUTRAL_DEFAULTS = {
    "pain_score": 4.0,
    "prior_conditions_count": 0.0,
    "prior_ed_visits": 0.0,
}

      
@dataclass  
class EngineeredBatch:
    """Model-ready features plus the data-quality signals the engine needs."""
    frame: pd.DataFrame
    missing_fields: list[list[str]] = field(default_factory=list)
    unknown_categories: list[list[str]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.frame)

    def row(self, i: int) -> pd.Series:
        return self.frame.iloc[i]


def text_severity_score(text: Any) -> float:
    """Keyword-based severity of the free-text symptom description.

    Deliberately crude — it is a stand-in for clinical NLP, not a substitute.
    """
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return 0.0
    lowered = str(text).lower()
    score = 0.35 * sum(kw in lowered for kw in SEVERE_KEYWORDS)
    score -= 0.20 * sum(kw in lowered for kw in MILD_KEYWORDS)
    return float(np.clip(score, -0.3, 1.0))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(out) else out


def _deviation(value: float, bounds: tuple[float, float]) -> float:
    lo, hi = bounds
    mid, half_span = (lo + hi) / 2, (hi - lo) / 2
    return (value - mid) / half_span


def _prepare_record(record: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    cfg = load_config()

    age = _as_float(record.get("age"))
    if age is None:
        raise ValueError("'age' is required and cannot be imputed")

    group = record.get("age_group") or age_group_for(age)
    norms = cfg.norms_for(group)

    missing: list[str] = []
    unknown: list[str] = []
    values: dict[str, Any] = {"age": age, "age_group": group}

    for column in VITAL_FIELDS:
        supplied = _as_float(record.get(column))
        if supplied is None:
            missing.append(column)
            if column == "diastolic_bp":
                continue  # filled from systolic once that is resolved
            lo, hi = norms[VITAL_NORM_KEYS[column]]
            supplied = (lo + hi) / 2
        values[column] = supplied

    if "diastolic_bp" not in values:
        values["diastolic_bp"] = round(values["systolic_bp"] * 0.62, 1)

    values["spo2"] = float(np.clip(values["spo2"], 50.0, 100.0))

    for column, default in _NEUTRAL_DEFAULTS.items():
        supplied = _as_float(record.get(column))
        if supplied is None:
            missing.append(column)
            supplied = default
        values[column] = supplied

    has_history = record.get("has_prior_history")
    if has_history is None:
        has_history = bool(values["prior_conditions_count"] or values["prior_ed_visits"])
    values["has_prior_history"] = bool(has_history)

    symptom_text = record.get("symptom_text") or ""
    if not symptom_text:
        missing.append("symptom_text")
    values["symptom_text"] = str(symptom_text)

    # Unknown categories are silently dropped to all-zeros by the encoder, which
    # pushes risk *down*. We record them so confidence can be penalised instead.
    for column, allowed in (("chief_complaint", KNOWN_CHIEF_COMPLAINTS),
                            ("arrival_mode", KNOWN_ARRIVAL_MODES),
                            ("gender", KNOWN_GENDERS)):
        supplied = record.get(column)
        if supplied is None:
            missing.append(column)
            supplied = "unknown"
        elif supplied not in allowed:
            unknown.append(column)
        values[column] = str(supplied)

    # --- age-adjusted features (must match the notebook) ---
    values["hr_deviation"] = _deviation(values["heart_rate"], norms["hr"])
    values["rr_deviation"] = _deviation(values["resp_rate"], norms["rr"])
    values["sbp_deviation"] = _deviation(values["systolic_bp"], norms["sbp"])
    values["temp_deviation"] = _deviation(values["temperature_c"], norms["temp"])
    values["spo2_deficit"] = max(0.0, norms["spo2"][0] - values["spo2"])

    values["vital_abnormality_score"] = float(np.mean([
        abs(values["hr_deviation"]), abs(values["rr_deviation"]),
        abs(values["sbp_deviation"]), abs(values["temp_deviation"]),
    ]))
    values["symptom_text_severity"] = text_severity_score(values["symptom_text"])
    values["is_pediatric"] = int(group == "pediatric")
    values["is_geriatric"] = int(group == "geriatric")
    values["zero_history_flag"] = int(not values["has_prior_history"])

    if "patient_id" in record:
        values["patient_id"] = record["patient_id"]

    return values, missing, unknown


def engineer(records: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> EngineeredBatch:
    """Build the model input frame for one record or a batch of them."""
    if isinstance(records, Mapping):
        records = [records]
    if not records:
        raise ValueError("no records supplied")

    cfg = load_config()
    rows, missing, unknown = [], [], []
    for record in records:
        values, miss, unk = _prepare_record(record)
        rows.append(values)
        missing.append(miss)
        unknown.append(unk)

    frame = pd.DataFrame(rows)
    frame[list(cfg.numeric_features)] = frame[list(cfg.numeric_features)].astype(float)
    for column in cfg.categorical_features:
        frame[column] = frame[column].astype(str)

    ordered = cfg.feature_columns + [
        c for c in ("patient_id", "age_group", "symptom_text", "has_prior_history")
        if c in frame.columns
    ]
    return EngineeredBatch(frame=frame[ordered], missing_fields=missing,
                           unknown_categories=unknown)
         
        
def model_input(batch: EngineeredBatch) -> pd.DataFrame:
    """The exact columns the fitted pipeline was trained on."""
    return batch.frame[load_config().feature_columns]

