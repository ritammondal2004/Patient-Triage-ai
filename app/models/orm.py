
"""SQLAlchemy models — the authoritative schema.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey,
    Index, Integer,String,Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Kept as plain strings rather than DB enums — easier to extend in a prototype.
VISIT_STATUSES = ("waiting", "in_treatment", "discharged", "left_without_being_seen")
ASSESSMENT_TRIGGERS = ("intake", "reassessment_wait", "reassessment_vitals", "manual_rescore")
VITALS_SOURCES = ("intake", "nurse_recheck", "monitor", "simulated")
AUDIT_EVENT_TYPES = (
    "patient_registered", "visit_created", "vitals_recorded", "triage_scored",
    "reassessment_triggered", "clinician_override", "consent_granted",
    "consent_withdrawn", "simulation_run",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)  


class Hospital(Base):
    """Site entity — lets the same engine serve EDs of different sizes."""

    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str | None] = mapped_column(String(80))
    capacity_doctors: Mapped[int] = mapped_column(Integer, default=4)
    capacity_beds: Mapped[int] = mapped_column(Integer, default=12)
    avg_daily_visits: Mapped[int] = mapped_column(Integer, default=300)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    visits: Mapped[list["Visit"]] = relationship(back_populates="hospital")


class Patient(Base):
    """Person-level record. Stable across visits; carries prior-history counts."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(20))
    has_prior_history: Mapped[bool] = mapped_column(Boolean, default=False)
    prior_conditions_count: Mapped[int] = mapped_column(Integer, default=0)
    prior_ed_visits: Mapped[int] = mapped_column(Integer, default=0)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    visits: Mapped[list["Visit"]] = relationship(back_populates="patient")
    consents: Mapped[list["ConsentRecord"]] = relationship(back_populates="patient")


class Visit(Base):
    """One ED encounter. This is the unit the queue and the simulation operate on."""

    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)

    chief_complaint: Mapped[str] = mapped_column(String(60))
    symptom_text: Mapped[str] = mapped_column(Text, default="")
    arrival_mode: Mapped[str] = mapped_column(String(30))
    is_ambiguous_case: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(30), default="waiting")
    arrived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    treatment_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Simulated reference label — evaluation only, never shown as ground truth.
    reference_esi_level: Mapped[int | None] = mapped_column(Integer)

    # DPDP retention: stamped at creation, drives the purge job.
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped["Patient"] = relationship(back_populates="visits")
    hospital: Mapped["Hospital"] = relationship(back_populates="visits")
    vitals: Mapped[list["VitalsRecord"]] = relationship(
        back_populates="visit", order_by="VitalsRecord.recorded_at"
    )
    assessments: Mapped[list["TriageAssessment"]] = relationship(
        back_populates="visit", order_by="TriageAssessment.created_at"
    )

    __table_args__ = (Index("ix_visits_status_arrived", "status", "arrived_at"),)


class VitalsRecord(Base):
    """A single set of observations at a point in time. Multiple rows per visit is the
    whole point — comparing the latest to the previous is how worsening is detected."""

    __tablename__ = "vitals_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    source: Mapped[str] = mapped_column(String(30), default="intake")

    # Nullable on purpose: missing vitals must be representable, because the engine
    # treats incomplete data as a reason to escalate rather than something to hide.
    heart_rate: Mapped[float | None] = mapped_column(Float)  
    resp_rate: Mapped[float | None] = mapped_column(Float)
    systolic_bp: Mapped[float | None] = mapped_column(Float)
    diastolic_bp: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    spo2: Mapped[float | None] = mapped_column(Float)
    pain_score: Mapped[int | None] = mapped_column(Integer)

    visit: Mapped["Visit"] = relationship(back_populates="vitals")


class TriageAssessment(Base):
    """One scoring event. Stores the full engine decision so the UI and the audit trail
    can show exactly what the clinician saw, including why it was escalated."""

    __tablename__ = "triage_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    vitals_record_id: Mapped[int | None] = mapped_column(ForeignKey("vitals_records.id"))
    trigger: Mapped[str] = mapped_column(String(30), default="intake")

    final_priority: Mapped[int] = mapped_column(Integer, index=True)
    priority_label: Mapped[str] = mapped_column(String(30))
    ml_only_priority: Mapped[int] = mapped_column(Integer)
    risk_probability: Mapped[float] = mapped_column(Float)

    # Never nullable: the PS forbids returning a score without a confidence indicator.
    confidence_label: Mapped[str] = mapped_column(String(10))
    uncertainty_score: Mapped[float] = mapped_column(Float)
    confidence_reasons: Mapped[list] = mapped_column(JSON, default=list)

    safety_rules_triggered: Mapped[list] = mapped_column(JSON, default=list)
    safety_rule_details: Mapped[list] = mapped_column(JSON, default=list)
    rule_priority_floor: Mapped[int] = mapped_column(Integer, default=5)
    escalated_by_rules: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_by_uncertainty: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_indicators: Mapped[list] = mapped_column(JSON, default=list)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    unknown_categories: Mapped[list] = mapped_column(JSON, default=list)

    model_version: Mapped[str] = mapped_column(String(40))
    operating_threshold: Mapped[float] = mapped_column(Float)
    safety_mode: Mapped[str] = mapped_column(String(20), default="conservative")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    visit: Mapped["Visit"] = relationship(back_populates="assessments")
    override: Mapped["ClinicianOverride | None"] = relationship(back_populates="assessment")

    __table_args__ = (Index("ix_assessment_visit_created", "visit_id", "created_at"),)


class ClinicianOverride(Base):
    """The clinician's final say. Under DPDP this is the legally meaningful."""

    __tablename__ = "clinician_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("triage_assessments.id"), unique=True)
    clinician_id: Mapped[str] = mapped_column(String(60))
    clinician_role: Mapped[str] = mapped_column(String(40), default="triage_nurse")

    ai_priority: Mapped[int] = mapped_column(Integer)
    override_priority: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(20))  # escalated | de-escalated
    reason_code: Mapped[str] = mapped_column(String(60))
    reason_text: Mapped[str] = mapped_column(Text)
    acknowledged_ai_recommendation: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    assessment: Mapped["TriageAssessment"] = relationship(back_populates="override")


class ConsentRecord(Base):
    """DPDP purpose-limitation record: consent is per purpose and can be withdrawn."""

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(80))  # e.g. clinical_triage, quality_audit
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    notice_version: Mapped[str] = mapped_column(String(20), default="v1.0-prototype")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped["Patient"] = relationship(back_populates="consents")


class AuditEvent(Base):
    """Append-only audit trail. Never updated or deleted by application code.

    prev_hash/event_hash chain each event to the one before it, so a deleted or edited
    row breaks the chain and is detectable — cheap tamper-evidence for the demo.
    """   

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(60))
    actor: Mapped[str] = mapped_column(String(60), default="system")
    purpose: Mapped[str] = mapped_column(String(80), default="clinical_triage")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class SimulationRun(Base):
    """Persisted simulation results so the surge comparison survives a page refresh."""

    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario: Mapped[str] = mapped_column(String(40))  # normal | surge_3x | ...
    arrival_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)