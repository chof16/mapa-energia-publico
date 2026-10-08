import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { httpClient } from '../../api/http-client';
import { loadProvinceSummary } from './load-province-summary';

const valid = {
  sector: 'electricity', snapshot_date: '2026-10-04',
  scope: 'documented_provincial_presence', complete: false,
  items: [
    { province_code: '24', documented_distributor_count: 3 },
    { province_code: '46', documented_distributor_count: 1 },
  ],
};
const originalAdapter = httpClient.defaults.adapter;
const adapter = vi.fn(async (config) => ({
  data: JSON.stringify(valid), status: 200, statusText: 'OK', headers: {}, config,
}));

beforeEach(() => { adapter.mockClear(); httpClient.defaults.adapter = adapter; });
afterEach(() => { httpClient.defaults.adapter = originalAdapter; });

describe('provincial map summary contract', () => {
  it('loads positive counts with cancellation and no quarter parameter', async () => {
    const signal = new AbortController().signal;
    expect((await loadProvinceSummary(signal)).items).toEqual(valid.items);
    expect(adapter).toHaveBeenCalledWith(expect.objectContaining({
      url: '/v1/distribution/provinces',
      params: { sector: 'electricity' },
      signal,
    }));
  });

  it.each([
    { ...valid, complete: true },
    { ...valid, sector: 'gas' },
    { ...valid, items: [...valid.items, valid.items[0]] },
    { ...valid, items: [{ province_code: '50', documented_distributor_count: 0 }] },
    { ...valid, items: [{ province_code: '53', documented_distributor_count: 1 }] },
    { ...valid, snapshot_date: '2026-02-30' },
  ])('rejects a summary that could misstate unknown coverage', async (payload) => {
    httpClient.defaults.adapter = async (config) => ({
      data: JSON.stringify(payload), status: 200, statusText: 'OK', headers: {}, config,
    });
    await expect(loadProvinceSummary(new AbortController().signal)).rejects.toThrow();
  });

  it('rejects oversized text before parsing', async () => {
    httpClient.defaults.adapter = async (config) => ({
      data: ' '.repeat(32_001), status: 200, statusText: 'OK', headers: {}, config,
    });
    await expect(loadProvinceSummary(new AbortController().signal)).rejects.toThrow('Resumen provincial no válido');
  });

  it.each([6, 1_000])('accepts %i distinct distributors per province across 48 documented provinces', async (count) => {
    const items = Array.from({ length: 52 }, (_, index) => String(index + 1).padStart(2, '0'))
      .filter((code) => !['09', '12', '35', '47'].includes(code))
      .map((province_code) => ({ province_code, documented_distributor_count: count }));
    httpClient.defaults.adapter = async (config) => ({
      data: JSON.stringify({ ...valid, items }), status: 200, statusText: 'OK', headers: {}, config,
    });
    const result = await loadProvinceSummary(new AbortController().signal);
    expect(result).toMatchObject({ complete: false, items });
    expect(result.items).toHaveLength(48);
  });

  it.each([-1, 0, 1.5, 1_001, Number.MAX_SAFE_INTEGER + 1, '6', null])('rejects invalid distributor count %s', async (count) => {
    httpClient.defaults.adapter = async (config) => ({
      data: JSON.stringify({ ...valid, items: [{ province_code: '51', documented_distributor_count: count }] }),
      status: 200, statusText: 'OK', headers: {}, config,
    });
    await expect(loadProvinceSummary(new AbortController().signal)).rejects.toThrow('Resumen provincial no válido');
  });

  it.each(['x', 'ñ'])('rejects otherwise valid JSON above the byte budget (%s padding)', async (character) => {
    const body = JSON.stringify({ ...valid, padding: character.repeat(character === 'x' ? 32_000 : 16_000) });
    expect(new TextEncoder().encode(body).length).toBeGreaterThan(32_000);
    if (character === 'ñ') expect(body.length).toBeLessThan(32_000);
    httpClient.defaults.adapter = async (config) => ({
      data: body, status: 200, statusText: 'OK', headers: {}, config,
    });
    await expect(loadProvinceSummary(new AbortController().signal)).rejects.toThrow('Resumen provincial no válido');
  });
});
