import { useQuery } from '@tanstack/react-query';
import { loadProvinceSummary } from '../actions/load-province-summary';

export function useProvinceSummary(enabled: boolean) {
  return useQuery({
    queryKey: ['distribution', 'province-summary', 'electricity'],
    queryFn: ({ signal }) => loadProvinceSummary(signal),
    enabled,
    retry: false,
    staleTime: 300_000,
  });
}
