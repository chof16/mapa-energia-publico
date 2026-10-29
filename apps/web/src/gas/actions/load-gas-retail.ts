import { httpClient } from '../../api/http-client';
import type { GasFilters, GasPage, GasSeries } from '../interfaces/retail';
import { array, gasContext, gasCoverage, gasHash, gasId, gasIdentityStatus, gasMarketer, gasPeriodItem, gasPoint, gasReference, integer, invalidGas, object, string } from '../lib/retail-validation';

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const maxBytes = 8_000_000;

// Bound JSON before decoding, independently of the declared Content-Type.
export function parseGasJson(body: unknown): Record<string, unknown> {
  if (typeof body !== 'string' || body.length > maxBytes || new TextEncoder().encode(body).length > maxBytes || !body.trimStart().startsWith('{')) return invalidGas();
  let depth = 0, quoted = false, escaped = false;
  for (const c of body) {
    if (quoted) {
      if (escaped) escaped = false;
      else if (c === '\\') escaped = true;
      else if (c === '"') quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === '{' || c === '[') { if (++depth > 24) return invalidGas(); }
    else if (c === '}' || c === ']') depth--;
  }
  try { return object(JSON.parse(body)); } catch { return invalidGas(); }
}
async function get(path: string, params: Record<string, string | number>, signal: AbortSignal) {
  const response = await httpClient.get(`${apiBase}/v1/gas/${path}`, {
    params, signal, responseType: 'text', transformResponse: [(v: unknown) => v],
  });
  return parseGasJson(response.data);
}
function pageItems<T>(r: Record<string, unknown>, limit: number, offset: number, parse: (v: unknown) => T) {
  const total = integer(r.total, 10_100);
  if (r.limit !== limit || r.offset !== offset) return invalidGas();
  const items = array(r.items, limit, parse);
  if (items.length !== Math.min(limit, Math.max(0, total - offset))) return invalidGas();
  return { total, items };
}
async function pages<T>(path: string, params: Record<string, string>, signal: AbortSignal, parse: (v: unknown) => T, check?: (r: Record<string, unknown>) => void): Promise<GasPage<T>> {
  if (params.load_id) gasHash(params.load_id);
  const limit = 100;
  const first = await get(path, { ...params, limit, offset: 0 }, signal);
  check?.(first);
  const context = gasContext(first), result = pageItems(first, limit, 0, parse);
  if (params.load_id && context.revision.load_id !== params.load_id) return invalidGas();
  const items = [...result.items];
  // Pin subsequent pages to the first revision, even when a newer import arrives.
  for (let offset = limit; offset < result.total; offset += limit) {
    const next = await get(path, { ...params, load_id: context.revision.load_id, limit, offset }, signal);
    check?.(next);
    const nextContext = gasContext(next), page = pageItems(next, limit, offset, parse);
    if (nextContext.revision.load_id !== context.revision.load_id || page.total !== result.total) return invalidGas();
    items.push(...page.items);
  }
  return { ...context, total: result.total, limit, offset: 0, items };
}
export async function loadGasRevision(loadId: string, signal: AbortSignal) {
  if (loadId) gasHash(loadId);
  const r = await get('retail/revisions', { ...(loadId ? { load_id: loadId } : {}), limit: 1, offset: 0 }, signal);
  const result = pageItems(r, 1, 0, gasCoverage).items[0] ?? null;
  if (loadId && result && result.load_id !== loadId) return invalidGas();
  return result;
}
type DataFilters = Pick<GasFilters, 'metric' | 'scope'>;
export async function loadGasPeriods(filters: DataFilters, loadId: string, signal: AbortSignal) {
  const result = await pages('retail/periods', { ...filters, load_id: loadId }, signal, gasPeriodItem);
  if (result.items.some((x) => x.audit.metric !== filters.metric || x.scope !== filters.scope) || new Set(result.items.map((x) => x.audit.period)).size !== result.total) return invalidGas();
  return result;
}
export async function loadGasMarketers(filters: DataFilters, loadId: string, signal: AbortSignal) {
  const result = await pages('retail/marketers', { ...filters, load_id: loadId }, signal, gasMarketer, (r) => {
    if (r.metric !== filters.metric || r.scope !== filters.scope) invalidGas();
  });
  if (new Set(result.items.map((item) => item.marketer_id)).size !== result.total) return invalidGas();
  return result;
}
export async function loadGasSeries(id: string, filters: Pick<GasFilters, 'metric' | 'scope' | 'start_period' | 'end_period'>, loadId: string, signal: AbortSignal): Promise<GasSeries> {
  gasId(id); gasHash(loadId);
  const params = { metric: filters.metric, scope: filters.scope, load_id: loadId,
    ...(filters.start_period ? { start_period: filters.start_period } : {}),
    ...(filters.end_period ? { end_period: filters.end_period } : {}), limit: 120, offset: 0 };
  const r = await get(`retail/series/${id}`, params, signal), context = gasContext(r), page = pageItems(r, 120, 0, gasPoint);
  if (gasIdentityStatus(r.identity_status) === 'source_local_identity') return invalidGas();
  if (page.total > 120 || r.marketer_id !== id || r.metric !== filters.metric || r.scope !== filters.scope || context.revision.load_id !== loadId ||
      new Set(page.items.map((x) => x.audit.period)).size !== page.total ||
      page.items.some((p) => p.audit.metric !== filters.metric || (filters.start_period && p.audit.period < filters.start_period) || (filters.end_period && p.audit.period > filters.end_period) || p.records.some((v) => v.gas_id !== id || v.scope !== filters.scope))) return invalidGas();
  return { ...context, ...page, limit: 120, offset: 0, marketer_id: id, company_name: string(r.company_name, 500), identity_review_note: string(r.identity_review_note ?? ''), identity_status: gasIdentityStatus(r.identity_status), metric: filters.metric, scope: filters.scope };
}
export function loadGasReferences(signal: AbortSignal) {
  return pages('reference-marketers', {}, signal, gasReference);
}
