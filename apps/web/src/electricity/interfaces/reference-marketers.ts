export interface ReferenceMarketer {
  marketer_code: string;
  name: string;
  territorial_limit: 'ceuta' | 'melilla' | null;
}

export interface ReferenceMarketers {
  sector: 'electricity';
  scope: 'reference_marketers';
  snapshot_date: string;
  designation_source_url: string;
  code_source_url: string;
  code_source_period: string;
  code_source_metadata_modified: string;
  attribution: string;
  items: ReferenceMarketer[];
}
