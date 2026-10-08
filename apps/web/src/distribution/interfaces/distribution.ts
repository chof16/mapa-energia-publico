export interface CoverageEvidence {
  source_title: string;
  source_url: string;
  published_on: string | null;
  checked_on: string;
  geographic_claim: string;
  confidence: 'official_document' | 'group_first_party_reported' | 'other_operator_reported';
}

export interface AssociationEvidence {
  source_title: string;
  source_url: string;
  published_on: string | null;
  checked_on: string;
  relationship_claim: string;
}

export interface CorporateGroupAssociation {
  group_name: string;
  evidence: AssociationEvidence;
}

export interface DistributorPresence {
  distributor_code: string;
  distributor_name: string;
  registry_source_url: string;
  evidence: CoverageEvidence;
  corporate_group: CorporateGroupAssociation | null;
}

export interface ProvincePresence {
  sector: 'electricity';
  province_code: string;
  snapshot_date: string;
  scope: 'provincial_presence';
  complete: false;
  items: DistributorPresence[];
}

export interface ProvincePresenceSummary {
  sector: 'electricity';
  snapshot_date: string;
  scope: 'documented_provincial_presence';
  complete: false;
  items: {
    province_code: string;
    documented_distributor_count: number;
  }[];
}
