
"""Patient arrival process.

Interarrival times are exponential, but the rate is not constant: lambda(t) varies by
hour of day and is scaled by a surge multiplier. Sampling the gap using the rate at the
current instant is the piecewise-constant approximation to a non-homogeneous Poisson
process -- exact thinning would be stricter, but with hourly blocks the difference is
negligible and this stays readable.
      
Nights are the interesting case. Fewer people turn up at 03:00, but the ones who do are
far more likely to be genuinely sick, nobody walks in at 3am for a two-day-old rash.
So volume falls and acuity rises at the same time, which is exactly the combination that
strands a deteriorating patient behind a thin overnight roster.  
"""

import random
from collections import deque

from synthetic.generator import VOLATILE_COMPLAINTS, generate_patients

# Baseline mean arrival rate. 8.5/hour -> ~204 visits/day, a busy district ED.
BASE_ARRIVALS_PER_HOUR = 8.5

# Relative arrival intensity by hour of day (0-23). Normalised below so that
DIURNAL = (
    0.55, 0.45, 0.38, 0.32, 0.30, 0.35,   # 00:00 - 05:59  quiet 
    0.55, 0.80, 1.10, 1.35, 1.45, 1.40,   # 06:00 - 11:59 
    1.30, 1.20, 1.15, 1.15, 1.25, 1.40,   # 12:00 - 17:59  
    1.50, 1.45, 1.30, 1.10, 0.90, 0.70,   # 18:00 - 23:59  evening peak
)
_DIURNAL_MEAN = sum(DIURNAL) / 24.0

# Probability that a given arrival is a genuinely high-acuity patient, by hour.
ACUITY_BY_HOUR = (                                                                  
    0.40, 0.42, 0.44, 0.45, 0.44, 0.40,   # 00:00 - 05:59  low volume, high acuity       
    0.32, 0.26, 0.20, 0.17, 0.15, 0.14,   # 06:00 - 11:59  the walk-in crowd arrives       
    0.14, 0.14, 0.15, 0.15, 0.16, 0.17,   # 12:00 - 17:59                         
    0.19, 0.20, 0.23, 0.27, 0.32, 0.36,   # 18:00 - 23:59  acuity climbs again    
)                                                                           

DAY_HOURS = range(7, 19)  # 07:00-18:59 counts as day; the rest is night


def hour_of(minute: float) -> int:
    return int((minute // 60) % 24)


def is_night(minute: float) -> bool:
    return hour_of(minute) not in DAY_HOURS


class ArrivalPlan:
    """The rate schedule for one simulation run."""

    def __init__(self, base_per_hour: float = BASE_ARRIVALS_PER_HOUR, multiplier: float = 1.0,
                 use_diurnal: bool = True, use_night_acuity: bool = True,
                 seed: int = 42, id_prefix: str = "SIM"):
        self.base_per_hour = float(base_per_hour)
        self.multiplier = float(multiplier)
        self.use_diurnal = bool(use_diurnal)
        self.use_night_acuity = bool(use_night_acuity)
        self.seed = int(seed)
        self.id_prefix = id_prefix

    def rate_at(self, minute: float) -> float:
        """lambda in arrivals per hour at a given simulation minute."""
        rate = self.base_per_hour * self.multiplier
        if self.use_diurnal:
            rate *= DIURNAL[hour_of(minute)] / _DIURNAL_MEAN
        return max(rate, 0.01)

    def lambda_per_minute(self, minute: float)-> float:
        return self.rate_at(minute) / 60.0

    def high_acuity_probability(self, minute: float) ->float:
        """Chance the next arrival is drawn from the high-acuity sub-pool."""
        if not self.use_night_acuity:
            return 0.192  # the generator's own prevalence, i.e. no time-of-day effect 
        return ACUITY_BY_HOUR[hour_of(minute)]

    def expected_arrivals(self, horizon_minutes: float) -> int:
        """Integrate the rate over the horizon in one-hour blocks."""
        total = 0.0
        minute = 0.0
        while minute < horizon_minutes:
            block = min(60.0, horizon_minutes - minute)
            total += self.rate_at(minute) * (block / 60.0)
            minute += 60.0
        return max(int(total), 1)

    def describe(self) -> dict:
        return {
            "base_arrivals_per_hour": self.base_per_hour,
            "surge_multiplier": self.multiplier,
            "lambda_per_minute_mean": round(self.base_per_hour * self.multiplier / 60.0, 4),
            "peak_arrivals_per_hour": round(self.base_per_hour * self.multiplier
                                            * max(DIURNAL) / _DIURNAL_MEAN, 1),
            "trough_arrivals_per_hour": round(self.base_per_hour * self.multiplier
                                              * min(DIURNAL) / _DIURNAL_MEAN, 1),
            "diurnal": self.use_diurnal,
            "night_acuity": self.use_night_acuity,
        }


def interarrival_minutes(rng: random.Random, rate_per_hour: float) -> float:
    return rng.expovariate(max(rate_per_hour, 0.01) / 60.0)


def build_pool(size: int, seed: int, id_prefix: str = "SIM") -> list:
    """Pre-generate the cohort that will arrive.
    """
    return generate_patients(n=max(size, 1), seed=seed, id_prefix=id_prefix)
               
  
def split_by_acuity(pool: list) -> tuple[deque, deque]:
    """Two index queues: genuinely high-risk patients, and everyone else."""
    high, low = deque(), deque()
    for index, patient in enumerate(pool):
        if bool(getattr(patient, "reference_high_risk", False)):
            high.append(index)
        else:
            low.append(index)
    return high, low


def is_volatile(chief_complaint: str) -> bool:
    """Complaints where a patient can realistically deteriorate while waiting."""
    try:  
        return chief_complaint in VOLATILE_COMPLAINTS
    except Exception:
        return False  