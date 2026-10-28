import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import {
  loadQuarters,
  loadMarketers,
  loadCommunities,
  loadSupplies,
  loadShareSeries,
} from '../actions/load-electricity';
import { validMarketer } from '../lib/electricity-url';

export function useElectricity(
  enabled: boolean,
  evolution: boolean,
  community: string | null,
) {
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();
  const quarters = useQuery({
    queryKey: ['electricity', 'quarters'],
    queryFn: ({ signal }) => loadQuarters(signal),
    enabled,
    retry: false,
    staleTime: 300_000,
  });
  const requestedPeriod = params.get('period');
  // An unpublished incoming period stays visible as an error, never silently substituted.
  const period = requestedPeriod || quarters.data?.[0]?.period || '';
  const published = !!quarters.data?.some((item) => item.period === period);
  const marketer = params.get('marketer') || '';
  const codeValid = validMarketer(marketer);
  const comparison = [...new Set((params.get('compare') || '').split(','))]
    .filter((code) => validMarketer(code) && code !== marketer)
    .slice(0, 3);
  const metric = params.get('metric') === 'share' ? 'share' : 'supplies';
  const layer =
    params.get('map_layer') === 'market' ? 'market' : 'distribution';
  const marketers = useQuery({
    queryKey: ['electricity', 'marketers', period],
    queryFn: ({ signal }) => loadMarketers(period, signal),
    enabled: enabled && published,
    retry: false,
    staleTime: 300_000,
  });
  const communities = useQuery({
    queryKey: ['electricity', 'communities', marketer, period],
    queryFn: ({ signal }) => loadCommunities(marketer, period, signal),
    enabled: enabled && !evolution && published && codeValid,
    retry: false,
    staleTime: 300_000,
  });
  const areaMarketers = useQuery({
    queryKey: ['electricity', 'area-marketers', period, community],
    queryFn: ({ signal }) => loadMarketers(period, signal, community),
    enabled: enabled && !evolution && published && !!community,
    retry: false,
    staleTime: 300_000,
  });
  const supplies = useQuery({
    queryKey: ['electricity', 'supplies', marketer, community],
    queryFn: ({ signal }) => loadSupplies(marketer, community, signal),
    enabled:
      enabled && evolution && metric === 'supplies' && published && codeValid,
    retry: false,
    staleTime: 300_000,
  });
  const shareSeries = useQuery({
    queryKey: ['electricity', 'share-series', marketer, community],
    queryFn: ({ signal }) => loadShareSeries(marketer, community, signal),
    enabled:
      enabled && evolution && metric === 'share' && published && codeValid,
    retry: false,
    staleTime: 300_000,
  });
  async function preloadPeriod(nextPeriod: string) {
    await Promise.all([
      queryClient.ensureQueryData({
        queryKey: ['electricity', 'marketers', nextPeriod],
        queryFn: ({ signal }) => loadMarketers(nextPeriod, signal),
        staleTime: 300_000,
      }),
      queryClient.ensureQueryData({
        queryKey: ['electricity', 'communities', marketer, nextPeriod],
        queryFn: ({ signal }) => loadCommunities(marketer, nextPeriod, signal),
        staleTime: 300_000,
      }),
      ...(community
        ? [
            queryClient.ensureQueryData({
              queryKey: ['electricity', 'area-marketers', nextPeriod, community],
              queryFn: ({ signal }) =>
                loadMarketers(nextPeriod, signal, community),
              staleTime: 300_000,
            }),
          ]
        : []),
    ]);
  }
  function change(changes: {
    period?: string;
    marketer?: string;
    metric?: string;
    layer?: 'market' | 'distribution';
    comparison?: string[];
  }, options?: { replace?: boolean }) {
    const next = new URLSearchParams(params);
    if (published) next.set('period', period);
    if (changes.period !== undefined) {
      next.set('period', changes.period);
      next.delete('year');
    }
    if (changes.marketer !== undefined) {
      if (changes.marketer) next.set('marketer', changes.marketer);
      else next.delete('marketer');
      if (published) next.set('period', period);
    }
    if (changes.metric !== undefined) next.set('metric', changes.metric);
    if (changes.layer !== undefined) next.set('map_layer', changes.layer);
    if (changes.comparison !== undefined) {
      if (changes.comparison.length)
        next.set('compare', changes.comparison.join(','));
      else next.delete('compare');
    }
    if (next.toString() !== params.toString())
      setParams(next, { replace: options?.replace });
  }
  return {
    enabled,
    period,
    published,
    marketer,
    codeValid,
    comparison,
    community,
    metric,
    layer,
    quarters,
    marketers,
    areaMarketers,
    communities,
    supplies,
    shareSeries,
    preloadPeriod,
    change,
  };
}
