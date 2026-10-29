// Preserve geographic context while removing retired gas statistics filters.
export function gasMapParams(params: URLSearchParams) {
  const next = new URLSearchParams(params);
  for (const key of ['dataset', 'period', 'year', 'quarter', 'load_id', 'observed_name', 'compare_name',
    'province_name', 'tariff_group', 'market_segment', 'supply_type', 'observation_kind', 'mode',
    'metric', 'scope', 'measure', 'search', 'page', 'limit', 'map_layer', 'marketer', 'compare', 'display', 'start_period', 'end_period',
    'role', 'snapshot_id', 'snapshot_date', 'offset', 'active_tab']) next.delete(key);
  const view = next.get('map_view') || next.get('view');
  next.delete('map_view');
  if (view === 'canary_islands' || view === 'mainland') next.set('view', view);
  else next.delete('view');
  next.set('sector', 'gas');
  return next;
}
