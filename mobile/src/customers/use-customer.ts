import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type Customer = {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
};

type CustomerListResponse = {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
};

export function useCustomers() {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["customers"],
    enabled: Boolean(accessToken),
    queryFn: () =>
      apiFetch<CustomerListResponse>("/api/v1/customers?page=1&page_size=50", {
        token: accessToken,
      }),
  });
}

export function useCustomer(customerId: string) {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["customers", customerId],
    enabled: Boolean(accessToken) && Boolean(customerId),
    queryFn: () => apiFetch<Customer>(`/api/v1/customers/${customerId}`, { token: accessToken }),
  });
}

export function useCreateCustomer() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { name: string; phone?: string; email?: string; address?: string }) =>
      apiFetch<Customer>("/api/v1/customers", { method: "POST", body, token: accessToken }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}
