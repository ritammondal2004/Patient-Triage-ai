
"""Pydantic request/response models — the API contract the frontend consumes.
                 
Nothing here computes clinical logic; these only validate shapes and ranges. Vitals are
all optional on purpose: a missing vital is a real intake condition, and the engine
treats it as a reason to escalate rather than something to reject at the door. 
"""       

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Priority = Literal[1, 2, 3, 4, 5]
SafetyMode = Literal["conservative", "balanced"]
VitalsSource = Literal["intake", "nurse_recheck", "monitor", "simulated"]
ArrivalMode = Literal["walk-in", "ambulance", "referred"]
AssessmentTrigger = Literal["intake", "reassessment_wait", "reassessment_vitals", "manual_rescore"]



class VitalsIn(BaseModel):
    """Ranges are physiological sanity bounds, not clinical thresholds."""

    heart_rate: float | None = Field(None, ge=20, le=300)
    resp_rate: float | None = Field(None, ge=4, le=80)
    systolic_bp: float | None = Field(None, ge=40, le=300)
    diastolic_bp: float | None = Field(None, ge=20, le=200)
    temperature_c: float | None = Field(None, ge=30, le=45)
    spo2: float | None = Field(None, ge=50, le=100)
    pain_score: int | None = Field(None, ge=0, le=10)
    source: VitalsSource = "intake"

          
    def recorded_fields(self) -> dict[str, float]:
        return {
            k: v for k, v in self.model_dump(exclude={"source"}).items() if v is not None
        }

    def has_any(self) -> bool:
        return bool(self.recorded_fields())


class PatientIn(BaseModel):
    patient_code: str | None = Field(None, max_length=40)
    age: int = Field(ge=0, le=120)
    gender: Literal["male", "female", "other"] = "other"
    has_prior_history: bool = False
    prior_conditions_count: int = Field(0, ge=0, le=30)
    prior_ed_visits: int = Field(0, ge=0, le=100)

    @model_validator(mode="after")
    def _sync_history_flag(self) -> "PatientIn":
        if self.prior_conditions_count or self.prior_ed_visits:
            self.has_prior_history = True
        return self


class VisitIntakeRequest(BaseModel):
    """One call registers the patient, opens the visit, records vitals and scores."""

    patient: PatientIn
    chief_complaint: str = Field(max_length=60)
    symptom_text: str = Field("", max_length=1000)
    arrival_mode: ArrivalMode = "walk-in"
    vitals: VitalsIn = Field(default_factory=VitalsIn)
    hospital_id: int | None = None
    is_ambiguous_case: bool = False
    reference_esi_level: Priority | None = None  # demo/eval only
    safety_mode: SafetyMode | None = None


class VitalsUpdateRequest(BaseModel):
    vitals: VitalsIn
    rescore: bool = True
    recorded_by: str = "nurse"


class OverrideRequest(BaseModel):
    clinician_id: str = Field(max_length=60)
    clinician_role: str = Field("triage_nurse", max_length=40)
    override_priority: Priority
    reason_code: str = Field(max_length=60)
         
    reason_text: str = Field(min_length=10, max_length=1000)
    acknowledged_ai_recommendation: bool = True


class SimulationRequest(BaseModel):
    scenario: str = Field("normal", max_length=40)
    hours: float = Field(8.0, gt=0, le=72)
    arrival_multiplier: float = Field(1.0, gt=0, le=10)
    doctors: int | None = Field(None, ge=1, le=50)
    beds: int | None = Field(None, ge=1, le=200)
    seed: int = 42
    persist: bool = True


# outputs

class ConfidenceOut(BaseModel):
    """Never optional anywhere a score is returned."""

    label: Literal["High", "Medium", "Low"]
    uncertainty_score: float
    reasons: list[str] = []


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    trigger: AssessmentTrigger
    final_priority: int
    priority_label: str
    ml_only_priority: int
    risk_probability: float
    confidence_label: str
    uncertainty_score: float
    confidence_reasons: list[str] = []
    safety_rules_triggered: list[str] = []
    safety_rule_details: list[Any] = []
    rule_priority_floor: int
    escalated_by_rules: bool
    escalated_by_uncertainty: bool
    risk_indicators: list[str] = []
    missing_fields: list[str] = []
    unknown_categories: list[Any] = []
    model_version: str
    operating_threshold: float
    safety_mode: str
    created_at: datetime


class VitalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime
    source: str
    heart_rate: float | None = None
    resp_rate: float | None = None
    systolic_bp: float | None = None
    diastolic_bp: float | None = None
    temperature_c: float | None = None
    spo2: float | None = None
    pain_score: int | None = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_code: str
    age: int
    gender: str
    has_prior_history: bool
    prior_conditions_count: int
    prior_ed_visits: int


class VisitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    hospital_id: int
    chief_complaint: str
    symptom_text: str
    arrival_mode: str
    status: str
    is_ambiguous_case: bool
    arrived_at: datetime
    treatment_started_at: datetime | None = None
    closed_at: datetime | None = None


class TriageResponse(BaseModel):
    """What the intake endpoint returns: the visit, the decision, and the vitals used."""

    visit: VisitOut
    patient: PatientOut
    assessment: AssessmentOut
    vitals: VitalsOut | None = None
    confidence: ConfidenceOut


class QueueEntryOut(BaseModel):
    visit_id: int
    patient_code: str
    age: int
    chief_complaint: str
    arrival_mode: str
    final_priority: int
    priority_label: str
    confidence_label: str
    risk_probability: float
    escalated_by_rules: bool
    escalated_by_uncertainty: bool
    safety_rules_triggered: list[str] = []
    arrived_at: datetime
    waited_minutes: float
    max_wait_minutes: int
    wait_breached: bool
    reassessment_due: bool
    reassessment_reasons: list[str] = []
    last_assessed_at: datetime | None = None
    override_applied: bool = False


class OverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    clinician_id: str
    clinician_role: str
    ai_priority: int
    override_priority: int
    direction: str
    reason_code: str
    reason_text: str
    acknowledged_ai_recommendation: bool
    created_at: datetime


class ReassessmentOut(BaseModel):
    visit_id: int
    due: bool
    trigger: AssessmentTrigger | None = None
    urgency: str = "routine"
    reasons: list[str] = []
    previous_priority: int | None = None
    new_priority: int | None = None
    assessment: AssessmentOut | None = None


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    entity_type: str
    entity_id: str
    actor: str
    purpose: str
    payload: dict = {}
    prev_hash: str | None = None
    event_hash: str
    created_at: datetime


class AuditChainStatus(BaseModel):
    events: int
    intact: bool
    first_broken_id: int | None = None


class SimulationResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    scenario: str
    arrival_multiplier: float
    params: dict = {}
    metrics: dict = {}
    created_at: datetime | None = None


class EngineInfoOut(BaseModel):
    """Shown in the UI footer so nobody mistakes this for validated clinical software."""
            
    model_version: str       
    production_model: str
    operating_threshold: float
    safety_mode: str
    jurisdiction: str
    status: str = "PROTOTYPE - NOT VALIDATED FOR CLINICAL USE"
    data_source: str = "100% synthetic data. No real patient data was used."