"""Priority queue for the discrete-event ED simulation.

Patients are held in order of priority; the monitor walks the queue to check everyone
waiting and may escalate priorities. Pop returns the highest-priority waiting patient.
"""



from dataclasses import dataclass, field

VITALS_FIELDS = (
    "heart_rate", "resp_rate", "systolic_bp", "diastolic_bp",
    "temperature_c", "spo2", "pain_score",
)


@dataclass
class WaitingPatient:
    patient_id: str
    age: int
    chief_complaint: str
    record: dict
    vitals: dict
    arrival_minute: float
    priority: int
    intake_priority: int
    ml_only_priority: int
    probability: float
    confidence: str
    reference_high_risk: bool
    reference_esi_level: int
    last_assessment_minute: float = 0.0
    reassessment_count: int = 0
    escalation_count: int = 0
    deteriorated: bool = False
    escalated_after_deterioration: bool = False
    treatment_start_minute: float | None = None
    treatment_priority: int | None = None
    history: list = field(default_factory=list)

    def waited(self, now: float) -> float:
        return max(0.0, now - self.arrival_minute)

    def apply_priority(self, new_priority: int, now: float, trigger: str) -> bool:
        """Escalate-only. An automated rescore may never demote a waiting patient --
        the same asymmetry the safety layer enforces inside the engine."""
        new_priority = int(new_priority)
        changed = new_priority < self.priority
        if changed:
            self.escalation_count += 1
            self.priority = new_priority
        self.last_assessment_minute = now
        self.reassessment_count += 1
        self.history.append({"minute": round(now, 1), "trigger": trigger,
                             "priority": self.priority, "escalated": changed})
        return changed


class TriageQueue:
    def __init__(self):
        self.entries: list[WaitingPatient] = []
        self.max_length = 0
        self._length_samples: list[int] = []

    def add(self, entry: WaitingPatient) -> None:
        self.entries.append(entry)
        self.max_length = max(self.max_length, len(self.entries))

    def pop_next(self, now: float) -> WaitingPatient | None:
        """Highest acuity first, longest wait breaking the tie."""
        if not self.entries:
            return None
        self.entries.sort(key=lambda e: (e.priority, e.arrival_minute))
        return self.entries.pop(0)

    def sample_length(self) -> None:
        self._length_samples.append(len(self.entries))
        self.max_length = max(self.max_length, len(self.entries))

    def mean_length(self) -> float:
        if not self._length_samples:
            return 0.0
        return round(sum(self._length_samples) / len(self._length_samples), 2)

    def __len__(self) -> int:
        return len(self.entries) 