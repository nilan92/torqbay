import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";
import { useAuth } from "@/auth/auth-context";

export type InventoryItem = {
  id: string;
  sku: string;
  name: string;
  unit_price: number;
  quantity_on_hand: number;
};

/** No search endpoint exists — filtering the list client-side is fine for a
 * shop's inventory (up to 100 items, the API's page-size ceiling). */
export function useInventoryItems() {
  const { accessToken } = useAuth();

  return useQuery({
    queryKey: ["inventory-items"],
    enabled: Boolean(accessToken),
    queryFn: () =>
      apiFetch<{ items: InventoryItem[]; total: number }>(
        "/api/v1/inventory-items?page=1&page_size=100",
        { token: accessToken }
      ),
  });
}
