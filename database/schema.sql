-- PatientTriageAI Database Schema

--
CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    city VARCHAR(80),
    capacity_doctors INTEGER NOT NULL DEFAULT 4,
    capacity_beds INTEGER NOT NULL DEFAULT 12,
    avg_daily_visits INTEGER NOT NULL DEFAULT 300,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE hospitals IS 'Emergency Department facility master data';
COMMENT ON COLUMN hospitals.name IS 'Unique hospital identifier';
COMMENT ON COLUMN hospitals.capacity_doctors IS 'Number of doctors available';
COMMENT ON COLUMN hospitals.capacity_beds IS 'Number of beds in ED';
COMMENT ON COLUMN hospitals.avg_daily_visits IS 'Expected daily patient volume';


-- ============================================================================
-- TABLE 2: patients
-- ============================================================================
-- Person-level record. Stable across multiple ED visits.
-- Carries prior history counts for risk assessment context.
--
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    patient_code VARCHAR(40) NOT NULL UNIQUE,
    age INTEGER NOT NULL,
    gender VARCHAR(20) NOT NULL,
    has_prior_history BOOLEAN NOT NULL DEFAULT FALSE,
    prior_conditions_count INTEGER NOT NULL DEFAULT 0,
    prior_ed_visits INTEGER NOT NULL DEFAULT 0,
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_patients_code ON patients(patient_code);
COMMENT ON TABLE patients IS 'Person-level record, stable across visits';
COMMENT ON COLUMN patients.patient_code IS 'Unique patient identifier';
COMMENT ON COLUMN patients.has_prior_history IS 'Flag: patient has chronic conditions/prior complications';
COMMENT ON COLUMN patients.prior_conditions_count IS 'Number of documented chronic conditions';
COMMENT ON COLUMN patients.prior_ed_visits IS 'Historical ED visits count';
COMMENT ON COLUMN patients.is_synthetic IS 'TRUE if generated for simulation/testing';


