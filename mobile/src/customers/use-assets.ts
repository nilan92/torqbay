import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type Asset = {
  id: string;
  customer_id: string;
  type: string;
  label: string;
  identifier: string | null;
  notes: string | null;
};

type AssetListResponse = {
  items: Asset[];
  total: number;
  page: number;
  page_size: number;
};

export function useAssets(customerId: string) {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["customers", customerId, "assets"],
    enabled: Boolean(accessToken) && Boolean(customerId),
    queryFn: () =>
      apiFetch<AssetListResponse>(`/api/v1/customers/${customerId}/assets?page=1&page_size=50`, {
        token: accessToken,
      }),
  });
}

export function useCreateAsset(customerId: string) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { type: string; label: string; identifier?: string }) =>
      apiFetch<Asset>(`/api/v1/customers/${customerId}/assets`, {
        method: "POST",
        body,
        token: accessToken,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers", customerId, "assets"] });
    },
  });
}
