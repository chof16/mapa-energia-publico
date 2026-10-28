import { afterEach, describe, expect, it, vi } from 'vitest';
import { httpClient } from '../../api/http-client';
import { gasDistributionResponse, gasNetworkSource } from '../../test/fixtures/gas-distribution';
import { loadGasNetworkDistributors, loadGasNetworkProvinces } from './load-gas-distribution';

afterEach(() => vi.restoreAllMocks());

describe('gas territorial response validation', () => {
  it.each([
    '<html>Unexpected content</html>',
    JSON.stringify({ ...gasDistributionResponse('/provinces'), total: 3 }),
    JSON.stringify({ ...gasDistributionResponse('/provinces'), complete: true }),
    JSON.stringify({ ...gasDistributionResponse('/provinces'), source: { ...gasNetworkSource, period: '2019-13' } }),
    JSON.stringify({ ...gasDistributionResponse('/provinces'), source: { ...gasNetworkSource, source_url: 'javascript:alert(1)' } }),
    JSON.stringify({ ...gasDistributionResponse('/provinces'), items: [{ province_code: '1', documented_distributor_count: 1 }] }),
  ])('rejects malformed or incomplete map data', async (body) => {
    vi.spyOn(httpClient, 'get').mockResolvedValue({ data: body });
    await expect(loadGasNetworkProvinces(new AbortController().signal)).rejects.toThrow();
  });

  it('rejects a detail from a different province or source revision', async () => {
    vi.spyOn(httpClient, 'get').mockResolvedValue({ data: JSON.stringify(gasDistributionResponse('/provinces/28')) });
    await expect(loadGasNetworkDistributors('35', gasNetworkSource.load_id, new AbortController().signal)).rejects.toThrow();
    await expect(loadGasNetworkDistributors('28', 'a'.repeat(64), new AbortController().signal)).rejects.toThrow();
  });
});
