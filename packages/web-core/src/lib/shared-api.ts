import { useQuery } from "@tanstack/react-query";

import { api, type Paginated } from "./api";

export type Area = { id: number; city: string; name_en: string; name_bn: string; ward: string };
export type Category = { id: number; kind: "product" | "service"; parent: number | null; slug: string; name_en: string; name_bn: string; sort_order: number; is_active: boolean };

export type CatalogItem = {
  id: number;
  category: number;
  category_slug: string;
  slug: string;
  name_en: string;
  name_bn: string;
  description: string;
  image_url: string;
  area_ids: number[];
  is_active: boolean;
};
export type Service = CatalogItem & { base_price: string; price_note: string; duration_minutes: number; warranty_days: number; emergency_available: boolean };
export type Product = CatalogItem & { price: string; unit: string; stock: number; shop_name: string };

export function useAreas(city?: string) {
  return useQuery({
    queryKey: ["areas", city],
    queryFn: async () => (await api.get<Area[]>("/areas/", { params: city ? { city } : {} })).data,
    staleTime: 10 * 60_000,
  });
}

export function useCategories(kind?: "product" | "service") {
  return useQuery({
    queryKey: ["categories", kind],
    queryFn: async () => (await api.get<Category[]>("/categories/", { params: kind ? { kind } : {} })).data,
    staleTime: 10 * 60_000,
  });
}

export type CatalogFilters = { q?: string; category?: string; area?: number; min_price?: number; max_price?: number; ordering?: string; page?: number; emergency?: string };

export function useServices(filters: CatalogFilters = {}) {
  return useQuery({
    queryKey: ["services", filters],
    queryFn: async () => (await api.get<Paginated<Service>>("/services/", { params: filters })).data,
  });
}

export function useProducts(filters: CatalogFilters = {}) {
  return useQuery({
    queryKey: ["products", filters],
    queryFn: async () => (await api.get<Paginated<Product>>("/products/", { params: filters })).data,
  });
}

export function areaName(areas: Area[] | undefined, id: number) {
  return areas?.find((a) => a.id === id)?.name_bn ?? `#${id}`;
}

/** Starts an online payment and sends the browser to the gateway (SSLCommerz or the dev mock page). */
export async function payOnline(purpose: "order" | "subscription" | "custom_request_advance", referenceId: number) {
  const { data } = await api.post<{ tran_id: string; redirect_url: string }>("/payments/initiate/", { purpose, reference_id: referenceId });
  window.location.href = data.redirect_url;
}
