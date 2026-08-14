import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type LaborEntry = {
  id: string;
  job_id: string;
  technician_id: string;
  start_time: string;
  end_time: string | null;
  hourly_rate: number | null;
};

type LaborEntryListResponse = {
  items: LaborEntry[];
  total: number;
};

export function useLaborEntries(jobId: string) {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["jobs", jobId, "labor-entries"],
    enabled: Boolean(accessToken) && Boolean(jobId),
    queryFn: () =>
      apiFetch<LaborEntryListResponse>(`/api/v1/jobs/${jobId}/labor-entries?page=1&page_size=100`, {
        token: accessToken,
      }),
  });
}

/** Starts a timer: technicians here are salaried, so no rate is sent — see
 * project-torqbay-labour-model. */
export function useStartTimer(jobId: string) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (technicianId: string) =>
      apiFetch<LaborEntry>(`/api/v1/jobs/${jobId}/labor-entries`, {
        method: "POST",
        body: { technician_id: technicianId, start_time: new Date().toISOString() },
        token: accessToken,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId, "labor-entries"] });
    },
  });
}

export function useStopTimer(jobId: string) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (entryId: string) =>
      apiFetch<LaborEntry>(`/api/v1/jobs/${jobId}/labor-entries/${entryId}`, {
        method: "PATCH",
        body: { end_time: new Date().toISOString() },
        token: accessToken,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId, "labor-entries"] });
    },
  });
}
