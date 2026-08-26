"""Doctors, beds and treatment-time sampling.

Treatment time is drawn in two stages, which is closer to how consultations actually
distribute than a single smooth curve: a random draw picks a band (quick / typical /
complex), then the minutes are uniform inside that band. A P4 laceration is almost always
a quick 6-10 minutes; a P1 resuscitation is rarely under 20.

Bands are physician contact minutes, not total length of stay -- the patient may stay in
a bed far longer, which is why beds are tracked separately.
"""

import random

# priority 1 is the most urgent, priority 5 is the least. The treatment bands are weighted to
TREATMENT_BINS = {
    1: ((0.20, 20.0, 30.0), (0.50, 30.0, 45.0), (0.30, 45.0, 70.0)),   # mean ~41 min
    2: ((0.30, 15.0, 22.0), (0.45, 22.0, 35.0), (0.25, 35.0, 55.0)),   # mean ~30 min
    3: ((0.40, 10.0, 15.0), (0.40, 15.0, 25.0), (0.20, 25.0, 38.0)),   # mean ~19 min
    4: ((0.50, 6.0, 10.0), (0.35, 10.0, 16.0), (0.15, 16.0, 25.0)),    # mean ~12 min
    5: ((0.65, 4.0, 7.0), (0.25, 7.0, 12.0), (0.10, 12.0, 18.0)),      # mean ~7 min  
}

# How long a bed stays occupied relative to physician contact time.
BED_OCCUPANCY_FACTOR = {1: 2.6, 2: 2.2, 3: 1.8, 4: 1.3, 5: 1.1}


class EDCapacity:
    def __init__(self, doctors: int = 4, beds: int = 12):
        self.doctors = max(int(doctors), 1)
        self.beds = max(int(beds), 1)

    def describe(self) -> dict:
        return {"doctors": self.doctors, "beds": self.beds}


def sample_treatment_minutes(rng: random.Random, priority: int) -> float:
    """Pick a band by random draw, then draw uniformly inside it."""
    bins = TREATMENT_BINS.get(int(priority), TREATMENT_BINS[3])
    draw = rng.random()
    cumulative = 0.0
    for weight, low, high in bins:
        cumulative += weight
        if draw <= cumulative:
            return round(rng.uniform(low, high), 1)
    weight, low, high = bins[-1]      # guards against probabilities summing under 1.0
    return round(rng.uniform(low, high), 1)


def sample_bed_minutes(rng: random.Random, priority: int, treatment_minutes: float) -> float:
    factor = BED_OCCUPANCY_FACTOR.get(int(priority), 1.6)
    return round(treatment_minutes * factor * rng.uniform(0.85, 1.15), 1)


def mean_treatment_minutes(priority: int) -> float:
    bins = TREATMENT_BINS.get(int(priority), TREATMENT_BINS[3])
    return round(sum(w * (low + high) / 2.0 for w, low, high in bins), 2)


def service_rate_per_hour(priority: int) -> float:
    """mu for one doctor treating only this priority. Useful for sanity-checking load."""
    mean = mean_treatment_minutes(priority)
    return round(60.0 / mean, 2) if mean else 0.0


class UtilisationTracker:
    """Accumulates busy time so utilisation is measured, not assumed."""

    def __init__(self, capacity: int):
        self.capacity = max(int(capacity), 1)
        self.busy_minutes = 0.0

    def add(self, minutes: float) -> None:
        self.busy_minutes += max(0.0, float(minutes))

    def utilisation(self, horizon_minutes: float) -> float:
        denominator = self.capacity * max(horizon_minutes, 1.0)
        return round(min(self.busy_minutes / denominator, 1.0), 3)  