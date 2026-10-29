export type GasMetric = 'clients' | 'sales';
export type GasScope = 'whole_market' | 'liberalised' | 'regulated';
export type GasIdentityStatus = 'reviewed_identity' | 'source_local_identity' | 'legacy_unspecified';
export type GasStatus = 'exact' | 'zero' | 'missing' | 'suppressed' | 'source_error' | 'bounded';
export type GasAuditStatus = 'not_reviewed' | 'located' | 'partial' | 'reviewed' | 'unavailable' | 'source_error';
export interface GasSource {
  source_id: string; url: string; title: string; publisher: string;
  published_on: string | null; retrieved_on: string; sha256: string;
  media_type: 'pdf' | 'html'; page_count: number; reuse_status: 'review_pending'; notes: string;
}
export interface GasRevision {
  load_id: string; reviewed_on: string; imported_at: string; complete: false; reuse_status: 'review_pending';
}
export interface GasAudit {
  period: string; metric: GasMetric; status: GasAuditStatus; pages: number[]; sources: GasSource[]; note: string;
}
export interface GasSourceAudit {
  source: GasSource; period: string; metric: GasMetric; status: GasAuditStatus;
  table_review_status: 'reviewed' | 'partial' | 'unavailable' | 'not_reviewed' | 'source_error';
  retailer_coverage: 'reviewed' | 'partial' | 'unknown' | 'unavailable_in_table';
  geographic_scope: string; pages: number[]; note: string;
}
export interface GasContext {
  sector: 'gas'; complete: false; revision: GasRevision; geographic_scope: 'source_defined';
  geographic_note: string; identity_note: string;
}
export interface GasPage<T> extends GasContext { total: number; limit: number; offset: number; items: T[] }
export interface GasPeriod { audit: GasAudit; scope: GasScope; reviewed_retailer_count: number; source_audits?: GasSourceAudit[] }
export interface GasMarketer { marketer_id: string; company_name: string; observed_name: string; source: GasSource; mapping_review_note: string; identity_review_note?: string; identity_status?: GasIdentityStatus }
export interface GasObservation {
  observation_id: string; mapping_id: string; observed_name: string; mapping_review_note: string;
  month: string; metric: GasMetric; scope: GasScope; unit: 'clients' | 'MWh' | 'GWh' | 'kWh';
  page: number; table_label: string; source_row: string; raw_value: string; status: GasStatus;
  value: string | null; upper_bound: string | null; upper_bound_exclusive: true; review_note: string;
  original_unit: string; review_status: 'reviewed' | 'partial' | 'source_error'; publication_status: 'reviewed' | 'source_error';
}
export interface GasUnresolvedObservation extends Omit<GasObservation, 'month' | 'publication_status' | 'upper_bound_exclusive'> {
  month: null; period: string; status: 'source_error'; value: null; upper_bound: null;
}
export interface GasValue {
  gas_id: string; source: GasSource; period: string; metric: GasMetric; scope: GasScope;
  status: GasStatus; unit: 'clients' | 'MWh'; value: string | null; upper_bound: string | null;
  upper_bound_exclusive: true; original_unit: GasObservation['unit']; original_value: string | null;
  original_upper_bound: string | null; missing_months: string[]; input_statuses: GasStatus[];
  observations: GasObservation[];
  source_audit?: GasSourceAudit | null; review_status?: 'reviewed' | 'partial' | 'source_error';
  withheld_observation_ids?: string[]; unresolved_observations?: GasUnresolvedObservation[];
}
export interface GasSeriesValue extends GasValue {
  denominator: GasValue | null;
  denominator_status: 'matched' | 'missing' | 'ambiguous' | 'unavailable' | 'zero' | 'inconsistent';
  share: string | null;
}
export interface GasPoint { audit: GasAudit; availability: 'reviewed' | 'unreviewed' | 'unavailable'; records: GasSeriesValue[]; source_audits?: GasSourceAudit[] }
export interface GasSeries extends GasPage<GasPoint> { marketer_id: string; company_name: string; identity_review_note?: string; identity_status?: GasIdentityStatus; metric: GasMetric; scope: GasScope }
export interface GasCoverage extends GasRevision {
  coverage: { metric: GasMetric; counts: { status: GasAuditStatus; periods: number }[]; audits_url: string }[];
  issue_count: number;
  issues: { period: string; metric: GasMetric; status: GasAuditStatus; note: string; audit_url: string }[];
  issues_truncated: boolean;
}
export interface GasReference {
  marketer_id: string;
  observations: { observed_name: string; designation: 'gas_cur'; evidence_on: string; page: number; review_note: string; source: GasSource }[];
}
export interface GasFilters {
  metric: GasMetric; scope: GasScope; measure: 'absolute' | 'share'; display: 'chart' | 'table';
  marketer: string; compare: string[]; start_period: string; end_period: string; load_id: string;
}
