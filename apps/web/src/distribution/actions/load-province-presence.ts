import { httpClient } from '../../api/http-client';
import type { AssociationEvidence, CoverageEvidence, ProvincePresence } from '../interfaces/distribution';
import { MAX_PROVINCIAL_DISTRIBUTORS } from '../lib/validation-limits';

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const fail = (): never => { throw new Error('Respuesta provincial no válida'); };

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : fail();
}

function text(value: unknown, max = 4000): string {
  return typeof value === 'string' && !!value.trim() && value.length <= max
    ? value : fail();
}

function url(value: unknown): string {
  const result = text(value, 2000);
  try {
    const parsed = new URL(result);
    if (parsed.protocol === 'https:' || parsed.protocol === 'http:') return result;
  } catch { /* Invalid links fail the response. */ }
  return fail();
}

function date(value: unknown): string {
  const result = text(value, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(result)) fail();
  const parsed = new Date(`${result}T00:00:00Z`);
  return parsed.toISOString().slice(0, 10) === result ? result : fail();
}

function evidence(value: unknown): CoverageEvidence {
  const row = record(value);
  const confidence = row.confidence;
  if (
    confidence !== 'official_document' &&
    confidence !== 'group_first_party_reported' &&
    confidence !== 'other_operator_reported'
  ) return fail();
  const published_on = row.published_on === null ? null : date(row.published_on);
  const checked_on = date(row.checked_on);
  if (published_on && published_on > checked_on) fail();
  return {
    source_title: text(row.source_title, 500),
    source_url: url(row.source_url),
    published_on,
    checked_on,
    geographic_claim: text(row.geographic_claim),
    confidence,
  };
}

function associationEvidence(value: unknown, snapshotDate: string): AssociationEvidence {
  const row = record(value);
  const published_on = row.published_on === null ? null : date(row.published_on);
  const checked_on = date(row.checked_on);
  if ((published_on && published_on > checked_on) || checked_on > snapshotDate) fail();
  return {
    source_title: text(row.source_title, 500),
    source_url: url(row.source_url),
    published_on,
    checked_on,
    relationship_claim: text(row.relationship_claim),
  };
}

export async function loadProvincePresence(
  provinceCode: string,
  signal: AbortSignal,
): Promise<ProvincePresence> {
  if (!/^(0[1-9]|[1-4][0-9]|5[0-2])$/.test(provinceCode)) fail();
  const response = await httpClient.get(`${apiBase}/v1/distribution/provinces/${provinceCode}`, {
    params: { sector: 'electricity' },
    signal,
    responseType: 'text',
    transformResponse: [(data: unknown) => data],
  });
  const body: unknown = response.data;
  if (
    typeof body !== 'string' ||
    body.length > 32_000 ||
    new TextEncoder().encode(body).length > 32_000
  ) return fail();
  let parsed: unknown;
  try { parsed = JSON.parse(body); } catch { return fail(); }
  const data = record(parsed);
  if (
    data.sector !== 'electricity' ||
    data.province_code !== provinceCode ||
    data.scope !== 'provincial_presence' ||
    data.complete !== false ||
    !Array.isArray(data.items) ||
    data.items.length > MAX_PROVINCIAL_DISTRIBUTORS
  ) return fail();
  const snapshot_date = date(data.snapshot_date);
  const codes = new Set<string>();
  const items = data.items.map((value: unknown) => {
    const row = record(value);
    const distributor_code = text(row.distributor_code, 20);
    if (!/^R1-\d{3}$/.test(distributor_code) || codes.has(distributor_code)) fail();
    codes.add(distributor_code);
    // COR data is outside this view; validate its shape before accepting the payload.
    if (row.cor !== null) {
      const cor = record(row.cor);
      if (!/^R2-\d{3}$/.test(text(cor.marketer_code, 20))) fail();
      text(cor.marketer_name, 500);
      associationEvidence(cor.evidence, snapshot_date);
    }
    const corporate_group = row.corporate_group === null ? null : (() => {
      const group = record(row.corporate_group);
      return {
        group_name: text(group.group_name, 500),
        evidence: associationEvidence(group.evidence, snapshot_date),
      };
    })();
    const itemEvidence = evidence(row.evidence);
    if (itemEvidence.checked_on > snapshot_date) fail();
    return {
      distributor_code,
      distributor_name: text(row.distributor_name, 500),
      registry_source_url: url(row.registry_source_url),
      evidence: itemEvidence,
      corporate_group,
    };
  });
  return { sector: 'electricity', province_code: provinceCode, scope: 'provincial_presence', complete: false, snapshot_date, items };
}
