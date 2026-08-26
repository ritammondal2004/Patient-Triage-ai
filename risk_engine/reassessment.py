
"""Reassessment policy — when does a waiting patient need to be looked at again?

Pure functions, no framework and no clock: callers pass elapsed minutes. This lives in
risk_engine so the live API service and the SimPy loop share one definition of "overdue"
instead of drifting apart.

The problem statement requires two triggers: wait time exceeding the safe threshold for
the patient's severity, or vitals re-recorded as worsening.  
"""

from dataclasses import dataclass, field

from risk_engine.config import MAX_WAIT_MINUTES, load_config

# Minimum change in a vital before it counts as worsening. Signs are meaningful:
# negative means a drop is bad, positive means a rise is bad. 
WORSENING_DELTAS: dict[str, float] = {
    "spo2": -2.0,
    "systolic_bp": -15.0,
    "heart_rate": 15.0,
    "resp_rate": 4.0,
    "temperature_c": 0.8,
    "pain_score": 2.0,
}

READABLE = {
    "spo2": "SpO2",
    "systolic_bp": "systolic BP",
    "heart_rate": "heart rate",
    "resp_rate": "respiratory rate",
    "temperature_c": "temperature",
    "pain_score": "pain score",
}

# Vitals we compare against the age band to catch "was normal, now isn't".
BAND_CHECKED = {"spo2": "spo2", "heart_rate": "hr", "resp_rate": "rr", "systolic_bp": "sbp"}

# Guards against rescoring storms during a 3x surge run.
MIN_RESCORE_INTERVAL_MINUTES = 2.0


@dataclass
class ReassessmentSignal:
    due: bool
    trigger: str | None = None          # reassessment_vitals | reassessment_wait
    urgency: str = "routine"            # routine | immediate
    reasons: list[str] = field(default_factory=list)
    waited_minutes: float = 0.0
    max_wait_minutes: int = 0
    wait_breached: bool = False
    minutes_until_due: float = 0.0

    def to_dict(self) -> dict:
        return {
            "due": self.due,
            "trigger": self.trigger,
            "urgency": self.urgency,
            "reasons": list(self.reasons),
            "waited_minutes": round(self.waited_minutes, 1),
            "max_wait_minutes": self.max_wait_minutes,
            "wait_breached": self.wait_breached,
            "minutes_until_due": round(self.minutes_until_due, 1),
        }


def max_wait_for(priority: int | None) -> int:
    """Safe waiting target in minutes. Unknown priority is treated as the most urgent
    tier we still queue, because guessing low here would be the unsafe direction."""
    if priority is None:
        return MAX_WAIT_MINUTES.get(2, 10)
    return MAX_WAIT_MINUTES.get(int(priority), MAX_WAIT_MINUTES.get(3, 30))


def wait_breached(priority: int | None, waited_minutes: float) -> bool:
    limit = max_wait_for(priority)
    if waited_minutes is None:
        return False
    # P1's target is 0 minutes (immediate), so any measurable wait is already a breach.
    return waited_minutes > 0 if limit <= 0 else waited_minutes >= limit


def minutes_until_due(priority: int | None, waited_minutes: float) -> float:
    limit = max_wait_for(priority)
    return max(0.0, limit - (waited_minutes or 0.0))


def _out_of_band(field_name: str, value: float, norms: dict) -> bool:
    key = BAND_CHECKED.get(field_name)
    if key is None or value is None:
        return False
    bounds = norms.get(key)
    if not bounds:
        return False
    low, high = bounds
    return value < low or value > high


def vitals_worsened(
    previous: dict | None,
    latest: dict | None,
    age: int | None = None,
) -> list[str]:
    """Compare two vitals sets and describe every clinically meaningful deterioration.

    Only fields present in BOTH sets are compared — a newly recorded vital is not a
    change, and a vital that stopped being recorded is handled by the engine's
    missing-data path instead.
    """
    if not previous or not latest:
        return []

    norms = {}
    if age is not None:
        try:
            norms = load_config().norms_for(int(age))
        except Exception:
            norms = {}

    reasons: list[str] = []
    for field_name, threshold in WORSENING_DELTAS.items():
        old = previous.get(field_name)
        new = latest.get(field_name)
        if old is None or new is None:
            continue
        try:
            delta = float(new) - float(old)
        except (TypeError, ValueError):
            continue

        label = READABLE.get(field_name, field_name)
        worse = delta <= threshold if threshold < 0 else delta >= threshold
        if worse:
            direction = "fell" if delta < 0 else "rose"
            reasons.append(f"{label} {direction} from {old:g} to {new:g}")
        elif norms and _out_of_band(field_name, float(new), norms) and not _out_of_band(
            field_name, float(old), norms):
          
            reasons.append(f"{label} moved outside the age-band normal range ({new:g})")

    return reasons


def evaluate(
    *,
    priority: int | None,
    waited_minutes: float,
    age: int | None = None,
    previous_vitals: dict | None = None,
    latest_vitals: dict | None = None,
    minutes_since_last_assessment: float | None = None) -> ReassessmentSignal:
    """Decide whether this waiting patient is due for another look.
    """
    waited = float(waited_minutes or 0.0)
    limit = max_wait_for(priority)
    breached = wait_breached(priority, waited)

    worsening = vitals_worsened(previous_vitals, latest_vitals, age)

    signal = ReassessmentSignal(
        due=False,
        waited_minutes=waited,
        max_wait_minutes=limit,
        wait_breached=breached,
        minutes_until_due=minutes_until_due(priority, waited),
    )

    if worsening:
        signal.due = True
        signal.trigger = "reassessment_vitals"
        signal.urgency = "immediate"
        signal.reasons = ["Vitals re-recorded as worsening:"] + worsening
        return signal

    if breached:
        # Suppress a pure wait-based rescore if we just scored this patient; without
        # this a surge run would rescore P1/P2 patients on every single tick.
        if (
            minutes_since_last_assessment is not None
            and minutes_since_last_assessment < MIN_RESCORE_INTERVAL_MINUTES
        ):
            signal.reasons = ["Wait target exceeded, but reassessed moments ago"]
            return signal

        signal.due = True
        signal.trigger = "reassessment_wait"
        signal.urgency = "immediate" if (priority or 5) <= 2 else "routine"
        signal.reasons = [
            f"Waited {waited:.0f} min, exceeding the {limit} min safe target for priority "
            f"P{priority if priority else '?'}"
        ]
        return signal

    return signal   