
"""The discrete-event model.

Three process types: arrivals push patients into the queue, one process per doctor pulls
from it, and a monitor re-checks everyone still waiting. The monitor is the point of the
whole exercise, it is the thing a static triage system does not have.

Beds are held longer than the doctor is, so at high load the department can be blocked by
bed occupancy even when a doctor is technically free.
"""

import random
from dataclasses import dataclass

import simpy

from risk_engine import reassessment as policy
from simulation.arrivals import (
    ArrivalPlan,
    build_pool,
    hour_of,
    interarrival_minutes,
    is_night,
    is_volatile,
    split_by_acuity,
)
from simulation.queue import TriageQueue, WaitingPatient
from simulation.resources import (
    EDCapacity,
    UtilisationTracker,
    sample_bed_minutes,
    sample_treatment_minutes,
)

# How a deteriorating patient's vitals move per monitor tick. This is a modelled
# assumption, not something learned from data -- say so when presenting it.
DRIFT = {
    "spo2": (-4.0, -1.0),
    "systolic_bp": (-25.0, -6.0),
    "heart_rate": (6.0, 25.0),
    "resp_rate": (2.0, 8.0),
    "temperature_c": (0.3, 1.2),
    "pain_score": (1.0, 3.0),
}
FLOORS = {"spo2": 70.0, "systolic_bp": 60.0, "diastolic_bp": 35.0, "resp_rate": 8.0,
          "heart_rate": 40.0, "temperature_c": 35.0, "pain_score": 0.0}
CEILINGS = {"spo2": 100.0, "systolic_bp": 220.0, "diastolic_bp": 130.0, "resp_rate": 60.0,
            "heart_rate": 200.0, "temperature_c": 42.0, "pain_score": 10.0}
                      
VITALS_KEYS = ("heart_rate", "resp_rate", "systolic_bp", "diastolic_bp",
               "temperature_c", "spo2", "pain_score")


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(round((q / 100.0) * (len(ordered) - 1))), len(ordered) - 1)
    return round(ordered[index], 1)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


@dataclass
class SimConfig:
    horizon_hours: float = 24.0
    reassessment_enabled: bool = True
    monitor_interval: float = 10.0
    deterioration_rate: float = 0.10
    safety_mode: str | None = None
    seed: int = 42


