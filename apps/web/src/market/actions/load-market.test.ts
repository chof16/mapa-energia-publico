import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { httpClient } from '../../api/http-client';
import { marketResponse } from '../../test/fixtures/market';
import {
  loadCommunities,
  loadMarketers,
  loadQuarters,
  loadShareSeries,
  loadSupplies,
} from './load-market';

const originalAdapter = httpClient.defaults.adapter;
const signal = () => new AbortController().signal;
beforeEach(() => {
  httpClient.defaults.adapter = async (config) => ({
    data: JSON.stringify(marketResponse(config.url!, config.params)),
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  });
});
afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

describe('read-only market contracts', () => {
  it('pages beyond the first hundred registered codes and preserves cancellation', async () => {
    const abort = signal();
    const adapter = vi.fn(async (config) => ({
      data: JSON.stringify({
        sector: 'electricity',
        period: '2025T4',
        community_code: null,
        items: Array.from(
          { length: config.params.offset === 0 ? 100 : 1 },
          (_, index) => ({
            marketer_code: `R2-${index + config.params.offset + 1}`,
            observed_name: 'Prueba',
            supplies: 1,
          }),
        ),
      }),
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }));
    httpClient.defaults.adapter = adapter;
    expect(await loadMarketers('2025T4', abort)).toHaveLength(101);
    expect(adapter).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        signal: abort,
        params: {
          sector: 'electricity',
          period: '2025T4',
          limit: 100,
          offset: 100,
        },
      }),
    );
  });
  it('keeps registered codes whose source name is absent in early quarters', async () => {
    httpClient.defaults.adapter = async (config) => ({
      data: JSON.stringify({
        sector: 'electricity',
        period: '2011T1',
        community_code: null,
        items: [
          { marketer_code: 'R2-284', observed_name: null, supplies: 342_547 },
        ],
      }),
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    });
    await expect(loadMarketers('2011T1', signal())).resolves.toEqual([
      { marketer_code: 'R2-284', observed_name: null, supplies: 342_547 },
    ]);
  });
  it('preserves zero and null separately in community and share-series responses', async () => {
    const communities = await loadCommunities('R2-001', '2025T4', signal());
    expect(communities.items.map((item) => item.share)).toEqual([0, null]);
    expect(
      (await loadShareSeries('R2-001', null, signal())).series.map(
        (item) => item.share,
      ),
    ).toEqual([0.25, null, 0]);
    expect(
      (await loadSupplies('R2-001', null, signal())).series.map(
        (item) => item.period,
      ),
    ).toEqual(['2025T1', '2025T4']);
  });
  it.each([
    'null-with-denominator',
    'zero-without-denominator',
    'wrong-period',
    'duplicate-community',
  ])('rejects an inconsistent response: %s', async (scenario) => {
    httpClient.defaults.adapter = async (config) => {
      const data = marketResponse(config.url!, config.params) as {
        items: { share: number | null }[];
        period: string;
      };
      if (scenario === 'null-with-denominator') data.items[0]!.share = null;
      if (scenario === 'zero-without-denominator') data.items[1]!.share = 0;
      if (scenario === 'wrong-period') data.period = '2025T1';
      if (scenario === 'duplicate-community') data.items.push(data.items[0]!);
      return {
        data: JSON.stringify(data),
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      };
    };
    await expect(loadCommunities('R2-001', '2025T4', signal())).rejects.toThrow(
      'Respuesta de mercado no válida',
    );
  });
  it('rejects oversized JSON before parsing and rejects malformed payloads', async () => {
    httpClient.defaults.adapter = async (config) => ({
      data: ' '.repeat(1_000_001),
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    });
    await expect(loadQuarters(signal())).rejects.toThrow(
      'Respuesta de mercado no válida',
    );
    httpClient.defaults.adapter = async (config) => ({
      data: '<html>Error</html>',
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    });
    await expect(loadQuarters(signal())).rejects.toThrow();
  });
  it('passes through API availability and quota errors without automatic requests', async () => {
    const adapter = vi.fn(async (config) => {
      throw new AxiosError(
        'Unavailable',
        'ERR_BAD_RESPONSE',
        config,
        undefined,
        {
          data: {},
          status: 503,
          statusText: 'Unavailable',
          headers: {},
          config,
        },
      );
    });
    httpClient.defaults.adapter = adapter;
    await expect(loadQuarters(signal())).rejects.toMatchObject({
      response: { status: 503 },
    });
    expect(adapter).toHaveBeenCalledTimes(1);
  });
});
