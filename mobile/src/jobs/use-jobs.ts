import { useQuery } from "@tanstack/react-query";

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