class EDSimulation:
    def __init__(self, plan: ArrivalPlan, capacity: EDCapacity, config: SimConfig):
        self.plan = plan
        self.capacity = capacity
        self.config = config
        self.horizon = float(config.horizon_hours) * 60.0

        self.rng = random.Random(config.seed)
        self.env = simpy.Environment()
        self.queue = TriageQueue()
        self.work = simpy.Store(self.env)              # one token per waiting patient
        self.beds = simpy.Resource(self.env, capacity=capacity.beds)
        self.doctor_time = UtilisationTracker(capacity.doctors)
        self.bed_time = UtilisationTracker(capacity.beds)

        self.treated: list[WaitingPatient] = []
        self.pool: list = []
        self.decisions: list = []
        self.service_minutes: list[float] = []
        self.arrived = 0
        self.reassessments = 0
        self.deteriorations = 0
        self.scoring_errors = 0
        self.acuity_fallbacks = 0
        self.pool_exhausted = False

    # -- scoring
                                
    def _prescore(self) -> None:     
        """One batched predict_proba for the whole cohort's intake vitals."""
        from risk_engine.predictor import score, score_batch

        size = max(int(self.plan.expected_arrivals(self.horizon) * 1.8), 60)
        self.pool = build_pool(size, self.config.seed, self.plan.id_prefix)
        records = [p.as_record() for p in self.pool]

        try:
            self.decisions = list(score_batch(records, safety_mode=self.config.safety_mode))
        except Exception as exc:
            print(f"[warn] batch scoring unavailable ({exc}); falling back to per-patient")
            self.decisions = []
            for record in records:
                try:
                    self.decisions.append(score(record, safety_mode=self.config.safety_mode))
                except Exception:
                    self.decisions.append(None)
                    self.scoring_errors += 1

        self._high, self._low = split_by_acuity(self.pool)

    def _next_index(self, minute: float) -> int | None:
        """Pick the next arriving patient, biased by the hour's acuity profile."""
        want_high = self.rng.random() < self.plan.high_acuity_probability(minute)
        primary, secondary = (self._high, self._low) if want_high else (self._low, self._high)

        if primary:
            return primary.popleft()
        if secondary:
            self.acuity_fallbacks += 1     # sub-pool ran dry; visible, not silent
            return secondary.popleft()
        self.pool_exhausted = True
        return None

    def _rescore(self, entry: WaitingPatient) -> int | None:
        from risk_engine.predictor import score

        record = dict(entry.record)
        record.update(entry.vitals)
        try:
            decision = score(record, safety_mode=self.config.safety_mode)
            return int(getattr(decision, "final_priority", entry.priority))
        except Exception:
            self.scoring_errors += 1
            return None

    #  processes

    def _arrivals(self):
        while True:
            yield self.env.timeout(interarrival_minutes(self.rng, self.plan.rate_at(self.env.now)))
            index = self._next_index(self.env.now)
            if index is None:
                return  

            patient, decision = self.pool[index], self.decisions[index]
            if decision is None:
                continue

            record = patient.as_record()
            priority = int(getattr(decision, "final_priority", 3))
            entry = WaitingPatient(
                patient_id=str(record.get("patient_id", f"SIM-{index}")),
                age=int(record.get("age", 40)),
                chief_complaint=str(record.get("chief_complaint", "")),
                record=record,
                vitals={key: record.get(key) for key in VITALS_KEYS},
                arrival_minute=self.env.now,
                priority=priority,
                 intake_priority = priority,
                ml_only_priority=int(getattr(decision, "ml_only_priority", priority)),
                probability=float(getattr(decision, "risk_probability", 0.0)),
                confidence=str(getattr(decision, "confidence_label", "Medium")),
                reference_high_risk=bool(getattr(patient, "reference_high_risk", False)),
                reference_esi_level=int(getattr(patient, "reference_esi_level", 3)),
                last_assessment_minute=self.env.now,
            )
            self.arrived += 1
            self.queue.add(entry)
            yield self.work.put(1)

    def _doctor(self, doctor_id: int):
        while True:
            yield self.work.get()
            entry = self.queue.pop_next(self.env.now)
            if entry is None:
                continue

            treatment = sample_treatment_minutes(self.rng, entry.priority)
            bed_minutes = sample_bed_minutes(self.rng, entry.priority, treatment)

            with self.beds.request() as bed:
                yield bed
                entry.treatment_start_minute = self.env.now
                entry.treatment_priority = entry.priority
                yield self.env.timeout(treatment)          # doctor is occupied
                self.doctor_time.add(treatment)
                self.treated.append(entry)
                self.service_minutes.append(treatment)
                # Bed stays occupied after the doctor moves on.
                yield self.env.timeout(max(0.0, bed_minutes - treatment))
            self.bed_time.add(bed_minutes)

    def _monitor(self):
        """Re-check everyone still waiting: vitals drift, then the reassessment policy."""
        while True:
            yield self.env.timeout(self.config.monitor_interval)
            self.queue.sample_length()
            if not self.config.reassessment_enabled:
                continue

            for entry in list(self.queue.entries):
                previous = dict(entry.vitals)
                worsened = self._maybe_deteriorate(entry)

                signal = policy.evaluate(
                    priority=entry.priority,
                    waited_minutes=entry.waited(self.env.now),
                    age=entry.age,
                    previous_vitals=previous,
                    latest_vitals=entry.vitals,
                    minutes_since_last_assessment=self.env.now - entry.last_assessment_minute,
                )
                if not signal.due:
                    continue

                # A P1 is already at the ceiling; rescoring on wait alone changes nothing.
                if entry.priority == 1 and signal.trigger != "reassessment_vitals":
                    continue

                new_priority = self._rescore(entry)
                if new_priority is None:
                    continue
                self.reassessments += 1
                escalated = entry.apply_priority(new_priority, self.env.now,
                                                 signal.trigger or "wait")
                if escalated and worsened:
                    entry.escalated_after_deterioration = True

    def _maybe_deteriorate(self, entry: WaitingPatient) -> bool:
        """Truly sick patients deteriorate more often than stable ones."""
        chance = self.config.deterioration_rate * (2.0 if entry.reference_high_risk else 0.35)
        if not (is_volatile(entry.chief_complaint) or entry.reference_high_risk):
            chance *= 0.3
        if self.rng.random() > min(chance, 0.5):
            return False

        for field in self.rng.sample(list(DRIFT), k=self.rng.randint(2, 4)):
            current = entry.vitals.get(field)
            if current is None:
                continue
            low, high = DRIFT[field]
            moved = float(current) + self.rng.uniform(low, high)
            moved = max(FLOORS.get(field, moved), min(CEILINGS.get(field, moved), moved))
            entry.vitals[field] = round(moved, 1)

        entry.deteriorated = True
        self.deteriorations += 1
        return True

    # -------- run

    def run(self) -> dict:
        self._prescore()
        self.env.process(self._arrivals())
        self.env.process(self._monitor())
        for doctor_id in range(self.capacity.doctors):
            self.env.process(self._doctor(doctor_id))
        self.env.run(until=self.horizon)
        return self._metrics()

    def _daypart_stats(self, night: bool) -> dict:
        group = [e for e in self.treated
                 if is_night(e.arrival_minute) == night and e.treatment_start_minute is not None]
        if not group:
            return {"treated": 0}  
        waits = [e.treatment_start_minute - e.arrival_minute for e in group]
        high_risk = sum(1 for e in group if e.reference_high_risk)
        return {
            "treated": len(group),
            "high_risk_share": round(high_risk / len(group), 3),
            "mean_wait": _mean(waits),
            "p90_wait": _percentile(waits, 90),
            "mean_intake_priority": round(
                sum(e.intake_priority for e in group) / len(group), 2),
        }

    def _metrics(self) -> dict:
        waits = [e.treatment_start_minute - e.arrival_minute for e in self.treated
                 if e.treatment_start_minute is not None]

        by_priority: dict[str, dict] = {}
        for level in (1, 2, 3, 4, 5):
            group = [e for e in self.treated if e.intake_priority == level
                     and e.treatment_start_minute is not None]
            if not group:
                continue
            group_waits = [e.treatment_start_minute - e.arrival_minute for e in group]
            target = policy.max_wait_for(level)
            within = sum(1 for w in group_waits if w <= target)
            by_priority[str(level)] = {
                "treated": len(group),
                "mean_wait": _mean(group_waits),
                "p90_wait": _percentile(group_waits, 90),
                "target_minutes": target,
                "within_target_pct": round(100.0 * within / len(group), 1),
            }

        # The headline comparison: how many genuinely high-risk patients sat in a
        # low-priority slot at intake, versus were still in one when a doctor saw them.
        high_risk = [e for e in self.treated if e.reference_high_risk]
        under_intake = sum(1 for e in high_risk if e.intake_priority >= 3)
        under_treatment = sum(1 for e in high_risk if (e.treatment_priority or e.priority) >= 3)

        mean_service = _mean(self.service_minutes)
        effective_lambda = (self.arrived / max(self.config.horizon_hours, 0.01))
        rho = 0.0
        if mean_service:
            rho = round(effective_lambda / (60.0 / mean_service * self.capacity.doctors), 3)

        return {
            "scenario_params": {
                **self.plan.describe(),
                **self.capacity.describe(),
                "horizon_hours": self.config.horizon_hours,
                "reassessment_enabled": self.config.reassessment_enabled,
                "monitor_interval_minutes": self.config.monitor_interval,
                "deterioration_rate": self.config.deterioration_rate,
                "seed": self.config.seed,
            },
            "arrivals": self.arrived,
            "treated": len(self.treated),
            "still_waiting": len(self.queue),
            "arrivals_per_hour_observed": round(effective_lambda, 2),
            "mean_treatment_minutes": mean_service,
            "offered_load_rho": rho,
            "mean_wait_minutes": _mean(waits),
            "median_wait_minutes": _percentile(waits, 50),
            "p90_wait_minutes": _percentile(waits, 90),
            "max_wait_minutes": round(max(waits), 1) if waits else 0.0,
            "doctor_utilisation": self.doctor_time.utilisation(self.horizon),
            "bed_utilisation": self.bed_time.utilisation(self.horizon),
            "max_queue_length": self.queue.max_length,
            "mean_queue_length": self.queue.mean_length(),
            "by_priority": by_priority,
            "by_daypart": {"day": self._daypart_stats(False), "night": self._daypart_stats(True)},
            "deteriorations": self.deteriorations,
            "reassessments": self.reassessments,
            "escalations": sum(e.escalation_count for e in self.treated),
            "high_risk_treated": len(high_risk),
            "high_risk_low_priority_at_intake": under_intake,
            "high_risk_low_priority_at_treatment": under_treatment,
            "caught_by_reassessment": max(0, under_intake - under_treatment),
            "acuity_pool_fallbacks": self.acuity_fallbacks,
            "pool_exhausted": self.pool_exhausted,
            "scoring_errors": self.scoring_errors,
        }


def run_simulation(*, multiplier: float = 1.0, doctors: int = 4, beds: int = 12,
                   horizon_hours: float = 24.0, base_per_hour: float | None = None,
                   reassessment_enabled: bool = True, monitor_interval: float = 10.0,
                   deterioration_rate: float = 0.10, safety_mode: str | None = None,
                   seed: int = 42, use_diurnal: bool = True,
                   use_night_acuity: bool = True) -> dict:
    from simulation.arrivals import BASE_ARRIVALS_PER_HOUR

    plan = ArrivalPlan(
        base_per_hour=BASE_ARRIVALS_PER_HOUR if base_per_hour is None else base_per_hour,
        multiplier=multiplier, use_diurnal=use_diurnal,
        use_night_acuity=use_night_acuity, seed=seed,
    )
    config = SimConfig(horizon_hours=horizon_hours,
                       reassessment_enabled = reassessment_enabled,
                       monitor_interval = monitor_interval,
                       deterioration_rate = deterioration_rate,
                       safety_mode = safety_mode, seed=seed)
    return EDSimulation(plan, EDCapacity(doctors, beds), config).run()