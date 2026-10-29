import { useEffect, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { loadGasMarketers, loadGasPeriods, loadGasRevision, loadGasSeries } from '../actions/load-gas-retail';
import type { GasFilters } from '../interfaces/retail';
import { useGasQuery } from './useGasQuery';

// Old document identities must not survive in company selections or the HMR cache.
const catalogueContract = 'canonical-companies-v1';
const sourceLocalId = (v: string) => /^gas-cnmc-/.test(v);
const id = (v: string | null) => v && /^gas-[a-z0-9-]{1,75}$/.test(v) && !sourceLocalId(v) ? v : '';
const period = (v: string | null) => v && /^20\d{2}T[1-4]$/.test(v) ? v : '';
function readGasFilters(params: URLSearchParams): GasFilters {
  const marketer = id(params.get('marketer'));
  const start = period(params.get('start_period')), end = period(params.get('end_period'));
  const load = params.get('load_id') || '';
  return { metric: params.get('metric') === 'sales' ? 'sales' : 'clients',
    scope: params.get('scope') === 'liberalised' ? 'liberalised' : params.get('scope') === 'regulated' ? 'regulated' : 'whole_market',
    measure: params.get('measure') === 'share' ? 'share' : 'absolute', display: params.get('display') === 'table' ? 'table' : 'chart',
    marketer, compare: marketer ? [...new Set((params.get('compare') || '').split(',').map(id).filter((v) => v && v !== marketer))].slice(0, 3) : [],
    start_period: start, end_period: start && end && start > end ? '' : end, load_id: /^[a-f0-9]{64}$/.test(load) ? load : '' };
}
function gasFilterParams(filters: GasFilters) {
  const params = new URLSearchParams({ sector: 'gas' });
  if (filters.metric !== 'clients') params.set('metric', filters.metric);
  if (filters.scope !== 'whole_market') params.set('scope', filters.scope);
  if (filters.measure !== 'absolute') params.set('measure', filters.measure);
  if (filters.display !== 'chart') params.set('display', filters.display);
  for (const key of ['marketer', 'start_period', 'end_period', 'load_id'] as const) if (filters[key]) params.set(key, filters[key]);
  if (filters.compare.length) params.set('compare', filters.compare.join(','));
  return params;
}

export function useGasRetail() {
  const [params, setParams] = useSearchParams();
  const [retiredSelection] = useState(() => [params.get('marketer') || '', ...(params.get('compare') || '').split(',')].some(sourceLocalId));
  const filters = readGasFilters(params);
  const canonical = gasFilterParams(filters).toString();
  useEffect(() => { if (params.toString() !== canonical) setParams(canonical, { replace: true }); }, [canonical, params, setParams]);
  function change(update: Partial<GasFilters>) {
    const next = { ...filters, ...update };
    if ((update.metric && update.metric !== filters.metric) || (update.scope && update.scope !== filters.scope)) { next.marketer = ''; next.compare = []; }
    if (update.marketer !== undefined) next.compare = next.compare.filter((v) => v !== update.marketer);
    if (!next.marketer) next.compare = [];
    const clean = readGasFilters(gasFilterParams(next));
    setParams(gasFilterParams(clean));
  }
  const revision = useQuery({
    queryKey: ['gas', 'retail', catalogueContract, 'revision', filters.load_id],
    queryFn: ({ signal }) => loadGasRevision(filters.load_id, signal), retry: false,
    staleTime: filters.load_id ? 300_000 : 0,
    refetchOnWindowFocus: !filters.load_id,
    refetchInterval: filters.load_id ? false : 60_000,
  });
  const loadId = revision.data?.load_id || '';
  const dataFilters = { metric: filters.metric, scope: filters.scope };
  const periods = useGasQuery(['retail', catalogueContract, 'periods', loadId, dataFilters], (signal) => loadGasPeriods(dataFilters, loadId, signal), !!loadId);
  const marketers = useGasQuery(['retail', catalogueContract, 'marketers', loadId, dataFilters], (signal) => loadGasMarketers(dataFilters, loadId, signal), !!loadId);
  const ids = [filters.marketer, ...filters.compare].filter(Boolean);
  const seriesFilters = { ...dataFilters, start_period: filters.start_period, end_period: filters.end_period };
  const series = useQueries({ queries: ids.map((id) => ({ queryKey: ['gas', 'retail', catalogueContract, 'series', loadId, id, seriesFilters],
    queryFn: ({ signal }: { signal: AbortSignal }) => loadGasSeries(id, seriesFilters, loadId, signal), enabled: !!loadId, retry: false, staleTime: 300_000 })) });
  return { filters, change, revision, periods, marketers, ids, series, retiredSelection };
}
