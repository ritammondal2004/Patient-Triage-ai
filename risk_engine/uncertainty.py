
"""Confidence scoring for a single risk probability.

Confidence is a decision-margin heuristic: the closer the probability sits to
the operating threshold, the less the model is actually committing to an answer.
It is not a calibrated credible interval and should not be presented as one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import (
    HIGH_CONFIDENCE_MAX,
    INCOMPLETE_DATA_PENALTY,
    MEDIUM_CONFIDENCE_MAX,
    UNCERTAINTY_MARGIN_SCALE,
    ZERO_HISTORY_PENALTY,
)
   

@dataclass(frozen=True)
class Confidence:
    score: float           # 0.0 = fully confident, 1.0 = no signal
    label: str             # High | Medium | Low  
    reasons: list[str] = field(default_factory=list)

    @property
    def is_low(self) -> bool:
        return self.label == "Low"


def label_for(uncertainty: float) -> str:
    if uncertainty<HIGH_CONFIDENCE_MAX:
        return "High"
    if uncertainty < MEDIUM_CONFIDENCE_MAX:
        return "Medium"
    return "Low" 
                   
   
def assess(
    probability: float,
    threshold:  float,  
    zero_history: bool = False,
    missing_fields: tuple[str, ...] | list[str] = (),
    unknown_categories: tuple[str, ...] | list[str] = (),
) -> Confidence:
    margin = abs(probability - threshold)
    score = float(np.clip(1.0 - (margin / UNCERTAINTY_MARGIN_SCALE), 0.0, 1.0))
                                 
    reasons: list[str] = []               
    if margin < UNCERTAINTY_MARGIN_SCALE / 2:
        reasons.append(                                 
            f"Risk probability {probability:.2f} sits close to the "
            f"{threshold:.2f} decision threshold"        
        )            
             
    if zero_history:
        score += ZERO_HISTORY_PENALTY
        reasons.append("No prior record on file")
                           
    if missing_fields:     
        score += INCOMPLETE_DATA_PENALTY
        reasons.append(f"Incomplete intake data: {', '.join(sorted(missing_fields))}")

    if unknown_categories:
        score += INCOMPLETE_DATA_PENALTY
        reasons.append(
            f"Unrecognised value for: {', '.join(sorted(unknown_categories))} "
            "(not seen during training)"
        )

    score = float(np.clip(score, 0.0, 1.0))
    return Confidence(score=round(score, 3), label=label_for(score), reasons=reasons) 
  