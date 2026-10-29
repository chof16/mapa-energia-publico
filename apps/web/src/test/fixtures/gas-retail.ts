import type { GasAudit, GasCoverage, GasMetric, GasScope, GasSeriesValue, GasSource } from '../../gas/interfaces/retail';

// Synthetic fixtures only. No real evidence or source cells are redistributed.
export const gasRetailSource: GasSource = { source_id: 'source-test', url: 'https://example.org/gas.pdf', title: 'Informe sintético 2025', publisher: 'Organismo de prueba', published_on: '2026-01-01', retrieved_on: '2026-10-29', sha256: 'b'.repeat(64), media_type: 'pdf', page_count: 20, reuse_status: 'review_pending', notes: 'Ámbito peninsular de prueba; no comparable a todo el territorio.' };
export const gasRetailRevision: GasCoverage = {
  load_id: 'a'.repeat(64), reviewed_on: '2026-10-29', imported_at: '2026-10-29T10:00:00Z', complete: false, reuse_status: 'review_pending',
  coverage: (['clients', 'sales'] as const).map((metric) => ({ metric, counts: [{ status: 'reviewed', periods: 3 }, { status: 'partial', periods: 1 }], audits_url: `/v1/gas/retail/periods?metric=${metric}&load_id=${'a'.repeat(64)}` })),
  issue_count: 2, issues: [{ period: '2025T2', metric: 'clients', status: 'partial', note: 'Continuación pendiente de revisión.', audit_url: `/v1/gas/retail/periods?period=2025T2&load_id=${'a'.repeat(64)}` }], issues_truncated: false,
};
export const gasRetailContext = { sector: 'gas', complete: false, revision: gasRetailRevision, geographic_scope: 'source_defined', geographic_note: 'No se presupone comparabilidad nacional histórica.', identity_note: 'Identidades literales independientes, sin equivalencia R2.' };
export function gasRetailAudit(period = '2025T1', metric: GasMetric = 'clients'): GasAudit {
  return { period, metric, status: period === '2025T2' ? 'partial' : 'reviewed', pages: [3], sources: [gasRetailSource], note: period === '2025T2' ? 'Continuación pendiente de revisión.' : 'Tabla sintética revisada.' };
}
export function gasRetailValue(id = 'gas-test-0', period = '2025T1', metric: GasMetric = 'clients', scope: GasScope = 'whole_market'): GasSeriesValue {
  const bounded = period === '2025T3', zero = period === '2025T4';
  const value = bounded ? null : zero ? '0' : metric === 'clients' ? '100' : '1000';
  const observation = { observation_id: `${id}-${period}`, mapping_id: 'mapping-test', observed_name: `Empresa sintética ${id.split('-').at(-1)}`, mapping_review_note: 'Identidad literal de prueba.', month: `2025-${String(Number(period.at(-1)) * 3).padStart(2, '0')}`, metric, scope, unit: metric === 'clients' ? 'clients' as const : 'GWh' as const, page: 3, table_label: 'Tabla sintética', source_row: '1', raw_value: bounded ? '<50' : value!, status: bounded ? 'bounded' as const : zero ? 'zero' as const : 'exact' as const, value, upper_bound: bounded ? '50' : null, upper_bound_exclusive: true as const, review_note: 'Celda de prueba.' };
  const base = { gas_id: id, source: gasRetailSource, period, metric, scope, status: observation.status, unit: metric === 'clients' ? 'clients' as const : 'MWh' as const, value, upper_bound: bounded ? '50' : null, upper_bound_exclusive: true as const, original_unit: observation.unit, original_value: value, original_upper_bound: bounded ? '50' : null, missing_months: [], input_statuses: [observation.status], observations: [{ ...observation, original_unit: observation.unit, review_status: 'reviewed' as const, publication_status: 'reviewed' as const }] };
  return { ...base, denominator: { ...base, gas_id: 'gas-total', status: 'exact', value: '10000', upper_bound: null }, denominator_status: 'matched', share: bounded ? null : zero ? '0' : '0.01' };
}
export function gasRetailResponse(path: string, params: Record<string, string | number> = {}) {
  const metric = (params.metric || 'clients') as GasMetric, scope = (params.scope || 'whole_market') as GasScope;
  const limit = Number(params.limit || 100), offset = Number(params.offset || 0);
  const paged = <T,>(items: T[]) => ({ ...gasRetailContext, total: items.length, limit, offset, items: items.slice(offset, offset + limit) });
  const periods = ['2025T1', '2025T2', '2025T3', '2025T4'];
  if (path.endsWith('/revisions')) return { total: 1, limit, offset, items: [gasRetailRevision] };
  if (path.endsWith('/periods')) return paged(periods.map((period) => ({ audit: gasRetailAudit(period, metric), scope, reviewed_retailer_count: period === '2025T2' ? 0 : 25 })));
  if (path.endsWith('/marketers')) return { ...paged(Array.from({ length: 25 }, (_, i) => ({ marketer_id: `gas-test-${i}`, company_name: `Empresa sintética ${i}`, observed_name: `Empresa sintética ${i}`, source: gasRetailSource, mapping_review_note: 'Correspondencia revisada de prueba.' })).filter((m) => !params.search || m.observed_name.includes(String(params.search)))), metric, scope };
  if (path.includes('/series/')) {
    const id = path.split('/').at(-1)!;
    return { ...paged(periods.filter((p) => (!params.start_period || p >= params.start_period) && (!params.end_period || p <= params.end_period)).map((period) => ({ audit: gasRetailAudit(period, metric), availability: period === '2025T2' ? 'unreviewed' : 'reviewed', records: period === '2025T2' ? [] : [gasRetailValue(id, period, metric, scope)] }))), marketer_id: id, company_name: `Empresa sintética ${id.split('-').at(-1)}`, metric, scope };
  }
  if (path.endsWith('/reference-marketers')) return paged(Array.from({ length: 4 }, (_, i) => ({ marketer_id: `gas-cur-test-${i}`, observations: [
    { observed_name: `CUR sintética ${i}`, designation: 'gas_cur', evidence_on: '2022-11-14', page: 3, review_note: 'Fecha de evidencia, no alta legal.', source: { ...gasRetailSource, published_on: '2022-11-14' } },
    { observed_name: `CUR sintética ${i} variante`, designation: 'gas_cur', evidence_on: '2026-10-29', page: 0, review_note: 'Variante literal consultada.', source: { ...gasRetailSource, source_id: 'source-html', media_type: 'html', published_on: null, url: 'https://example.org/gas' } },
  ] })));
  throw new Error(`Unexpected synthetic gas route: ${path}`);
}
