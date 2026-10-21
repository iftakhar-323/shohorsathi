import { useQuery } from "@tanstack/react-query";

import { api, type Paginated } from "./client";

export type Service = {
  id: number;
  slug: string;
  name_en: string;
  name_bn: string;
  description: string;
  image_url: string;
  base_price: string;
  warranty_days: number;
  emergency_available: boolean;
};

export type ServiceFilters = {
  q?: string;
  category?: string;
  area?: number;
  min_price?: number;
  max_price?: number;
};

export function useServices(filters: ServiceFilters = {}) {
  return useQuery({
    queryKey: ["services", filters],
    queryFn: async () => (await api.get<Paginated<Service>>("/services/", { params: filters })).data,
  });
}
