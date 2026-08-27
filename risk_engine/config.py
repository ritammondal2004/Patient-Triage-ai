"""Configuration for the risk engine.

Anything the trained artifact defines (feature columns, vital norms, operating
threshold) is read from artifacts/engine_config.json, which the training
notebook writes. Anything that is policy rather than model output (confidence
cut-offs, wait-time targets, safety aggressiveness) lives here.
"""
  
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

PACKAGE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = PACKAGE_DIR / "artifacts"
CHALLENGERS_DIR = ARTIFACTS_DIR / "challengers"
ENGINE_CONFIG_PATH = ARTIFACTS_DIR / "engine_config.json"
MODEL_CARD_PATH = ARTIFACTS_DIR / "model_card.json"
PRODUCTION_MODEL_PATH = ARTIFACTS_DIR / "pipeline_xgboost.joblib"

PEDIATRIC_MAX_AGE = 12
GERIATRIC_MIN_AGE = 65


AGE_GROUPS = ("pediatric", "adult", "geriatric")

UNCERTAINTY_MARGIN_SCALE = 0.30
ZERO_HISTORY_PENALTY = 0.05
INCOMPLETE_DATA_PENALTY = 0.15
HIGH_CONFIDENCE_MAX = 0.25
MEDIUM_CONFIDENCE_MAX = 0.55

# Target time to first assessment, in minutes, per priority level. 
MAX_WAIT_MINUTES = {1: 0, 2: 10, 3: 30, 4: 60, 5: 120}

DEFAULT_SAFETY_MODE = "conservative"

KNOWN_CHIEF_COMPLAINTS = (
    "chest pain", "difficulty breathing", "severe bleeding", "head injury",
    "stroke-like symptoms", "abdominal pain", "high fever", "laceration",
    "back pain", "dizziness", "allergic reaction", "fall / limb injury",
    "psychiatric distress", "sore throat / cold", "vomiting / diarrhea",
)
KNOWN_ARRIVAL_MODES = ("walk-in", "ambulance", "referred")
KNOWN_GENDERS = ("male", "female")


VITAL_NORM_KEYS = {
    "heart_rate": "hr",
    "resp_rate": "rr",
    "systolic_bp": "sbp",
    "temperature_c": "temp",
    "spo2": "spo2",
}

# Outer limits of survivable physiology, used to clamp sampled and simulated vitals.
VITAL_BOUNDS = {
    "heart_rate": (25.0, 220.0),
    "resp_rate": (4.0, 60.0),
    "systolic_bp": (50.0, 260.0),
    "diastolic_bp": (25.0, 160.0), 
    "temperature_c": (32.0, 42.5),
    "spo2": (70.0, 100.0),
    "pain_score": (0.0, 10.0),
}  
 
_FALLBACK_ESI_LABELS = {
    1: "CRITICAL", 2: "URGENT", 3: "STANDARD", 4: "LOW RISK", 5: "LOW RISK",
}


class ConfigError(RuntimeError):
    pass


def age_group_for(age: float) -> str:
    """Map an age onto a vital-norm band. The single source of truth for the cut-offs."""
    try:
        value = float(age)
    except (TypeError, ValueError):
        raise ValueError(f"age must be numeric, got {age!r}") from None
    if value < 0:
        raise ValueError(f"age must be non-negative, got {age}")
    if value <= PEDIATRIC_MAX_AGE:
        return "pediatric"
    if value >= GERIATRIC_MIN_AGE:
        return "geriatric"
    return "adult"


@dataclass(frozen=True)
class EngineConfig:
    production_model: str
    model_version: str
    operating_threshold: float
    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]
    target_column: str
    vital_norms: Mapping[str, Mapping[str, tuple[float, float]]]
    esi_labels: Mapping[int, str]
    priority_thresholds: Mapping[str, float]
    raw: Mapping[str, Any]

    @property
    def feature_columns(self) -> list[str]:
        return list(self.numeric_features) + list(self.categorical_features)

    def norms_for(self, age_group: str | int | float) -> Mapping[str, tuple[float, float]]:
        """Vital norms for an age band.
        """
        key = age_group
        if isinstance(key, str):
            key = key.strip().lower()
        else:
            try:
                key = age_group_for(key)
            except (TypeError, ValueError):
                raise ConfigError(
                    f"Cannot resolve an age group from '{age_group}'"
                ) from None
        try:
            return self.vital_norms[key]
        except KeyError:
            raise ConfigError(f"No vital norms for age group '{age_group}'") from None


@lru_cache(maxsize=1)
def load_config() -> EngineConfig:
    """Load and validate engine_config.json. Cached; call load_config.cache_clear()
    after swapping in a retrained artifact."""

    if not ENGINE_CONFIG_PATH.exists():
        raise ConfigError(
            f"engine_config.json not found at {ENGINE_CONFIG_PATH}. "
            "Copy the artifacts produced by the training notebook into risk_engine/artifacts/."
        )

    raw = json.loads(ENGINE_CONFIG_PATH.read_text())

    for key in ("operating_threshold", "feature_columns_numeric",
                "feature_columns_categorical", "vital_norms_by_age_group"):
        if key not in raw:
            raise ConfigError(f"engine_config.json is missing required key '{key}'")


    norms = {
        str(group).strip().lower(): {
            vital: (float(lo), float(hi)) for vital, (lo, hi) in vitals.items()
        }
        for group, vitals in raw["vital_norms_by_age_group"].items()
    }

    # age_group_for() can only return the three names in AGE_GROUPS, so a band missing
 
    missing = [group for group in AGE_GROUPS if group not in norms]
    if missing:
        raise ConfigError(
            f"vital_norms_by_age_group is missing band(s) {missing}; "
            f"found {sorted(norms)}. Re-export engine_config.json from the notebook."
        )

    labels = {int(k): v for k, v in raw.get("esi_labels", {}).items()} or _FALLBACK_ESI_LABELS

    threshold = float(raw["operating_threshold"])
    bands = {k: float(v) for k, v in raw.get("ml_priority_thresholds", {}).items()}
    bands.setdefault("esi1", 0.75)
    bands.setdefault("high_risk", threshold)
    bands.setdefault("esi3", 0.25)
    bands.setdefault("esi4", 0.12)

    # A threshold of exactly 0.5 means the notebook fell back to sklearn's default
    if threshold == 0.5:
        raise ConfigError(
            "operating_threshold is 0.5, which is the notebook's fallback value. "
            "Re-run threshold selection and re-export engine_config.json."
        )

    return EngineConfig(
        production_model=raw.get("production_model", "xgboost"),
        model_version=raw.get("model_version", "unknown"),
        operating_threshold=threshold,
        numeric_features=tuple(raw["feature_columns_numeric"]),
        categorical_features=tuple(raw["feature_columns_categorical"]),
        target_column=raw.get("target_column", "true_high_risk"),
        vital_norms=norms,
        esi_labels=labels,
        priority_thresholds=bands,
        raw=raw,
    )