import { httpClient } from '../../api/http-client';
import type { ReferenceMarketer, ReferenceMarketers } from '../interfaces/reference-marketers';

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const fail = (): never => { throw new Error('Respuesta del catálogo de referencia no válida'); };

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : fail();
}

function text(value: unknown, max = 500): string {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= max
    ? value : fail();
}

function date(value: unknown): string {
  const result = text(value, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(result)) fail();
  const parsed = new Date(`${result}T00:00:00Z`);
  return parsed.toISOString().slice(0, 10) === result ? result : fail();
}

function url(value: unknown): string {
  const result = text(value, 2000);
  try {
    const parsed = new URL(result);
    if (parsed.protocol === 'https:') return result;
  } catch { /* Invalid source links fail the response. */ }
  return fail();
}

function revision(value: unknown): string {
  const result = text(value, 60);
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(result) &&
    Number.isFinite(Date.parse(result)) ? result : fail();
}

export async function loadReferenceMarketers(signal: AbortSignal): Promise<ReferenceMarketers> {
  const response = await httpClient.get(`${apiBase}/v1/market/reference-marketers`, {
    params: { sector: 'electricity' },
    signal,
    responseType: 'text',
    transformResponse: [(data: unknown) => data],
  });
  const body: unknown = response.data;
  if (typeof body !== 'string') return fail();
  if (body.length > 32_000 || new TextEncoder().encode(body).length > 32_000) return fail();
  let parsed: unknown;
  try { parsed = JSON.parse(body); } catch { return fail(); }
  const data = record(parsed);
  if (data.sector !== 'electricity' || data.scope !== 'reference_marketers') return fail();
  const rows = data.items;
  if (!Array.isArray(rows) || rows.length > 8) return fail();
  const snapshot_date = date(data.snapshot_date);
  const code_source_period = text(data.code_source_period, 6);
  if (!/^\d{4}T[1-4]$/.test(code_source_period)) fail();
  const code_source_metadata_modified = revision(data.code_source_metadata_modified);
  if (code_source_metadata_modified.slice(0, 10) > snapshot_date) fail();
  const codes = new Set<string>();
  const items = rows.map((value: unknown) => {
    const row = record(value);
    const marketer_code = text(row.marketer_code, 20);
    if (!/^R2-\d{3}$/.test(marketer_code) || codes.has(marketer_code)) fail();
    codes.add(marketer_code);
    const limit = row.territorial_limit;
    const territorial_limit: ReferenceMarketer['territorial_limit'] =
      limit === 'ceuta' || limit === 'melilla' ? limit : limit === null ? null : fail();
    return {
      marketer_code,
      name: text(row.name),
      territorial_limit,
    };
  });
  return {
    sector: 'electricity',
    scope: 'reference_marketers',
    snapshot_date,
    designation_source_url: url(data.designation_source_url),
    code_source_url: url(data.code_source_url),
    code_source_period,
    code_source_metadata_modified,
    attribution: text(data.attribution),
    items,
  };
}
