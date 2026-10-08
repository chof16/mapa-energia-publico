import { httpClient } from '../../api/http-client';
import type {
  Source,
  Quarter,
  Marketer,
  Communities,
  SuppliesSeries,
  ShareSeries,
} from '../interfaces/market';
import { validPeriod, validMarketer } from '../lib/market-url';
export async function loadShareSeries(
  code: string,
  community: string | null,
  signal: AbortSignal,
): Promise<ShareSeries> {
  const data = await get(
    `share-series/${encodeURIComponent(code)}`,
    { limit: 120, ...(community ? { community_code: community } : {}) },
    signal,
  );
  if (
    data.marketer_code !== code ||
    data.community_code !== community ||
    data.denominator !== 'supplies_with_registered_marketer'
  )
    fail();
  const series = list(data.series, 120)
    .map((item) => {
      const row = record(item);
      const supplies = count(row.supplies);
      const marketer_supplies = count(row.marketer_supplies);
      const share = row.share;
      if (
        supplies > marketer_supplies ||
        (marketer_supplies === 0
          ? share !== null
          : typeof share !== 'number' ||
            !Number.isFinite(share) ||
            Math.abs(share - supplies / marketer_supplies) > 1e-9)
      )
        fail();
      return {
        ...source(row),
        period: period(row.period),
        metadata_modified: revision(row.metadata_modified),
        community_code: community || '',
        supplies,
        marketer_supplies,
        share: share as number | null,
        direct_consumer_supplies: count(row.direct_consumer_supplies),
        unavailable_supplies: count(row.unavailable_supplies),
      };
    })
    .sort((a, b) => a.period.localeCompare(b.period));
  unique(series.map((row) => row.period));
  return { series };
}

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const fail = (): never => {
  throw new Error('Respuesta de mercado no válida');
};
function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : fail();
}
function text(value: unknown): string {
  return typeof value === 'string' && value.length <= 4000 ? value : fail();
}
function count(value: unknown): number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
    ? value
    : fail();
}
function period(value: unknown): string {
  const result = text(value);
  return validPeriod(result) ? result : fail();
}
function revision(value: unknown): string {
  const result = text(value);
  return result && Number.isFinite(Date.parse(result)) ? result : fail();
}
function source(value: Record<string, unknown>): Source {
  function url(key: string) {
    const result = text(value[key]);
    return /^https?:\/\//.test(result) ? result : fail();
  }
  return {
    source_url: url('source_url'),
    attribution: text(value.attribution),
    license_id: text(value.license_id),
    license_url: url('license_url'),
    conditions_url: url('conditions_url'),
  };
}
function list(value: unknown, cap: number): unknown[] {
  return Array.isArray(value) && value.length <= cap ? value : fail();
}
function unique(values: string[]) {
  if (new Set(values).size !== values.length) fail();
}
async function get(
  path: string,
  params: Record<string, string | number>,
  signal: AbortSignal,
) {
  const response = await httpClient.get(`${apiBase}/v1/market/${path}`, {
    params: { sector: 'electricity', ...params },
    signal,
    responseType: 'text',
    transformResponse: [(data: unknown) => data],
  });
  if (
    typeof response.data !== 'string' ||
    response.data.length > 1_000_000 ||
    new TextEncoder().encode(response.data).length > 1_000_000
  )
    fail();
  const result = record(JSON.parse(response.data));
  if (result.sector !== 'electricity') fail();
  return result;
}
export async function loadQuarters(signal: AbortSignal): Promise<Quarter[]> {
  const data = await get('quarters', {}, signal);
  const quarters = list(data.quarters, 120).map((item) => {
    const row = record(item);
    return {
      ...source(row),
      period: period(row.period),
      metadata_modified: revision(row.metadata_modified),
    };
  });
  unique(quarters.map((row) => row.period));
  return quarters.sort((a, b) => b.period.localeCompare(a.period));
}
export async function loadMarketers(
  selectedPeriod: string,
  signal: AbortSignal,
  community: string | null = null,
): Promise<Marketer[]> {
  const result: Marketer[] = [];
  for (let offset = 0; offset <= 10_000; offset += 100) {
    const data = await get(
      'shares',
      {
        period: selectedPeriod,
        limit: 100,
        offset,
        ...(community ? { community_code: community } : {}),
      },
      signal,
    );
    if (data.period !== selectedPeriod || data.community_code !== community)
      fail();
    const page = list(data.items, 100).map((item) => {
      const row = record(item);
      const code = text(row.marketer_code);
      if (!validMarketer(code)) fail();
      return {
        marketer_code: code,
        observed_name:
          row.observed_name === null ? null : text(row.observed_name),
        supplies: count(row.supplies),
      };
    });
    result.push(...page);
    if (page.length < 100) {
      unique(result.map((row) => row.marketer_code));
      return result;
    }
  }
  return fail();
}
export async function loadCommunities(
  code: string,
  selectedPeriod: string,
  signal: AbortSignal,
): Promise<Communities> {
  const data = await get(
    `communities/${encodeURIComponent(code)}`,
    { period: selectedPeriod },
    signal,
  );
  if (
    data.period !== selectedPeriod ||
    data.marketer_code !== code ||
    data.denominator !== 'supplies_with_registered_marketer'
  )
    fail();
  const items = list(data.items, 19).map((item) => {
    const row = record(item);
    const community_code = text(row.community_code);
    if (!/^(0[1-9]|1[0-9])$/.test(community_code)) fail();
    const supplies = count(row.supplies);
    const marketer_supplies = count(row.marketer_supplies);
    const share = row.share;
    if (
      supplies > marketer_supplies ||
      (marketer_supplies === 0
        ? share !== null
        : typeof share !== 'number' ||
          !Number.isFinite(share) ||
          Math.abs(share - supplies / marketer_supplies) > 1e-9)
    )
      fail();
    return {
      community_code,
      supplies,
      marketer_supplies,
      share: share as number | null,
      direct_consumer_supplies: count(row.direct_consumer_supplies),
      unavailable_supplies: count(row.unavailable_supplies),
    };
  });
  unique(items.map((row) => row.community_code));
  return {
    ...source(data),
    period: selectedPeriod,
    marketer_code: code,
    metadata_modified: revision(data.metadata_modified),
    items,
  };
}
export async function loadSupplies(
  code: string,
  community: string | null,
  signal: AbortSignal,
): Promise<SuppliesSeries> {
  const data = await get(
    `series/${encodeURIComponent(code)}`,
    community ? { community_code: community } : {},
    signal,
  );
  if (data.marketer_code !== code || data.community_code !== community) fail();
  const series = list(data.series, 120)
    .map((item) => {
      const row = record(item);
      return {
        period: period(row.period),
        supplies: count(row.supplies),
        metadata_modified: revision(row.metadata_modified),
      };
    })
    .sort((a, b) => a.period.localeCompare(b.period));
  unique(series.map((row) => row.period));
  return {
    ...source(data),
    marketer_code: code,
    community_code: community,
    series,
  };
}
