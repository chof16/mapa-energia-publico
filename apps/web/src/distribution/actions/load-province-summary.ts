import { httpClient } from '../../api/http-client';
import type { ProvincePresenceSummary } from '../interfaces/distribution';
import { MAX_PROVINCIAL_DISTRIBUTORS } from '../lib/validation-limits';

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const fail = (): never => { throw new Error('Resumen provincial no válido'); };

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : fail();
}

function date(value: unknown): string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return fail();
  const parsed = new Date(`${value}T00:00:00Z`);
  return parsed.toISOString().slice(0, 10) === value ? value : fail();
}

export async function loadProvinceSummary(signal: AbortSignal): Promise<ProvincePresenceSummary> {
  const response = await httpClient.get(`${apiBase}/v1/distribution/provinces`, {
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
  if (data.sector !== 'electricity' || data.scope !== 'documented_provincial_presence' ||
      data.complete !== false) return fail();
  const rows = data.items;
  if (!Array.isArray(rows) || rows.length > 52) return fail();
  const codes = new Set<string>();
  const items = rows.map((value: unknown) => {
    const item = record(value);
    const code = item.province_code;
    const count = item.documented_distributor_count;
    if (typeof code !== 'string' || !/^(0[1-9]|[1-4][0-9]|5[0-2])$/.test(code) || codes.has(code)) return fail();
    if (typeof count !== 'number' || !Number.isSafeInteger(count) || count < 1 || count > MAX_PROVINCIAL_DISTRIBUTORS) return fail();
    codes.add(code);
    return { province_code: code, documented_distributor_count: count };
  });
  return {
    sector: 'electricity',
    scope: 'documented_provincial_presence',
    complete: false,
    snapshot_date: date(data.snapshot_date),
    items,
  };
}
