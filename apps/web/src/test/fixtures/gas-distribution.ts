import type { GasNetworkSource } from '../../gas/interfaces/distribution';

export const gasNetworkSource: GasNetworkSource = {
  load_id: 'd'.repeat(64), period: '2019-06', source_url: 'https://example.org/gas-report',
  download_url: 'https://example.org/annex.xlsx', source_title: 'Anexo sintético de redes',
  published_on: '2020-07-29', retrieved_at: '2026-10-27T10:00:00Z', source_sha256: 'd'.repeat(64),
  row_count: 3, reuse_status: 'review_pending', attribution: 'Fuente sintética',
  confidence: 'official_document', network_scope: 'natural_gas_at_most_4_bar',
};

export function gasDistributionResponse(url: string) {
  const common = { sector: 'gas', scope: 'documented_provincial_presence', complete: false,
    source: gasNetworkSource, limit: 100, offset: 0 };
  if (url.endsWith('/provinces')) return { ...common, total: 2, items: [
    { province_code: '28', documented_distributor_count: 2, source_row_count: 2, supply_points: 15 },
    { province_code: '46', documented_distributor_count: 1, source_row_count: 1, supply_points: 0 },
  ] };
  const code = url.split('/').at(-1);
  const items = code === '28' ? [
    { distributor_name: 'Red sintética A SA', source_row_count: 1, supply_points: 15 },
    { distributor_name: 'Red sintética B SA', source_row_count: 1, supply_points: 0 },
  ] : [];
  return { ...common, province_code: code, total: items.length, items };
}
