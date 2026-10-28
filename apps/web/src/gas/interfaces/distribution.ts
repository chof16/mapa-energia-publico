export interface GasNetworkSource {
  load_id: string;
  period: string;
  source_url: string;
  download_url: string;
  source_title: string;
  published_on: string;
  retrieved_at: string;
  source_sha256: string;
  row_count: number;
  reuse_status: 'review_pending';
  attribution: string;
  confidence: 'official_document';
  network_scope: 'natural_gas_at_most_4_bar';
}

export interface GasNetworkPage<T> {
  sector: 'gas';
  scope: 'documented_provincial_presence';
  complete: false;
  source: GasNetworkSource;
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface GasNetworkProvince {
  province_code: string;
  documented_distributor_count: number;
  source_row_count: number;
  supply_points: number;
}

export interface GasNetworkDistributor {
  distributor_name: string;
  source_row_count: number;
  supply_points: number;
}

export type GasNetworkProvinces = GasNetworkPage<GasNetworkProvince>;
export type GasNetworkDistributors = GasNetworkPage<GasNetworkDistributor> & { province_code: string };
