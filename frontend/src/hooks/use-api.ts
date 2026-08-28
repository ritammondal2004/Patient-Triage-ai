import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { VisitIntakeRequest, OverrideRequest, SimulationRequest } from "../types/api";

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: api.fetchHealth });
export const useEngineInfo = () => useQuery({ queryKey: ["engineInfo"], queryFn: api.fetchEngineInfo });

export const useSubmitIntake = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: VisitIntakeRequest) => api.submitIntake(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["queueSummary"] });
    },
  });
};

export const useQueue = (hospitalId?: number) => useQuery({
  queryKey: ["queue", hospitalId],
  queryFn: () => api.fetchQueue(hospitalId),
  staleTime: 30000,
});

export const useQueueSummary = (hospitalId?: number) => useQuery({
  queryKey: ["queueSummary", hospitalId],
  queryFn: () => api.fetchQueueSummary(hospitalId),
  staleTime: 30000,
});

export const useCallNext = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (hospitalId?: number) => api.callNextPatient(hospitalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["queueSummary"] });
    },
  });
};

export const useCloseVisit = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ visitId, status }: { visitId: number; status?: string }) => api.closeVisit(visitId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["queueSummary"] });
    },
  });
};

export const useReassessAll = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (hospitalId?: number) => api.reassessAll(hospitalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
  });
};

export const usePatients = (limit?: number) => useQuery({ queryKey: ["patients", limit], queryFn: () => api.fetchPatients(limit) });
export const usePatient = (code: string) => useQuery({ queryKey: ["patient", code], queryFn: () => api.fetchPatient(code) });
export const usePatientVisits = (code: string) => useQuery({ queryKey: ["patientVisits", code], queryFn: () => api.fetchPatientVisits(code) });

export const useVisitAssessments = (visitId: number) => useQuery({ queryKey: ["visitAssessments", visitId], queryFn: () => api.fetchVisitAssessments(visitId) });

export const useCreateOverride = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ assessmentId, data }: { assessmentId: number; data: OverrideRequest }) => api.createOverride(assessmentId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["overrides"] });
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
  });
};

export const useOverrides = (limit?: number) => useQuery({ queryKey: ["overrides", limit], queryFn: () => api.fetchOverrides(limit) });
export const useOverride = (id: number) => useQuery({ queryKey: ["override", id], queryFn: () => api.fetchOverride(id) });

export const useAuditEvents = (params?: Record<string, string | number>) => useQuery({
  queryKey: ["auditEvents", params],
  queryFn: () => api.fetchAuditEvents(params),
  staleTime: 300000,
});

export const useAuditVerify = () => useQuery({ queryKey: ["auditVerify"], queryFn: api.verifyAuditChain });
export const useAuditPolicy = () => useQuery({ queryKey: ["auditPolicy"], queryFn: api.fetchAuditPolicy });

export const useSimulationScenarios = () => useQuery({ queryKey: ["simulationScenarios"], queryFn: api.fetchSimulationScenarios });

export const useRunSimulation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SimulationRequest) => api.runSimulation(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["simulationRuns"] }),
  });
};

export const useSimulationRuns = (params?: Record<string, string | number>) => useQuery({ queryKey: ["simulationRuns", params], queryFn: () => api.fetchSimulationRuns(params) });
export const useSimulationRun = (id: number) => useQuery({ queryKey: ["simulationRun", id], queryFn: () => api.fetchSimulationRun(id) });

export const useRunAblation = () => useMutation({ mutationFn: (params: any) => api.runAblation(params) });
export const useDayNight = (params?: any) => useQuery({ queryKey: ["daynight", params], queryFn: () => api.fetchDayNight(params) });
