import { afterEach, describe, expect, it, vi } from 'vitest';
import { httpClient } from '../../api/http-client';
import { gasRetailContext, gasRetailResponse, gasRetailRevision, gasRetailSource, gasRetailValue } from '../../test/fixtures/gas-retail';
import { loadGasMarketers, loadGasPeriods, loadGasReferences, loadGasRevision, loadGasSeries, parseGasJson } from './load-gas-retail';
import { gasPoint } from '../lib/retail-validation';
import { gasChartValue, gasPointLabel } from '../lib/retail-format';

const signal = new AbortController().signal;
const filters = { metric: 'clients' as const, scope: 'whole_market' as const };
const load = gasRetailRevision.load_id;
afterEach(() => vi.restoreAllMocks());
function mockApi() {
  return vi.spyOn(httpClient, 'get').mockImplementation(async (path, config) => ({ data: JSON.stringify(gasRetailResponse(path, config?.params as Record<string, string | number>)) }));
}
describe('gas retail API boundary', () => {
  it('loads a small company catalogue in one bounded request with query parameters', async () => {
    const request = mockApi();
    const result = await loadGasMarketers(filters, load, signal);
    expect(request).toHaveBeenCalledTimes(1);
    expect(result.total).toBe(25);
    expect(result.items).toHaveLength(25);
    expect(request.mock.calls[0][1]?.params).toEqual({ ...filters, limit: 100, offset: 0, load_id: load });
  });
  it('pins every audit page to the revision and does not silently truncate the period catalogue', async () => {
    const request = vi.spyOn(httpClient, 'get').mockImplementation(async (_path, config) => {
      const offset = Number((config?.params as { offset: number }).offset);
      const items = Array.from({ length: 101 }, (_, i) => ({ audit: { period: `${2000 + Math.floor(i / 4)}T${i % 4 + 1}`, metric: 'clients', status: 'partial', pages: [], sources: [], note: 'Pendiente' }, scope: 'whole_market', reviewed_retailer_count: 0 }));
      return { data: JSON.stringify({ ...gasRetailContext, limit: 100, offset, total: 101, items: items.slice(offset, offset + 100) }) };
    });
    const result = await loadGasPeriods(filters, load, signal);
    expect(result.items).toHaveLength(101);
    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls[1][1]?.params).toMatchObject({ load_id: load, offset: 100 });
  });
  it('rejects truncated pages, changed revisions and mismatched metric responses', async () => {
    const request = mockApi();
    for (const mismatch of [{ total: 26 }, { revision: { ...gasRetailRevision, load_id: 'c'.repeat(64) } }, { metric: 'sales' }]) {
      request.mockResolvedValueOnce({ data: JSON.stringify({ ...gasRetailResponse('/marketers', { limit: 100 }), ...mismatch }) });
      await expect(loadGasMarketers(filters, load, signal)).rejects.toThrow(/contrato/);
    }
  });
  it('loads all actual route shapes and keeps source pages, names and original units', async () => {
    mockApi();
    expect((await loadGasRevision('', signal))?.coverage).toHaveLength(2);
    expect((await loadGasReferences(signal)).items).toHaveLength(4);
    const result = await loadGasSeries('gas-test-0', { ...filters, metric: 'sales', start_period: '2025T1', end_period: '2025T4' }, load, signal);
    expect(result.items[0].records[0]).toMatchObject({ unit: 'MWh', original_unit: 'GWh', value: '1000' });
    expect(result.items[0].records[0].observations[0]).toMatchObject({ page: 3, observed_name: 'Empresa sintética 0' });
    expect(result.items[1].records).toEqual([]);
  });
  it('rejects duplicate company IDs rather than displaying inconsistent pagination totals', async () => {
    const item = { marketer_id: 'gas-company', company_name: 'Empresa canónica', observed_name: 'Nombre literal', source: gasRetailSource, mapping_review_note: 'Correspondencia revisada.' };
    vi.spyOn(httpClient, 'get').mockResolvedValue({ data: JSON.stringify({ ...gasRetailContext, metric: 'clients', scope: 'whole_market', total: 2, limit: 100, offset: 0, items: [item, { ...item, observed_name: 'Otra variante' }] }) });
    await expect(loadGasMarketers(filters, load, signal)).rejects.toThrow(/contrato/);
  });
  it('rejects source-local observation identities as public companies or company histories', async () => {
    const request = mockApi();
    const item = { marketer_id: 'gas-source-local', company_name: 'Empresa', observed_name: 'Empresa', source: gasRetailSource, mapping_review_note: '', identity_status: 'source_local_identity' };
    request.mockResolvedValueOnce({ data: JSON.stringify({ ...gasRetailContext, metric: 'clients', scope: 'whole_market', total: 1, limit: 100, offset: 0, items: [item] }) });
    await expect(loadGasMarketers(filters, load, signal)).rejects.toThrow(/contrato/);
    request.mockResolvedValueOnce({ data: JSON.stringify({ ...gasRetailResponse('/series/gas-test-0', { limit: 120 }), identity_status: 'source_local_identity' }) });
    await expect(loadGasSeries('gas-test-0', { ...filters, start_period: '', end_period: '' }, load, signal)).rejects.toThrow(/contrato/);
  });
  it('keeps the dropdown complete if the catalogue later exceeds one API page', async () => {
    const items = Array.from({ length: 101 }, (_, i) => ({ marketer_id: `gas-test-${i}`, company_name: `Empresa ${i}`, observed_name: `Nombre ${i}`, source: gasRetailSource, mapping_review_note: '' }));
    const request = vi.spyOn(httpClient, 'get').mockImplementation(async (_path, config) => {
      const offset = (config?.params as { offset: number }).offset;
      return { data: JSON.stringify({ ...gasRetailContext, metric: 'clients', scope: 'whole_market', total: 101, limit: 100, offset, items: items.slice(offset, offset + 100) }) };
    });
    expect((await loadGasMarketers(filters, load, signal)).items).toHaveLength(101);
    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls[1][1]?.params).toMatchObject({ load_id: load, offset: 100 });
  });
  it.each(['<html>bad</html>', '{bad', JSON.stringify({ a: 'x'.repeat(8_000_001) }), '{"a":' + '['.repeat(25) + '0' + ']'.repeat(25) + '}'])('rejects malformed or unbounded JSON before schema decoding', (body) => {
    expect(() => parseGasJson(body)).toThrow(/contrato/);
  });
  it('rejects unsafe URLs, oversized arrays, numeric leaks from partial audits and invalid shares', () => {
    const record = gasRetailValue();
    const point = { audit: { period: '2025T1', metric: 'clients', status: 'reviewed', pages: [3], sources: [gasRetailSource], note: '' }, availability: 'reviewed', records: [record] };
    for (const unsafe of [
      { ...point, audit: { ...point.audit, status: 'partial' } },
      { ...point, records: Array(101).fill(record) },
      { ...point, records: [{ ...record, source: { ...gasRetailSource, url: 'javascript:alert(1)' } }] },
      { ...point, records: [{ ...record, share: '1.5' }] },
      { ...point, records: [{ ...record, denominator_status: 'ambiguous' }] },
    ]) expect(() => gasPoint(unsafe)).toThrow(/contrato/);
  });
  it('preserves bounded and unavailable observations without chart values, and zero as a real point', async () => {
    mockApi();
    const result = await loadGasSeries('gas-test-0', { ...filters, start_period: '', end_period: '' }, load, signal);
    expect(result.items.map((p) => gasChartValue(p, false))).toEqual([100, null, null, 0]);
    expect(result.items.map((p) => gasChartValue(p, true))).toEqual([0.01, null, null, 0]);
    expect(gasPointLabel(result.items[2], false)).toBe('<50 clientes');
    expect(gasPointLabel(result.items[1], false)).toBe('Revisión parcial');
    expect(gasChartValue({ ...result.items[0], records: [result.items[0].records[0], result.items[0].records[0]] }, false)).toBeNull();
    const defective = { ...result.items[1], audit: { ...result.items[1].audit, status: 'source_error' as const } };
    expect(gasPointLabel(defective, false)).toBe('Defecto en la fuente');
  });
  it('uses source and cell review under a partial quarter summary, without combining alternatives', () => {
    const sourceAudit = { source: gasRetailSource, period: '2025T1', metric: 'clients', status: 'reviewed', table_review_status: 'reviewed', retailer_coverage: 'reviewed', geographic_scope: 'peninsular', pages: [3], note: 'Fuente revisada.' };
    const record = { ...gasRetailValue(), source_audit: sourceAudit, review_status: 'reviewed' };
    const point = { audit: { period: '2025T1', metric: 'clients', status: 'partial', pages: [3], sources: [gasRetailSource], note: 'Otra fuente pendiente.' }, availability: 'reviewed', source_audits: [sourceAudit], records: [record] };
    expect(gasChartValue(gasPoint(point), false)).toBe(100);
    expect(gasChartValue(gasPoint({ ...point, records: [record, record] }), false)).toBeNull();
    for (const change of [{ review_status: 'partial' }, { source_audit: { ...sourceAudit, status: 'partial' } }, { source_audit: { ...sourceAudit, retailer_coverage: 'partial' } }, { observations: [{ ...record.observations[0], review_status: 'partial' }] }]) {
      expect(() => gasPoint({ ...point, records: [{ ...record, ...change }] })).toThrow(/contrato/);
    }
  });
  it('preserves unresolved month provenance and withholds defective values from charts', () => {
    const original = gasRetailValue();
    const source_audit = { source: gasRetailSource, period: '2025T1', metric: 'clients', status: 'source_error', table_review_status: 'source_error', retailer_coverage: 'reviewed', geographic_scope: 'source_defined', pages: [3], note: 'Mes sin resolver.' };
    const record = { ...original, status: 'missing', value: null, original_value: null, share: null, denominator: null, denominator_status: 'unavailable', review_status: 'source_error', source_audit, observations: [], unresolved_observations: [{ ...original.observations[0], month: null, period: '2025T1', status: 'source_error', value: null, upper_bound: null, review_status: 'source_error', raw_value: '100' }] };
    const point = gasPoint({ audit: { period: '2025T1', metric: 'clients', status: 'source_error', pages: [3], sources: [gasRetailSource], note: '' }, availability: 'unreviewed', records: [record], source_audits: [source_audit] });
    expect(point.records[0].unresolved_observations?.[0]).toMatchObject({ month: null, raw_value: '100', value: null });
    expect(gasChartValue(point, false)).toBeNull();
    expect(() => gasPoint({ ...point, records: [{ ...record, value: '100' }] })).toThrow(/contrato/);
  });
});
