import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type Technician = { id: string; name: string };

export function useTechnicians() {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["technicians"],
    enabled: Boolean(accessToken),
    queryFn: () =>
      apiFetch<{ items: Technician[]; total: number }>("/api/v1/technicians", {
        token: accessToken,
      }),
  });
}
