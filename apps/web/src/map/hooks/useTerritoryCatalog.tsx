import { useQuery } from '@tanstack/react-query';
import { loadTerritoryCatalog } from '../actions/load-territory-catalog';
import { labelsUrl } from '../lib/map-style';

export function useTerritoryCatalog() {
  return useQuery({
    queryKey: ['territory-catalog', labelsUrl],
    queryFn: ({ signal }) => loadTerritoryCatalog(signal),
    // The cartographic artifact does not change while exploring the map.
    staleTime: Infinity,
    retry: false,
  });
}
