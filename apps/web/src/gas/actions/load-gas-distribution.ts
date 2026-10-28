import { httpClient } from '../../api/http-client';
import type { GasNetworkDistributors, GasNetworkPage, GasNetworkProvinces, GasNetworkSource } from '../interfaces/distribution';

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const fail = (): never => { throw new Error('La evidencia territorial de gas no cumple el contrato esperado.'); };
const record = (value: unknown): Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : fail();
const text = (value: unknown, max = 300): string => typeof value === 'string' && value.length > 0 && value.length <= max ? value : fail();
const count = (value: unknown): number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : fail();
const hash = (value: unknown) => { const result = text(value, 64); return /^[a-f0-9]{64}$/.test(result) ? result : fail(); };
const province = (value: unknown) => { const result = text(value, 2); return /^(0[1-9]|[1-4][0-9]|5[0-2])$/.test(result) ? result : fail(); };
function url(value: unknown) {
  const result = text(value, 2000);
  try { const parsed = new URL(result); if (parsed.protocol === 'https:' && !parsed.username && !parsed.password) return result; }
  catch { /* Validate source links before rendering them. */ }
  return fail();
}
function date(value: unknown) {
  const result = text(value, 10);
  const parsed = new Date(`${result}T00:00:00Z`);
  return /^\d{4}-\d{2}-\d{2}$/.test(result) && Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === result ? result : fail();
}
function source(value: unknown): GasNetworkSource {
  const row = record(value);
  const period = text(row.period, 7);
  const retrieved = text(row.retrieved_at, 60);
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period) || !/^\d{4}-\d{2}-\d{2}T/.test(retrieved) || !Number.isFinite(Date.parse(retrieved)) ||
      row.reuse_status !== 'review_pending' || row.confidence !== 'official_document' || row.network_scope !== 'natural_gas_at_most_4_bar') fail();
  return { load_id: hash(row.load_id), period, source_url: url(row.source_url), download_url: url(row.download_url),
    source_title: text(row.source_title), published_on: date(row.published_on), retrieved_at: retrieved,
    source_sha256: hash(row.source_sha256), row_count: count(row.row_count), attribution: text(row.attribution),
    reuse_status: 'review_pending', confidence: 'official_document', network_scope: 'natural_gas_at_most_4_bar' };
}
async function get(path: string, signal: AbortSignal, loadId?: string) {
  if (loadId) hash(loadId);
  const response = await httpClient.get(`${apiBase}/v1/gas/distribution/${path}`, {
    params: { limit: 100, offset: 0, ...(loadId ? { load_id: loadId } : {}) },
    signal, responseType: 'text', transformResponse: [(data: unknown) => data],
  });
  const body: unknown = response.data;
  if (typeof body !== 'string' || body.length > 200_000 || new TextEncoder().encode(body).length > 200_000 || !body.trimStart().startsWith('{')) return fail();
  let parsed: unknown;
  try { parsed = JSON.parse(body); } catch { return fail(); }
  return record(parsed);
}
function page<T>(data: Record<string, unknown>, parse: (item: Record<string, unknown>) => T): GasNetworkPage<T> {
  if (data.sector !== 'gas' || data.scope !== 'documented_provincial_presence' || data.complete !== false ||
      data.limit !== 100 || data.offset !== 0 || !Array.isArray(data.items) || data.items.length > 100) return fail();
  const total = count(data.total);
  // A map must never silently paint a truncated summary or hide distributors.
  if (total !== data.items.length) fail();
  return { sector: 'gas', scope: 'documented_provincial_presence', complete: false, source: source(data.source),
    total, limit: 100, offset: 0, items: data.items.map((item) => parse(record(item))) };
}
export async function loadGasNetworkProvinces(signal: AbortSignal): Promise<GasNetworkProvinces> {
  const result = page(await get('provinces', signal), (row) => ({ province_code: province(row.province_code),
    documented_distributor_count: count(row.documented_distributor_count), source_row_count: count(row.source_row_count), supply_points: count(row.supply_points) }));
  if (result.total > 52 || new Set(result.items.map((row) => row.province_code)).size !== result.total ||
      result.items.some((row) => row.documented_distributor_count < 1 || row.source_row_count < row.documented_distributor_count)) fail();
  return result;
}
export async function loadGasNetworkDistributors(code: string, loadId: string, signal: AbortSignal): Promise<GasNetworkDistributors> {
  const data = await get(`provinces/${province(code)}`, signal, loadId);
  const result = page(data, (row) => ({ distributor_name: text(row.distributor_name, 160),
    source_row_count: count(row.source_row_count), supply_points: count(row.supply_points) }));
  if (data.province_code !== code || result.source.load_id !== loadId ||
      new Set(result.items.map((row) => row.distributor_name)).size !== result.total || result.items.some((row) => row.source_row_count < 1)) fail();
  return { ...result, province_code: code };
}
