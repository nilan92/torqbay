import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type InventoryItem = {
  id: string;
  sku: string;
  name: string;
  category: string | null;
  unit_cost: number;
  unit_price: number;
  quantity_on_hand: number;
  reorder_threshold: number;
  supplier_id: string | null;
};

type InventoryItemListResponse = {
  items: InventoryItem[];
  total: number;
  page: number;
  page_size: number;
};

/** No search endpoint exists — filtering the list client-side is fine for a
 * shop's inventory (up to 100 items, the API's page-size ceiling). */
export function useInventoryItems(options?: { lowStock?: boolean }) {
  const { accessToken } = useAuth();
  const lowStock = options?.lowStock ?? false;

  return useQuery({
    queryKey: ["inventory-items", { lowStock }],
    enabled: Boolean(accessToken),
    queryFn: () =>
      apiFetch<InventoryItemListResponse>(
        `/api/v1/inventory-items?page=1&page_size=100${lowStock ? "&low_stock=true" : ""}`,
        { token: accessToken }
      ),
  });
}

export function useInventoryItem(itemId: string) {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["inventory-items", itemId],
    enabled: Boolean(accessToken) && Boolean(itemId),
    queryFn: () =>
      apiFetch<InventoryItem>(`/api/v1/inventory-items/${itemId}`, { token: accessToken }),
  });
}

export function useCreateInventoryItem() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: {
      sku: string;
      name: string;
      category?: string;
      unit_cost: number;
      unit_price: number;
      quantity_on_hand?: number;
      reorder_threshold?: number;
    }) => apiFetch<InventoryItem>("/api/v1/inventory-items", { method: "POST", body, token: accessToken }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-items"] });
    },
  });
}

/** Stock (quantity_on_hand) is deliberately not editable here — it only
 * moves through job-part consumption or a purchase-order receive, never a
 * direct edit, so drift between the number on the shelf and the number in
 * the system can't happen silently. */
export function useUpdateInventoryItem(itemId: string) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: {
      name?: string;
      category?: string;
      unit_cost?: number;
      unit_price?: number;
      reorder_threshold?: number;
    }) =>
      apiFetch<InventoryItem>(`/api/v1/inventory-items/${itemId}`, {
        method: "PATCH",
        body,
        token: accessToken,
      }),
    onSuccess: (item) => {
      queryClient.setQueryData(["inventory-items", itemId], item);
      queryClient.invalidateQueries({ queryKey: ["inventory-items"] });
    },
  });
}
