import { useQuery } from '@tanstack/react-query';

export function useGasQuery<T>(key: readonly unknown[], load: (signal: AbortSignal) => Promise<T>, enabled = true) {
  return useQuery({ queryKey: ['gas', ...key], queryFn: ({ signal }) => load(signal), enabled, retry: false, staleTime: 300_000 });
}
