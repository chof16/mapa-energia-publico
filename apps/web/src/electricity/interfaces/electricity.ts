export interface Source {
  source_url: string;
  attribution: string;
  license_id: string;
  license_url: string;
  conditions_url: string;
}
export interface Quarter extends Source {
  period: string;
  metadata_modified: string;
}
export interface Marketer {
  marketer_code: string;
  observed_name: string | null;
  supplies: number;
}
export interface CommunityShare {
  community_code: string;
  supplies: number;
  marketer_supplies: number;
  direct_consumer_supplies: number;
  unavailable_supplies: number;
  share: number | null;
}
export interface Communities extends Source {
  period: string;
  marketer_code: string;
  metadata_modified: string;
  items: CommunityShare[];
}
export interface SuppliesSeries extends Source {
  marketer_code: string;
  community_code: string | null;
  series: { period: string; supplies: number; metadata_modified: string }[];
}
export interface ShareSeries {
  series: (CommunityShare & Quarter)[];
}
