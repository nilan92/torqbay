import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type Job = {
  id: string;
  title: string;
  description: string | null;
  status: string;
  customer_id: string;
  asset_id: string;
  assigned_technician_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  labor_cost: number;
};

type JobListResponse = {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
};

export function useJobs() {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["jobs"],
    enabled: Boolean(accessToken),
    queryFn: () =>
      apiFetch<JobListResponse>("/api/v1/jobs?page=1&page_size=50", {
        token: accessToken,
      }),
  });
}

export function useJob(jobId: string) {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["jobs", jobId],
    enabled: Boolean(accessToken) && Boolean(jobId),
    queryFn: () => apiFetch<Job>(`/api/v1/jobs/${jobId}`, { token: accessToken }),
  });
}

/** Job status transitions (Start, Mark Done, Cancel) and the flat labour charge. */
export function useUpdateJob(jobId: string) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { status?: string; labor_cost?: number }) => {
      const path = "status" in body ? `/api/v1/jobs/${jobId}/status` : `/api/v1/jobs/${jobId}`;
      return apiFetch<Job>(path, { method: "PATCH", body, token: accessToken });
    },
    onSuccess: (job) => {
      queryClient.setQueryData(["jobs", jobId], job);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
