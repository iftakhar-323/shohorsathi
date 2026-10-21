import { api, type Paginated } from "@shohor/web-core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type CartItem = { id: number; item_type: "product" | "service"; slug: string; name: string; unit_price: string; quantity: number; line_total: string };
export type Cart = { items: CartItem[]; subtotal: string };

export type Booking = {
  id: number;
  order: number;
  order_number: string;
  service_slug: string;
  service_name: string;
  price: string;
  scheduled_date: string;
  slot: string;
  slot_label: string;
  problem_description: string;
  photo_urls: string[];
  is_emergency: boolean;
  status: string;
  provider_id: number | null;
  provider_name: string;
  provider_phone: string;
  arrival_code: string;
  warranty_days: number;
  warranty_until: string | null;
  completed_at: string | null;
  created_at: string;
};

export type Order = {
  id: number;
  number: string;
  status: string;
  payment_method: "cod" | "online";
  payment_status: string;
  subtotal: string;
  delivery_fee: string;
  discount: string;
  total: string;
  contact_name: string;
  contact_phone: string;
  address_line: string;
  area_id: number;
  area_name: string;
  note: string;
  items: { slug: string; name: string; unit_price: string; quantity: number; line_total: string }[];
  bookings: Booking[];
  created_at: string;
};

export type Address = { id: number; label: string; area: number; area_detail: { id: number; name_bn: string; name_en: string }; line: string; latitude: string | null; longitude: string | null; is_default: boolean };

export function useCart(enabled = true) {
  return useQuery({ queryKey: ["cart"], queryFn: async () => (await api.get<Cart>("/cart/")).data, enabled });
}

export function useAddToCart() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { item_type: "product" | "service"; slug: string; quantity?: number }) =>
      (await api.post<CartItem>("/cart/items/", body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cart"] }),
  });
}

export function useUpdateCartItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, quantity }: { id: number; quantity: number }) =>
      quantity > 0 ? api.patch(`/cart/items/${id}/`, { quantity }) : api.delete(`/cart/items/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cart"] }),
  });
}

export function useOrders() {
  return useQuery({ queryKey: ["orders"], queryFn: async () => (await api.get<Paginated<Order>>("/orders/")).data });
}

export function useOrder(id: string | undefined) {
  return useQuery({
    queryKey: ["orders", id],
    queryFn: async () => (await api.get<Order>(`/orders/${id}/`)).data,
    enabled: !!id,
    refetchInterval: 15_000,
  });
}

export function useTracking(id: string | undefined) {
  return useQuery({
    queryKey: ["orders", id, "tracking"],
    queryFn: async () => (await api.get<{ status: string; events: { status: string; note: string; booking: number | null; created_at: string }[] }>(`/orders/${id}/tracking/`)).data,
    enabled: !!id,
    refetchInterval: 15_000,
  });
}

export function useAddresses(enabled = true) {
  return useQuery({ queryKey: ["addresses"], queryFn: async () => (await api.get<Address[]>("/me/addresses/")).data, enabled });
}
