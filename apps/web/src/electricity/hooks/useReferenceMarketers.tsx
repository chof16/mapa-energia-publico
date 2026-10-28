import { useQuery } from '@tanstack/react-query';
import { loadReferenceMarketers } from '../actions/load-reference-marketers';

export function useReferenceMarketers(enabled: boolean) {
  return useQuery({
    queryKey: ['electricity', 'reference-marketers', 'electricity'],
    queryFn: ({ signal }) => loadReferenceMarketers(signal),
    enabled,
    retry: false,
    staleTime: 300_000,
  });
}