-- ============================================================================
-- TABLE 3: visits
-- ============================================================================
-- One ED encounter. This is the unit the queue and simulation operate on.
-- Links patient to hospital and tracks visit lifecycle.
--
-- Status values: 'waiting', 'in_treatment', 'discharged', 'left_without_being_seen'
-- Arrival modes: 'ambulance', 'self-arrived', 'walk-in', etc.
--
CREATE TABLE visits (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE RESTRICT,
    
    chief_complaint VARCHAR(60) NOT NULL,
    symptom_text TEXT NOT NULL DEFAULT '',
    arrival_mode VARCHAR(30) NOT NULL,
    is_ambiguous_case BOOLEAN NOT NULL DEFAULT FALSE,
    
    status VARCHAR(30) NOT NULL DEFAULT 'waiting',
    arrived_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    treatment_started_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE,
    
    reference_esi_level INTEGER,
    retention_until TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_visits_patient ON visits(patient_id);
CREATE INDEX idx_visits_hospital ON visits(hospital_id);
CREATE INDEX idx_visits_status_arrived ON visits(status, arrived_at);

COMMENT ON TABLE visits IS 'One ED encounter; unit of queue and simulation operations';
COMMENT ON COLUMN visits.chief_complaint IS 'Primary presenting symptom';
COMMENT ON COLUMN visits.is_ambiguous_case IS 'Flag: case requires manual review';
COMMENT ON COLUMN visits.status IS 'Current stage: waiting | in_treatment | discharged | left_without_being_seen';
COMMENT ON COLUMN visits.reference_esi_level IS 'Ground truth ESI level (evaluation only, hidden from clinician)';
COMMENT ON COLUMN visits.retention_until IS 'DPDP Act 2023 retention deadline; drive purge jobs';


-- ============================================================================
-- TABLE 4: vitals_records
-- ============================================================================
-- Vital signs observations at a point in time.
-- Multiple rows per visit; latest vs previous is how deterioration is detected.
--
-- Nullable by design: missing vitals MUST be representable because the engine
-- escalates on incomplete data rather than silently skipping.
--
-- Source values: 'intake', 'nurse_recheck', 'monitor', 'simulated'
--
CREATE TABLE vitals_records (
    id SERIAL PRIMARY KEY,
    visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(30) NOT NULL DEFAULT 'intake',
    
    heart_rate FLOAT,
    resp_rate FLOAT,
    systolic_bp FLOAT,
    diastolic_bp FLOAT,
    temperature_c FLOAT,
    spo2 FLOAT,
    pain_score INTEGER
);

CREATE INDEX idx_vitals_visit ON vitals_records(visit_id);
CREATE INDEX idx_vitals_recorded ON vitals_records(recorded_at);

COMMENT ON TABLE vitals_records IS 'Vital signs observations; multiple per visit track deterioration';
COMMENT ON COLUMN vitals_records.source IS 'Origin: intake | nurse_recheck | monitor | simulated';
COMMENT ON COLUMN vitals_records.heart_rate IS 'BPM; nullable if not recorded';
COMMENT ON COLUMN vitals_records.resp_rate IS 'Breaths per minute; nullable if not recorded';
COMMENT ON COLUMN vitals_records.systolic_bp IS 'mmHg; nullable if not recorded';
COMMENT ON COLUMN vitals_records.spo2 IS 'O2 saturation percentage; nullable if not recorded';


-- ============================================================================
-- TABLE 5: triage_assessments
-- ============================================================================
-- One triage scoring event. Stores complete AI decision for audit trail.
-- Shows exactly what the clinician saw and why it was escalated.

CREATE TABLE triage_assessments (
    id SERIAL PRIMARY KEY,
    visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    vitals_record_id INTEGER REFERENCES vitals_records(id) ON DELETE SET NULL,
    trigger VARCHAR(30) NOT NULL DEFAULT 'intake',
    
    final_priority INTEGER NOT NULL,
    priority_label VARCHAR(30) NOT NULL,
    ml_only_priority INTEGER NOT NULL,
    risk_probability FLOAT NOT NULL,
    
    confidence_label VARCHAR(10) NOT NULL,
    uncertainty_score FLOAT NOT NULL,
    confidence_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    safety_rules_triggered JSONB NOT NULL DEFAULT '[]'::jsonb,
    safety_rule_details JSONB NOT NULL DEFAULT '[]'::jsonb,
    rule_priority_floor INTEGER NOT NULL DEFAULT 5,
    escalated_by_rules BOOLEAN NOT NULL DEFAULT FALSE,
    escalated_by_uncertainty BOOLEAN NOT NULL DEFAULT FALSE,
    risk_indicators JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    unknown_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    model_version VARCHAR(40) NOT NULL,
    operating_threshold FLOAT NOT NULL,
    safety_mode VARCHAR(20) NOT NULL DEFAULT 'conservative',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_assessment_visit ON triage_assessments(visit_id);
CREATE INDEX idx_assessment_priority ON triage_assessments(final_priority);
CREATE INDEX idx_assessment_visit_created ON triage_assessments(visit_id, created_at);

COMMENT ON TABLE triage_assessments IS 'One triage scoring event; audit trail of AI decisions';
COMMENT ON COLUMN triage_assessments.final_priority IS 'Highest priority after all escalations (1=highest)';
COMMENT ON COLUMN triage_assessments.ml_only_priority IS 'Pure ML model output before safety rules';
COMMENT ON COLUMN triage_assessments.risk_probability IS 'Risk estimate from XGBoost model [0,1]';
COMMENT ON COLUMN triage_assessments.confidence_label IS 'Qualitative confidence: High | Medium | Low';
COMMENT ON COLUMN triage_assessments.uncertainty_score IS 'Quantitative uncertainty [0,1]';
COMMENT ON COLUMN triage_assessments.confidence_reasons IS 'Array of text reasons for confidence level';
COMMENT ON COLUMN triage_assessments.safety_rules_triggered IS 'Array of rule names that fired';
COMMENT ON COLUMN triage_assessments.escalated_by_rules IS 'Boolean: safety rules pushed priority up';
COMMENT ON COLUMN triage_assessments.escalated_by_uncertainty IS 'Boolean: high uncertainty pushed priority up';
COMMENT ON COLUMN triage_assessments.missing_fields IS 'Array of vitals not recorded at assessment time';
COMMENT ON COLUMN triage_assessments.trigger IS 'intake | reassessment_wait | reassessment_vitals | manual_rescore';


-- ============================================================================
-- TABLE 6: clinician_overrides
-- ============================================================================

CREATE TABLE clinician_overrides (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL UNIQUE REFERENCES triage_assessments(id) ON DELETE CASCADE,
    clinician_id VARCHAR(60) NOT NULL,
    clinician_role VARCHAR(40) NOT NULL DEFAULT 'triage_nurse',
    
    ai_priority INTEGER NOT NULL,
    override_priority INTEGER NOT NULL,
    direction VARCHAR(20) NOT NULL,
    reason_code VARCHAR(60) NOT NULL,
    reason_text TEXT NOT NULL,
    acknowledged_ai_recommendation BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_override_assessment ON clinician_overrides(assessment_id);
CREATE INDEX idx_override_clinician ON clinician_overrides(clinician_id);

COMMENT ON TABLE clinician_overrides IS 'Clinician''s final triage decision; legally meaningful under DPDP';
COMMENT ON COLUMN clinician_overrides.direction IS 'escalated | de-escalated';
COMMENT ON COLUMN clinician_overrides.reason_code IS 'Structured reason category (e.g., OBSERVED_DETERIORATION)';
COMMENT ON COLUMN clinician_overrides.reason_text IS 'Free-text clinical justification';


--
CREATE TABLE consent_records (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    purpose VARCHAR(80) NOT NULL,
    granted BOOLEAN NOT NULL DEFAULT TRUE,
    notice_version VARCHAR(20) NOT NULL DEFAULT 'v1.0-prototype',
    granted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    withdrawn_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_consent_patient ON consent_records(patient_id);
CREATE INDEX idx_consent_purpose ON consent_records(purpose);

COMMENT ON TABLE consent_records IS 'DPDP Act 2023 purpose-limited consent; one row per (patient, purpose)';
COMMENT ON COLUMN consent_records.purpose IS 'Data use purpose: clinical_triage | quality_audit | research | etc.';
COMMENT ON COLUMN consent_records.granted IS 'TRUE if patient consented; FALSE if withdrawn';
COMMENT ON COLUMN consent_records.withdrawn_at IS 'Timestamp if consent was withdrawn; NULL if still active';


-- ============================================================================
-- TABLE 8: audit_events
-- ============================================================================
-- Append-only audit trail. Never updated or deleted by application code.
--
-- prev_hash → event_hash chain each event to the previous one.
-- If a row is deleted or modified, the chain breaks and is detectable.
-- Cheap tamper-evidence for the prototype.
--
-- Event types: 'patient_registered', 'visit_created', 'vitals_recorded',
--              'triage_scored', 'reassessment_triggered', 'clinician_override',
--              'consent_granted', 'consent_withdrawn', 'simulation_run'
--
CREATE TABLE audit_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(40) NOT NULL,
    entity_type VARCHAR(40) NOT NULL,
    entity_id VARCHAR(60) NOT NULL,
    actor VARCHAR(60) NOT NULL DEFAULT 'system',
    purpose VARCHAR(80) NOT NULL DEFAULT 'clinical_triage',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    prev_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_event_type ON audit_events(event_type);
CREATE INDEX idx_audit_created ON audit_events(created_at);
CREATE INDEX idx_audit_entity ON audit_events(entity_type, entity_id);

COMMENT ON TABLE audit_events IS 'Append-only tamper-evident audit trail';
COMMENT ON COLUMN audit_events.event_type IS 'patient_registered | visit_created | vitals_recorded | triage_scored | reassessment_triggered | clinician_override | consent_* | simulation_run';
COMMENT ON COLUMN audit_events.entity_type IS 'patient | visit | vitals_record | triage_assessment | etc.';
COMMENT ON COLUMN audit_events.entity_id IS 'Primary key of affected entity';
COMMENT ON COLUMN audit_events.actor IS 'User ID, service name, or "system"';
COMMENT ON COLUMN audit_events.purpose IS 'DPDP purpose for this data access';
COMMENT ON COLUMN audit_events.payload IS 'Event details: {field: value, ...}';
COMMENT ON COLUMN audit_events.prev_hash IS 'SHA256 of previous audit event; NULL for first event';
COMMENT ON COLUMN audit_events.event_hash IS 'SHA256(prev_hash + payload); chain integrity check';


-- ============================================================================
-- TABLE 9: simulation_runs
-- ============================================================================
-- Persisted discrete-event simulation results.
-- Enables surge scenario comparison across page refreshes.
--
-- Scenario: 'normal', 'surge_3x', 'surge_5x', etc.
--
CREATE TABLE simulation_runs (
    id SERIAL PRIMARY KEY,
    scenario VARCHAR(40) NOT NULL,
    arrival_multiplier FLOAT NOT NULL DEFAULT 1.0,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulation_scenario ON simulation_runs(scenario);
CREATE INDEX idx_simulation_created ON simulation_runs(created_at);

COMMENT ON TABLE simulation_runs IS 'Discrete-event ED simulation results for surge planning';
COMMENT ON COLUMN simulation_runs.scenario IS 'normal | surge_3x | surge_5x | etc.';
COMMENT ON COLUMN simulation_runs.arrival_multiplier IS 'Patient arrival rate multiplier';
COMMENT ON COLUMN simulation_runs.params IS 'Simulation config: {doctors, beds, horizon_hours, ...}';
COMMENT ON COLUMN simulation_runs.metrics IS 'Results: {arrivals, mean_wait, queue_length, ...}';


-- ============================================================================
-- VIEWS (Optional, for common queries)
-- ============================================================================

-- Recent high-risk patients waiting
CREATE VIEW high_risk_waiting AS
SELECT
    p.id,
    p.patient_code,
    p.age,
    v.id as visit_id,
    v.chief_complaint,
    v.arrived_at,
    ta.final_priority,
    ta.confidence_label,
    ta.risk_probability
FROM patients p
JOIN visits v ON p.id = v.patient_id
JOIN triage_assessments ta ON v.id = ta.visit_id
WHERE v.status = 'waiting'
    AND ta.risk_probability > 0.7
    AND ta.created_at = (
        SELECT MAX(created_at) FROM triage_assessments WHERE visit_id = v.id
    )
ORDER BY ta.final_priority, v.arrived_at;

COMMENT ON VIEW high_risk_waiting IS 'Real-time view of high-risk patients currently waiting';

-- Assessment escalation audit
CREATE VIEW escalations_by_day AS
SELECT
    DATE(ta.created_at) as assessment_date,
    COUNT(CASE WHEN ta.escalated_by_rules THEN 1 END) as by_safety_rules,
    COUNT(CASE WHEN ta.escalated_by_uncertainty THEN 1 END) as by_uncertainty,
    COUNT(DISTINCT ta.visit_id) as total_assessments
FROM triage_assessments ta
GROUP BY DATE(ta.created_at)
ORDER BY assessment_date DESC;

COMMENT ON VIEW escalations_by_day IS 'Daily escalation rate by cause';


-- ============================================================================
-- CONSTRAINTS & INTEGRITY
-- ============================================================================

-- Ensure triage assessment priority is valid (1-5)
ALTER TABLE triage_assessments
ADD CONSTRAINT chk_priority_range CHECK (final_priority >= 1 AND final_priority <= 5);

-- Ensure risk probability in [0, 1]
ALTER TABLE triage_assessments
ADD CONSTRAINT chk_risk_probability CHECK (risk_probability >= 0 AND risk_probability <= 1);

-- Ensure uncertainty score in [0, 1]
ALTER TABLE triage_assessments
ADD CONSTRAINT chk_uncertainty_score CHECK (uncertainty_score >= 0 AND uncertainty_score <= 1);

-- Ensure age is non-negative
ALTER TABLE patients
ADD CONSTRAINT chk_patient_age CHECK (age >= 0 AND age <= 150);

-- Ensure override direction is valid
ALTER TABLE clinician_overrides
ADD CONSTRAINT chk_override_direction CHECK (direction IN ('escalated', 'de-escalated'));

-- Ensure visit timestamps are sensible
ALTER TABLE visits
ADD CONSTRAINT chk_visit_timeline CHECK (
    treatment_started_at IS NULL OR treatment_started_at >= arrived_at
);

ALTER TABLE visits
ADD CONSTRAINT chk_visit_closed CHECK (
    closed_at IS NULL OR closed_at >= arrived_at
);


-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Retention cleanup: find records past retention date
CREATE INDEX idx_visits_retention ON visits(retention_until) WHERE retention_until IS NOT NULL;

-- Audit trail traversal by timestamp
CREATE INDEX idx_audit_hash_chain ON audit_events(prev_hash);

-- Simulation metrics queries
CREATE INDEX idx_simulation_params ON simulation_runs USING GIN(params);


-- ============================================================================
-- METADATA
-- ============================================================================

COMMENT ON SCHEMA public IS 'PatientTriageAI Database Schema v1.0';

-- Grant appropriate permissions (adjust for your deployment)
-- GRANT USAGE ON SCHEMA public TO app_user;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_user;
