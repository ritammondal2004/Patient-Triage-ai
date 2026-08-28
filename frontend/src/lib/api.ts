import type {
  HealthResponse,
  EngineInfo,
  VisitIntakeRequest,
  TriageResponse,
  VitalsIn,
  ReassessmentOut,
  PatientOut,
  VisitOut,
  QueueEntryOut,
  QueueSummary,
  OverrideRequest,
  OverrideOut,
  AuditEventOut,
  AuditChainStatus,
  AuditPolicy,
  SimulationRequest,
  SimulationResultOut,
} from "../types/api";

const API_URL = import.meta.env.VITE_API_URL || "http://patienttriage-alb-19208886.eu-north-1.elb.amazonaws.com";

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  fetchHealth: () => fetchApi<HealthResponse>("/health"),
  fetchEngineInfo: () => fetchApi<EngineInfo>("/triage/engine"),
  submitIntake: (data: VisitIntakeRequest) => fetchApi<TriageResponse>("/triage/intake", { method: "POST", body: JSON.stringify(data) }),
  fetchVisitAssessments: (visitId: number) => fetchApi<TriageResponse[]>(`/triage/visits/${visitId}`),
  submitVitals: (visitId: number, data: VitalsIn) => fetchApi<TriageResponse>(`/triage/visits/${visitId}/vitals`, { method: "POST", body: JSON.stringify(data) }),
  rescoreVisit: (visitId: number) => fetchApi<TriageResponse>(`/triage/visits/${visitId}/rescore`, { method: "POST" }),
  fetchReassessment: (visitId: number) => fetchApi<ReassessmentOut>(`/triage/visits/${visitId}/reassessment`),
  
  fetchPatients: (limit?: number) => fetchApi<PatientOut[]>(`/patients${limit ? `?limit=${limit}` : ""}`),
  fetchPatient: (code: string) => fetchApi<PatientOut>(`/patients/${code}`),
  fetchPatientVisits: (code: string) => fetchApi<VisitOut[]>(`/patients/${code}/visits`),
  
  fetchQueue: (hospitalId?: number) => fetchApi<QueueEntryOut[]>(`/queue${hospitalId ? `?hospital_id=${hospitalId}` : ""}`),
  fetchQueueSummary: (hospitalId?: number) => fetchApi<QueueSummary>(`/queue/summary${hospitalId ? `?hospital_id=${hospitalId}` : ""}`),
  callNextPatient: (hospitalId?: number) => fetchApi<QueueEntryOut | null>(`/queue/next${hospitalId ? `?hospital_id=${hospitalId}` : ""}`, { method: "POST" }),
  closeVisit: (visitId: number, status?: string) => fetchApi<VisitOut>(`/queue/visits/${visitId}/close${status ? `?status=${status}` : ""}`, { method: "POST" }),
  reassessAll: (hospitalId?: number) => fetchApi<{ processed: number; rescored: number }>(`/queue/reassess${hospitalId ? `?hospital_id=${hospitalId}` : ""}`, { method: "POST" }),
  
  createOverride: (assessmentId: number, data: OverrideRequest) => fetchApi<OverrideOut>(`/overrides/assessments/${assessmentId}`, { method: "POST", body: JSON.stringify(data) }),
  fetchOverrides: (limit?: number) => fetchApi<OverrideOut[]>(`/overrides${limit ? `?limit=${limit}` : ""}`),
  fetchOverride: (id: number) => fetchApi<OverrideOut>(`/overrides/${id}`),
  
  fetchAuditEvents: (params?: Record<string, string | number>) => {
    const qs = params ? new URLSearchParams(params as Record<string, string>).toString() : "";
    return fetchApi<AuditEventOut[]>(`/audit/events${qs ? `?${qs}` : ""}`);
  },
  verifyAuditChain: () => fetchApi<AuditChainStatus>("/audit/verify"),
  fetchAuditPolicy: () => fetchApi<AuditPolicy>("/audit/policy"),
  
  fetchSimulationScenarios: () => fetchApi<string[]>("/simulation/scenarios"),
  runSimulation: (data: SimulationRequest) => fetchApi<SimulationResultOut>("/simulation/run", { method: "POST", body: JSON.stringify(data) }),
  fetchSimulationRuns: (params?: Record<string, string | number>) => {
    const qs = params ? new URLSearchParams(params as Record<string, string>).toString() : "";
    return fetchApi<SimulationResultOut[]>(`/simulation/runs${qs ? `?${qs}` : ""}`);
  },
  fetchSimulationRun: (id: number) => fetchApi<SimulationResultOut>(`/simulation/runs/${id}`),
  runAblation: (params: any) => fetchApi<any>("/simulation/ablation", { method: "POST", body: JSON.stringify(params) }),
  fetchDayNight: (params?: any) => {
    const qs = params ? new URLSearchParams(params as Record<string, string>).toString() : "";
    return fetchApi<any>(`/simulation/daynight${qs ? `?${qs}` : ""}`);
  },
};
