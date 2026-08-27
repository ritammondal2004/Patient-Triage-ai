#!/usr/bin/env python3
"""
Seed database with realistic demo data for PatientTriageAI.



Data flow:
  seed_data.py
        ↓
  app.core.config.get_settings()
        ↓
  load_dotenv() reads .env
        ↓
  database_url field from .env
        ↓
  Neon PostgreSQL (or your configured DB)
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path so we can import app modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models.orm import (
    Base, Hospital, Patient, Visit, VitalsRecord, TriageAssessment,
    ClinicianOverride, ConsentRecord, AuditEvent, SimulationRun
)


def get_database_session() -> Session:
    """
    Create SQLAlchemy session using DATABASE_URL from .env via app.core.config.
    
    The flow is:
      get_settings() 
        → reads from .env file (via load_dotenv() in config.py)
        → database_url field contains Neon connection string
        → create_engine() connects to Neon
    """
    settings = get_settings()
    
    print(f"📊 Connecting to database...")
    print(f"   Environment: {settings.environment}")
    print(f"   Database: {settings.database_url.split('/')[-1].split('?')[0]}")  # Extract db name
    print(f"   Host: {settings.database_url.split('@')[1].split('/')[0] if '@' in settings.database_url else 'localhost'}")
    
    # Create engine with connection string from .env
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    engine = create_engine(
        settings.database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return SessionLocal()


def seed_hospitals(session: Session):
    """Insert demo hospitals."""
    hospitals = [
        Hospital(
            name="Metro City General Hospital",
            city="Mumbai",
            capacity_doctors=8,
            capacity_beds=25,
            avg_daily_visits=450,
        ),
        Hospital(
            name="Rural District Medical Center",
            city="Pune",
            capacity_doctors=3,
            capacity_beds=8,
            avg_daily_visits=120,
        ),
        Hospital(
            name="Tertiary Care Medical Institute",
            city="Bangalore",
            capacity_doctors=12,
            capacity_beds=40,
            avg_daily_visits=800,
        ),
    ]
    
    for hospital in hospitals:
        try:
            session.add(hospital)
        except IntegrityError:
            session.rollback()
            print(f"   ⚠️  Hospital '{hospital.name}' already exists (skipped)")
            continue
    
    session.commit()
    print(f"✅ Seeded {len(hospitals)} hospitals")
    return session.query(Hospital).all()


def seed_patients(session: Session):
    """Insert demo patients with realistic prior histories."""
    patients = [
        Patient(
            patient_code="PT001",
            age=65,
            gender="M",
            has_prior_history=True,
            prior_conditions_count=3,
            prior_ed_visits=5,
            is_synthetic=False,
        ),
        Patient(
            patient_code="PT002",
            age=34,
            gender="F",
            has_prior_history=False,
            prior_conditions_count=0,
            prior_ed_visits=1,
            is_synthetic=False,
        ),
        Patient(
            patient_code="PT003",
            age=78,
            gender="M",
            has_prior_history=True,
            prior_conditions_count=4,
            prior_ed_visits=12,
            is_synthetic=False,
        ),
        Patient(
            patient_code="PT004",
            age=45,
            gender="F",
            has_prior_history=True,
            prior_conditions_count=2,
            prior_ed_visits=3,
            is_synthetic=False,
        ),
        Patient(
            patient_code="PT005",
            age=28,
            gender="M",
            has_prior_history=False,
            prior_conditions_count=0,
            prior_ed_visits=0,
            is_synthetic=True,  # Synthetic for simulation
        ),
    ]
    
    for patient in patients:
        try:
            session.add(patient)
        except IntegrityError:
            session.rollback()
            print(f"   ⚠️  Patient '{patient.patient_code}' already exists (skipped)")
            continue
    
    session.commit()
    print(f"✅ Seeded {len(patients)} patients")
    return session.query(Patient).all()


def seed_visits(session: Session, hospitals: list, patients: list):
    """Insert demo visits (ED encounters)."""
    now = datetime.now(timezone.utc)
    retention_until = now + timedelta(days=365)  # DPDP retention policy
    
    visits = [
        Visit(
            patient_id=patients[0].id,
            hospital_id=hospitals[0].id,
            chief_complaint="Chest pain",
            symptom_text="Acute onset substernal chest pain radiating to left arm",
            arrival_mode="ambulance",
            is_ambiguous_case=False,
            status="waiting",
            arrived_at=now - timedelta(hours=2),
            reference_esi_level=2,
            retention_until=retention_until,
        ),
        Visit(
            patient_id=patients[1].id,
            hospital_id=hospitals[0].id,
            chief_complaint="Fever and cough",
            symptom_text="High fever (39.5°C), productive cough, shortness of breath",
            arrival_mode="walk_in",
            is_ambiguous_case=False,
            status="in_treatment",
            arrived_at=now - timedelta(hours=1),
            treatment_started_at=now - timedelta(minutes=30),
            reference_esi_level=3,
            retention_until=retention_until,
        ),
        Visit(
            patient_id=patients[2].id,
            hospital_id=hospitals[1].id,
            chief_complaint="Fall and head injury",
            symptom_text="Fall from stairs, possible head trauma, loss of consciousness",
            arrival_mode="ambulance",
            is_ambiguous_case=False,
            status="in_treatment",
            arrived_at=now - timedelta(minutes=45),
            treatment_started_at=now - timedelta(minutes=40),
            reference_esi_level=2,
            retention_until=retention_until,
        ),
        Visit(
            patient_id=patients[3].id,
            hospital_id=hospitals[2].id,
            chief_complaint="Abdominal pain",
            symptom_text="Severe RUQ pain, nausea, vomiting",
            arrival_mode="walk_in",
            is_ambiguous_case=True,  # Ambiguous - could be multiple conditions
            status="waiting",
            arrived_at=now - timedelta(minutes=25),
            reference_esi_level=4,
            retention_until=retention_until,
        ),
    ]
    
    for visit in visits:
        try:
            session.add(visit)
        except IntegrityError:
            session.rollback()
            print(f"   ⚠️  Visit for patient {visit.patient_id} already exists (skipped)")
            continue
    
    session.commit()
    print(f"✅ Seeded {len(visits)} visits")
    return session.query(Visit).all()


def seed_vitals(session: Session, visits: list):
    """Insert vital signs records for visits."""
    now = datetime.now(timezone.utc)
    
    vitals_data = [
        # High-risk patient (chest pain)
        {
            "visit_id": visits[0].id,
            "heart_rate": 102,
            "resp_rate": 20,
            "systolic_bp": 165,
            "diastolic_bp": 98,
            "temperature_c": 36.8,
            "spo2": 95,
            "pain_score": 8,
            "recorded_at": now - timedelta(minutes=5),
        },
        # Fever patient
        {
            "visit_id": visits[1].id,
            "heart_rate": 118,
            "resp_rate": 24,
            "systolic_bp": 138,
            "diastolic_bp": 85,
            "temperature_c": 39.5,
            "spo2": 93,
            "pain_score": 4,
            "recorded_at": now - timedelta(minutes=20),
        },
        # Head injury patient
        {
            "visit_id": visits[2].id,
            "heart_rate": 95,
            "resp_rate": 18,
            "systolic_bp": 142,
            "diastolic_bp": 88,
            "temperature_c": 36.5,
            "spo2": 97,
            "pain_score": 7,
            "recorded_at": now - timedelta(minutes=40),
        },
        # Abdominal pain patient (missing one vital - simulating incomplete assessment)
        {
            "visit_id": visits[3].id,
            "heart_rate": 85,
            "resp_rate": 18,
            "systolic_bp": 128,
            "diastolic_bp": 78,
            "temperature_c": None,  # Missing temperature
            "spo2": 98,
            "pain_score": 6,
            "recorded_at": now - timedelta(minutes=10),
        },
    ]
    
    for vitals in vitals_data:
        vitals_record = VitalsRecord(
            visit_id=vitals["visit_id"],
            heart_rate=vitals["heart_rate"],
            resp_rate=vitals["resp_rate"],
            systolic_bp=vitals["systolic_bp"],
            diastolic_bp=vitals["diastolic_bp"],
            temperature_c=vitals["temperature_c"],
            spo2=vitals["spo2"],
            pain_score=vitals["pain_score"],
            recorded_at=vitals["recorded_at"],
        )
        session.add(vitals_record)
    
    session.commit()
    print(f"✅ Seeded {len(vitals_data)} vital signs records")
    return session.query(VitalsRecord).all()


def seed_triage_assessments(session: Session, visits: list, vitals: list):
    """Insert AI triage assessment results."""
    now = datetime.now(timezone.utc)
    
    assessments = [
        # High-risk: chest pain → Priority 2 (urgent)
        TriageAssessment(
            visit_id=visits[0].id,
            vitals_record_id=vitals[0].id,
            trigger="intake",
            final_priority=2,
            priority_label="Urgent",
            ml_only_priority=2,
            risk_probability=0.87,
            confidence_label="High",
            uncertainty_score=0.12,
            confidence_reasons=["Chest pain with cardiac risk factors", "Age 65", "Prior hypertension"],
            safety_rules_triggered=["CARDIAC_CHEST_PAIN", "HYPERTENSION_ALERT"],
            safety_rule_details=[
                {"rule": "CARDIAC_CHEST_PAIN", "reason": "Acute onset substernal pain with cardiac risk profile"},
                {"rule": "HYPERTENSION_ALERT", "reason": "Systolic BP 165 mmHg (elevated)"}
            ],
            rule_priority_floor=2,
            escalated_by_rules=True,
            model_version="xgboost-v1.2",
            operating_threshold=0.65,
            safety_mode="conservative",
        ),
      
        TriageAssessment(
            visit_id=visits[1].id,
            vitals_record_id=vitals[1].id,
            trigger="intake",
            final_priority=3,
            priority_label="Semi-urgent",
            ml_only_priority=4,
            risk_probability=0.62,
            confidence_label="Medium",
            uncertainty_score=0.28,
            confidence_reasons=["High fever with respiratory symptoms", "Tachycardia", "Mild hypoxia"],
            safety_rules_triggered=["FEVER_INFECTION_RISK"],
            safety_rule_details=[
                {"rule": "FEVER_INFECTION_RISK", "reason": "Temperature 39.5°C with cough and tachycardia"}
            ],
            rule_priority_floor=3,
            escalated_by_rules=True,
            model_version="xgboost-v1.2",
            operating_threshold=0.65,
            safety_mode="conservative",
        ),
        # Head injury → Priority 2 (urgent)
        TriageAssessment(
            visit_id=visits[2].id,
            vitals_record_id=vitals[2].id,
            trigger="intake",
            final_priority=2,
            priority_label="Urgent",
            ml_only_priority=2,
            risk_probability=0.78,
            confidence_label="High",
            uncertainty_score=0.15,
            confidence_reasons=["Head trauma with loss of consciousness", "Age 78 (falls risk)", "Neurological emergency"],
            safety_rules_triggered=["HEAD_TRAUMA", "NEURO_EMERGENCY"],
            safety_rule_details=[
                {"rule": "HEAD_TRAUMA", "reason": "Loss of consciousness following fall"},
                {"rule": "NEURO_EMERGENCY", "reason": "Potential intracranial injury"}
            ],
            rule_priority_floor=2,
            escalated_by_rules=True,
            model_version="xgboost-v1.2",
            operating_threshold=0.65,
            safety_mode="conservative",
        ),
        # Abdominal pain with missing vital → Priority 4 with uncertainty escalation
        TriageAssessment(
            visit_id=visits[3].id,
            vitals_record_id=vitals[3].id,
            trigger="intake",
            final_priority=3,  # Escalated from 4 due to uncertainty
            priority_label="Semi-urgent",
            ml_only_priority=4,
            risk_probability=0.51,
            confidence_label="Low",
            uncertainty_score=0.42,
            confidence_reasons=["Ambiguous abdominal pain", "Missing vital (temperature)"],
            missing_fields=["temperature"],
            safety_rules_triggered=[],
            safety_rule_details=[],
            rule_priority_floor=5,
            escalated_by_uncertainty=True,  # Escalated due to incomplete data
            model_version="xgboost-v1.2",
            operating_threshold=0.65,
            safety_mode="conservative",
        ),
    ]
    
    for assessment in assessments:
        session.add(assessment)
    
    session.commit()
    print(f"✅ Seeded {len(assessments)} triage assessments")
    return session.query(TriageAssessment).all()


def seed_clinician_overrides(session: Session, assessments: list):
    """Insert clinician override decisions (some agreed with AI, some overrode)."""
    now = datetime.now(timezone.utc)
    
    overrides = [
        # Clinician escalated the chest pain patient further
        ClinicianOverride(
            assessment_id=assessments[0].id,
            clinician_id="DR-2024-001",
            clinician_role="senior_physician",
            ai_priority=2,
            override_priority=1,  # Escalated to Critical
            direction="escalated",
            reason_code="ECG_ABNORMALITY",
            reason_text="12-lead ECG shows ST elevation, immediately escalated to cardiac cath lab",
            acknowledged_ai_recommendation=True,
        ),
        # Clinician agreed with fever assessment
        ClinicianOverride(
            assessment_id=assessments[1].id,
            clinician_id="NURSE-2024-045",
            clinician_role="triage_nurse",
            ai_priority=3,
            override_priority=3,  # No change
            direction="agreed",
            reason_code="ASSESSMENT_ACCEPTED",
            reason_text="Agreed with AI assessment; sent to respiratory isolation",
            acknowledged_ai_recommendation=True,
        ),
    ]
    
    for override in overrides:
        session.add(override)
    
    session.commit()
    print(f"✅ Seeded {len(overrides)} clinician overrides")


def seed_consent_records(session: Session, patients: list):
    """Insert DPDP consent records (purpose-limitation)."""
    now = datetime.now(timezone.utc)
    
    purposes = [
        "clinical_triage",
        "quality_audit",
        "research",
        "operational_analytics",
    ]
    
    consent_records = []
    for patient in patients[:3]:  # Seed for first 3 patients
        for purpose in purposes:
            consent_records.append(
                ConsentRecord(
                    patient_id=patient.id,
                    purpose=purpose,
                    granted=True,
                    notice_version="v1.0-prototype",
                    granted_at=now - timedelta(days=30),
                )
            )
    
    for record in consent_records:
        try:
            session.add(record)
        except IntegrityError:
            session.rollback()
            continue
    
    session.commit()
    print(f"✅ Seeded {len(consent_records)} consent records")


def seed_audit_events(session: Session, visits: list, assessments: list):
    """Insert tamper-evident audit trail records."""
    import hashlib
    import json
    
    now = datetime.now(timezone.utc)
    prev_hash = None
    
    audit_events = [
        {
            "event_type": "patient_registered",
            "entity_type": "patient",
            "entity_id": str(visits[0].patient_id),
            "actor": "registration_clerk",
            "purpose": "clinical_triage",
            "payload": {"patient_code": "PT001", "age": 65},
        },
        {
            "event_type": "visit_created",
            "entity_type": "visit",
            "entity_id": str(visits[0].id),
            "actor": "system",
            "purpose": "clinical_triage",
            "payload": {"chief_complaint": "Chest pain", "arrival_mode": "ambulance"},
        },
        {
            "event_type": "vitals_recorded",
            "entity_type": "vitals_record",
            "entity_id": str(visits[0].id),
            "actor": "nurse_intake",
            "purpose": "clinical_triage",
            "payload": {"heart_rate": 102, "systolic_bp": 165},
        },
        {
            "event_type": "triage_scored",
            "entity_type": "triage_assessment",
            "entity_id": str(assessments[0].id),
            "actor": "system",
            "purpose": "clinical_triage",
            "payload": {"priority": 2, "risk_probability": 0.87},
        },
    ]
    
    for event_data in audit_events:
        # Create hash chain for tamper detection
        event_hash = hashlib.sha256(
            f"{prev_hash}{json.dumps(event_data)}".encode()
        ).hexdigest()
        
        event = AuditEvent(
            event_type=event_data["event_type"],
            entity_type=event_data["entity_type"],
            entity_id=event_data["entity_id"],
            actor=event_data["actor"],
            purpose=event_data["purpose"],
            payload=event_data["payload"],
            prev_hash=prev_hash,
            event_hash=event_hash,
            created_at=now,
        )
        
        session.add(event)
        prev_hash = event_hash
    
    session.commit()
    print(f"✅ Seeded {len(audit_events)} audit events with hash chain")


def seed_simulation_runs(session: Session):
    """Insert demo simulation results."""
    now = datetime.now(timezone.utc)
    
    simulations = [
        SimulationRun(
            scenario="normal",
            arrival_multiplier=1.0,
            params={
                "simulation_hours": 24,
                "arrival_distribution": "poisson",
                "mean_arrivals_per_hour": 18,
            },
            metrics={
                "total_arrivals": 432,
                "total_treated": 428,
                "left_without_being_seen": 4,
                "mean_wait_minutes": 28.3,
                "p90_wait_minutes": 45.2,
                "escalations": 67,
            },
            created_at=now - timedelta(days=7),
        ),
        SimulationRun(
            scenario="surge_2x",
            arrival_multiplier=2.0,
            params={
                "simulation_hours": 8,
                "arrival_distribution": "poisson",
                "mean_arrivals_per_hour": 36,
            },
            metrics={
                "total_arrivals": 288,
                "total_treated": 276,
                "left_without_being_seen": 12,
                "mean_wait_minutes": 52.1,
                "p90_wait_minutes": 78.5,
                "escalations": 89,
            },
            created_at=now - timedelta(days=3),
        ),
    ]
    
    for sim in simulations:
        session.add(sim)
    
    session.commit()
    print(f"✅ Seeded {len(simulations)} simulation runs")


def main():
    """Main seeding orchestrator."""
    print("\n" + "=" * 70)
    print("  PatientTriageAI Database Seeding")
    print("=" * 70)
    print("  Database URL loaded from: .env file")
    print("  Flow: seed_data.py → app.core.config → .env → Neon PostgreSQL")
    print("=" * 70 + "\n")
    
    try:
        # Create session using DATABASE_URL from app.core.config
        session = get_database_session()
        
        print("✅ Database connection successful!\n")
        
        # Seed data in dependency order
        hospitals = seed_hospitals(session)
        patients = seed_patients(session)
        visits = seed_visits(session, hospitals, patients)
        vitals = seed_vitals(session, visits)
        assessments = seed_triage_assessments(session, visits, vitals)
        seed_clinician_overrides(session, assessments)
        seed_consent_records(session, patients)
        seed_audit_events(session, visits, assessments)
        seed_simulation_runs(session)
        
        session.close()
        
        print("\n" + "=" * 70)
        print("✅ Database seeding completed successfully!")
        print("=" * 70)
        print("\nYou can now run:")
        print("  • uvicorn app.main:app --reload")
        print("  • python -m pytest tests/ -v")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
