/* ── Shared API types matching the live backend exactly ── */

export interface HealthResponse {
  status: string;
  environment: string;
  engine: {
    model_version: string;
    production_model: string;
    operating_threshold: number;
    safety_mode: string;
    jurisdiction: string;
  };
}

export interface EngineInfo {
  model_version: string;
  production_model: string;
  operating_threshold: number;
  safety_mode: string;
  jurisdiction: string;
  status: string;
  data_source: string;
}

export interface VitalsIn {
  heart_rate?: number;
  resp_rate?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  temperature_c?: number;
  spo2?: number;
  pain_score?: number;
  source?: string;
}

export interface PatientIn {
  patient_code?: string;
  age: number;
  gender: string;
  has_prior_history?: boolean;
  prior_conditions_count?: number;
  prior_ed_visits?: number;
}

export interface VisitIntakeRequest {
  patient: PatientIn;
  chief_complaint: string;
  symptom_text?: string;
  arrival_mode?: string;
  vitals?: VitalsIn;
  hospital_id?: number;
  is_ambiguous_case?: boolean;
  safety_mode?: string;
}

export interface AssessmentOut {
  id: number;
  visit_id: number;
  vitals_record_id?: number;
  trigger: string;
  final_priority: number;
  priority_label: string;
  ml_only_priority: number;
  risk_probability: number;
  confidence_label: string;
  uncertainty_score: number;
  confidence_reasons: string[];
  safety_rules_triggered: string[];
  escalated_by_rules: boolean;
  escalated_by_uncertainty: boolean;
  risk_indicators: string[];
  missing_fields: string[];
  model_version: string;
  operating_threshold: number;
  safety_mode: string;
  created_at: string;
}

export interface PatientOut {
  id: number;
  patient_code: string;
  age: number;
  gender: string;
  has_prior_history: boolean;
  prior_conditions_count: number;
  prior_ed_visits: number;
  is_synthetic: boolean;
  registered_at: string;
}

export interface VisitOut {
  id: number;
  patient_id: number;
  hospital_id?: number;
  chief_complaint: string;
  symptom_text: string;
  arrival_mode: string;
  status: string;
  arrived_at: string;
  reference_esi_level?: number;
  retention_until?: string;
}

export interface VitalsOut {
  id: number;
  visit_id: number;
  source: string;
  heart_rate?: number;
  resp_rate?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  temperature_c?: number;
  spo2?: number;
  pain_score?: number;
  recorded_at: string;
}

export interface ConfidenceOut {
  label: string;
  uncertainty_score: number;
  reasons: string[];
}

export interface TriageResponse {
  visit: VisitOut;
  patient: PatientOut;
  assessment: AssessmentOut;
  vitals?: VitalsOut;
  confidence: ConfidenceOut;
}

export interface QueueEntryOut {
  visit_id: number;
  patient_code: string;
  patient_id: number;
  age: number;
  chief_complaint: string;
  arrival_mode: string;
  final_priority: number;
  priority_label: string;
  confidence_label: string;
  risk_probability: number;
  escalated_by_rules: boolean;
  escalated_by_uncertainty: boolean;
  safety_rules_triggered: string[];
  arrived_at: string;
  waited_minutes: number;
  max_wait_minutes: number;
  wait_breached: boolean;
  reassessment_due: boolean;
  reassessment_reasons: string[];
  last_assessed_at: string;
  override_applied: boolean;
}

export interface QueueSummary {
  waiting: number;
  by_priority: Record<string, number>;
  wait_breaches: number;
  reassessments_due: number;
  longest_wait_minutes: number;
  average_wait_minutes: number;
  low_confidence: number;
}

export interface OverrideRequest {
  clinician_id: string;
  clinician_role: string;
  override_priority: number;
  reason_code: string;
  reason_text: string;
  acknowledged_ai_recommendation: boolean;
}

export interface OverrideOut {
  id: number;
  assessment_id: number;
  clinician_id: string;
  clinician_role: string;
  ai_priority: number;
  override_priority: number;
  direction: string;
  reason_code: string;
  reason_text: string;
  acknowledged_ai_recommendation: boolean;
  created_at: string;
}

export interface AuditEventOut {
  id: number;
  event_type: string;
  entity_type: string;
  entity_id: string;
  actor: string;
  purpose: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  event_hash: string;
  created_at: string;
}

export interface AuditChainStatus {
  events: number;
  intact: boolean;
  first_broken_id: number | null;
}

export interface AuditPolicy {
  jurisdiction: string;
  retention_days: number;
  lawful_basis: string;
  purpose_limitation: string;
  consent_notice_version: string;
  [key: string]: unknown;
}

export interface SimulationRequest {
  scenario: string;
  hours?: number;
  arrival_multiplier?: number;
  doctors?: number;
  beds?: number;
  seed?: number;
  persist?: boolean;
}

export interface SimulationScenario {
  name: string;
  label: string;
  arrival_multiplier: number;
  doctors: number;
  beds: number;
  reassessment_enabled: boolean;
}

export interface SimulationResultOut {
  id: number;
  scenario: string;
  arrival_multiplier: number;
  params: Record<string, unknown>;
  metrics: Record<string, unknown>;
  created_at: string;
}

export interface ReassessmentOut {
  due: boolean;
  reasons: string[];
  last_assessment?: AssessmentOut;
}
