import type { InternalAxiosRequestConfig } from 'axios';
import { afterEach, expect, it, vi } from 'vitest';
import { httpClient } from '../../api/http-client';
import { loadProvincePresence } from './load-province-presence';

const originalAdapter = httpClient.defaults.adapter;
const valid = {
  sector: 'electricity', province_code: '24', snapshot_date: '2026-10-03',
  scope: 'provincial_presence', complete: false,
  items: [{
    distributor_code: 'R1-002', distributor_name: 'Distribuidora de prueba',
    registry_source_url: 'https://www.boe.es/registro', cor: null,
    corporate_group: {
      group_name: 'Grupo de prueba',
      evidence: {
        source_title: 'Fuente societaria', source_url: 'https://example.org/grupo',
        published_on: null, checked_on: '2026-10-03',
        relationship_claim: 'La distribuidora figura en el grupo.',
      },
    },
    evidence: {
      source_title: 'Documento de prueba', source_url: 'https://www.boe.es/zonas',
      published_on: null, checked_on: '2026-10-03',
      geographic_claim: 'Oeste de la provincia de León.', confidence: 'official_document',
    },
  }],
};

afterEach(() => { httpClient.defaults.adapter = originalAdapter; });

function respond(body: unknown) {
  const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
    data: typeof body === 'string' ? body : JSON.stringify(body),
    status: 200, statusText: 'OK', headers: {}, config,
  }));
  httpClient.defaults.adapter = adapter;
  return adapter;
}

it('loads a bounded, validated provincial presence response', async () => {
  const adapter = respond(valid);
  const result = await loadProvincePresence('24', new AbortController().signal);
  expect(result.items[0].evidence.geographic_claim).toBe('Oeste de la provincia de León.');
  expect(result.items[0].corporate_group?.group_name).toBe('Grupo de prueba');
  expect(adapter).toHaveBeenCalledWith(expect.objectContaining({
    url: '/v1/distribution/provinces/24', params: { sector: 'electricity' }, responseType: 'text',
  }));
});

it.each([
  { ...valid, complete: true },
  { ...valid, province_code: '28' },
  { ...valid, items: [...valid.items, valid.items[0]] },
  { ...valid, items: [{ ...valid.items[0], evidence: { ...valid.items[0].evidence, source_url: 'javascript:alert(1)' } }] },
  { ...valid, items: [{ ...valid.items[0], evidence: { ...valid.items[0].evidence, confidence: 'unverified' } }] },
  { ...valid, items: [{ ...valid.items[0], evidence: { ...valid.items[0].evidence, checked_on: '2026-02-30' } }] },
  { ...valid, items: [{ ...valid.items[0], corporate_group: { ...valid.items[0].corporate_group, evidence: { ...valid.items[0].corporate_group.evidence, source_url: 'javascript:alert(1)' } } }] },
  { ...valid, items: [{ ...valid.items[0], corporate_group: { ...valid.items[0].corporate_group, evidence: { ...valid.items[0].corporate_group.evidence, checked_on: '2026-10-04' } } }] },
  { ...valid, items: [{ ...valid.items[0], corporate_group: undefined }] },
  '<html>not json</html>',
  ' '.repeat(32_001),
])('rejects invalid or oversized API data before use', async (body) => {
  respond(body);
  await expect(loadProvincePresence('24', new AbortController().signal)).rejects.toThrow();
});

it('accepts an empty incomplete list as unknown', async () => {
  respond({ ...valid, items: [] });
  expect((await loadProvincePresence('24', new AbortController().signal)).items).toEqual([]);
});

it('accepts a distributor without a verified group', async () => {
  respond({ ...valid, items: [{ ...valid.items[0], corporate_group: null }] });
  expect((await loadProvincePresence('24', new AbortController().signal)).items[0].corporate_group).toBeNull();
});

it.each(['51', '52'])('accepts more than five distinct distributors, including local operators, in %s', async (provinceCode) => {
  // Synthetic co-presence, not a claim about either city's actual networks.
  const items = ['001', '002', '005', '008', '299', '030', '027'].map((code) => ({
    ...valid.items[0], distributor_code: `R1-${code}`, corporate_group: null,
  }));
  respond({ ...valid, province_code: provinceCode, items });
  const result = await loadProvincePresence(provinceCode, new AbortController().signal);
  expect(result).toMatchObject({
    complete: false, province_code: provinceCode,
    items: items.map(({ distributor_code, corporate_group, evidence }) => ({ distributor_code, corporate_group, evidence })),
  });
});

it('rejects an item count beyond the R1 code space within the byte budget', async () => {
  const body = JSON.stringify({ ...valid, items: Array(1_001).fill(null) });
  expect(new TextEncoder().encode(body).length).toBeLessThan(32_000);
  respond(body);
  await expect(loadProvincePresence('24', new AbortController().signal)).rejects.toThrow('Respuesta provincial no válida');
});

it.each(['duplicate', 'invalid code', 'invalid source'])('still validates every item beyond the fifth: %s', async (invalid) => {
  const items = Array.from({ length: 6 }, (_, index) => ({
    ...valid.items[0], distributor_code: `R1-${String(index).padStart(3, '0')}`,
  }));
  if (invalid === 'duplicate') items[5].distributor_code = items[0].distributor_code;
  if (invalid === 'invalid code') items[5].distributor_code = 'R1-1000';
  if (invalid === 'invalid source') items[5].evidence = { ...items[5].evidence, source_url: 'javascript:alert(1)' };
  respond({ ...valid, items });
  await expect(loadProvincePresence('24', new AbortController().signal)).rejects.toThrow('Respuesta provincial no válida');
});

it.each(['x', 'ñ'])('rejects otherwise valid JSON above the byte budget (%s padding)', async (character) => {
  const body = JSON.stringify({ ...valid, padding: character.repeat(character === 'x' ? 32_000 : 16_000) });
  expect(new TextEncoder().encode(body).length).toBeGreaterThan(32_000);
  if (character === 'ñ') expect(body.length).toBeLessThan(32_000);
  respond(body);
  await expect(loadProvincePresence('24', new AbortController().signal)).rejects.toThrow('Respuesta provincial no válida');
});
