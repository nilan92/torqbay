import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type Customer = { id: string; name: string; phone: string | null };

export function useCustomer(customerId: string) {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["customers", customerId],
    enabled: Boolean(accessToken) && Boolean(customerId),
    queryFn: () => apiFetch<Customer>(`/api/v1/customers/${customerId}`, { token: accessToken }),
  });
}
