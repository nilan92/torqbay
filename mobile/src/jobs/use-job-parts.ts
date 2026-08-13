import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type JobPart = {
  id: string;
  job_id: string;
  inventory_item_id: string;
  quantity: number;
  unit_cost_at_time: number;
  unit_price_at_time: number;
  overdrawn: boolean;
  shortfall: number;
};

type JobPartListResponse = {
  items: JobPart[];
  total: number;
};

export function useJobParts(jobId: string) {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["jobs", jobId, "parts"],
    enabled: Boolean(accessToken) && Boolean(jobId),
    queryFn: () =>
      apiFetch<JobPartListResponse>(`/api/v1/jobs/${jobId}/parts?page=1&page_size=100`, {
        token: accessToken,
      }),
  });
}

export function useAddJobPart(jobId: string) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { inventory_item_id: string; quantity: number }) =>
      apiFetch<JobPart>(`/api/v1/jobs/${jobId}/parts`, {
        method: "POST",
        body,
        token: accessToken,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId, "parts"] });
    },
  });
}
