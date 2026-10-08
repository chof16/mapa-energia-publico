import { useQuery } from '@tanstack/react-query';
import { loadProvincePresence } from '../actions/load-province-presence';

export function useProvincePresence(provinceCode: string | null) {
  return useQuery({
    queryKey: ['distribution', 'province', provinceCode],
    queryFn: ({ signal }) => loadProvincePresence(provinceCode!, signal),
    enabled: provinceCode !== null,
    retry: false,
    staleTime: 300_000,
  });
}
