import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { httpClient } from '../../api/http-client';
import { loadReferenceMarketers } from './load-reference-marketers';

const response = {
  sector: 'electricity',
  scope: 'reference_marketers',
  snapshot_date: '2026-10-04',
  designation_source_url: 'https://www.cnmc.es/cor',
  code_source_url: 'https://data.cnmc.es/market',
  code_source_period: '2025T4',
  code_source_metadata_modified: '2026-09-16T09:54:27.287603',
  attribution: 'Origen de los datos: Comisión Nacional de los Mercados y la Competencia',
  items: [
    { marketer_code: 'R2-292', name: 'Empresa de prueba', territorial_limit: null },
    { marketer_code: 'R2-530', name: 'Empresa de Ceuta', territorial_limit: 'ceuta' },
  ],
};
const originalAdapter = httpClient.defaults.adapter;
const signal = () => new AbortController().signal;

beforeEach(() => {
  httpClient.defaults.adapter = async (config) => ({
    data: JSON.stringify(response), status: 200, statusText: 'OK', headers: {}, config,
  });
});
afterEach(() => { httpClient.defaults.adapter = originalAdapter; });

describe('reference marketer catalog contract', () => {
  it('requests the electricity snapshot and keeps explicit limits separate', async () => {
    const data = await loadReferenceMarketers(signal());
    expect(data.items).toEqual(response.items);
    expect(data.snapshot_date).toBe('2026-10-04');
    expect(data.designation_source_url).toBe('https://www.cnmc.es/cor');
  });

  it.each([
    { ...response, sector: 'gas' },
    { ...response, items: [...response.items, response.items[0]] },
    { ...response, items: [{ ...response.items[0], territorial_limit: 'madrid' }] },
    { ...response, designation_source_url: 'javascript:alert(1)' },
    { ...response, snapshot_date: '2026-02-30' },
    { ...response, code_source_metadata_modified: '2026-10-05T00:00:00' },
  ])('rejects malformed or unsupported metadata', async (payload) => {
    httpClient.defaults.adapter = async (config) => ({
      data: JSON.stringify(payload), status: 200, statusText: 'OK', headers: {}, config,
    });
    await expect(loadReferenceMarketers(signal())).rejects.toThrow();
  });

  it('rejects an oversized body before parsing it', async () => {
    httpClient.defaults.adapter = async (config) => ({
      data: ' '.repeat(32_001), status: 200, statusText: 'OK', headers: {}, config,
    });
    await expect(loadReferenceMarketers(signal())).rejects.toThrow('Respuesta del catálogo');
  });
});
