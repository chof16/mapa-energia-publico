import type { GasAudit, GasContext, GasCoverage, GasMarketer, GasObservation, GasPeriod, GasPoint, GasReference, GasRevision, GasSeriesValue, GasSource, GasSourceAudit, GasUnresolvedObservation, GasValue } from '../interfaces/retail';

export const invalidGas = (): never => { throw new Error('La respuesta minorista de gas no cumple el contrato esperado.'); };
export const object = (v: unknown): Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : invalidGas();
export const string = (v: unknown, max = 4000): string => typeof v === 'string' && v.length <= max ? v : invalidGas();
export const integer = (v: unknown, max = 100_000): number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0 && v <= max ? v : invalidGas();
export function choice<T extends string | boolean>(v: unknown, values: readonly T[]): T { return values.includes(v as T) ? v as T : invalidGas(); }
export function array<T>(v: unknown, max: number, parse: (v: unknown) => T): T[] { return Array.isArray(v) && v.length <= max ? v.map(parse) : invalidGas(); }
export function pattern(v: unknown, regex: RegExp, max: number) { const result = string(v, max); return regex.test(result) ? result : invalidGas(); }
export const gasId = (v: unknown) => pattern(v, /^gas-[a-z0-9-]{1,75}$/, 79);
export const gasHash = (v: unknown) => pattern(v, /^[a-f0-9]{64}$/, 64);
export const gasPeriod = (v: unknown) => pattern(v, /^20\d{2}T[1-4]$/, 6);
const metric = (v: unknown) => choice(v, ['clients', 'sales'] as const);
const scope = (v: unknown) => choice(v, ['whole_market', 'liberalised', 'regulated'] as const);
const status = (v: unknown) => choice(v, ['exact', 'zero', 'missing', 'suppressed', 'source_error', 'bounded'] as const);
const auditStatus = (v: unknown) => choice(v, ['not_reviewed', 'located', 'partial', 'reviewed', 'unavailable', 'source_error'] as const);
const cellReview = (v: unknown) => choice(v, ['reviewed', 'partial', 'source_error'] as const);
export const gasIdentityStatus = (v: unknown) => choice(v ?? 'legacy_unspecified', ['reviewed_identity', 'source_local_identity', 'legacy_unspecified'] as const);
const unit = (v: unknown) => choice(v, ['clients', 'MWh', 'GWh', 'kWh'] as const);
const month = (v: unknown) => pattern(v, /^20\d{2}-(0[1-9]|1[0-2])$/, 7);
function date(v: unknown) {
  const result = pattern(v, /^\d{4}-\d{2}-\d{2}$/, 10);
  const parsed = new Date(result);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === result ? result : invalidGas();
}
function url(v: unknown) {
  const result = string(v, 2000);
  try { const parsed = new URL(result); if (parsed.protocol === 'https:' && !parsed.username && !parsed.password) return result; } catch { /* Reject unsafe source links. */ }
  return invalidGas();
}
function auditUrl(v: unknown) { return pattern(v, /^\/v1\/gas\/retail\/periods\?[a-zA-Z0-9_=&%.-]+$/, 2000); }
function decimal(v: unknown): string | null {
  if (v === null) return null;
  const result = pattern(v, /^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/, 100);
  return Number.isFinite(Number(result)) && Number(result) >= 0 ? result : invalidGas();
}
export function gasSource(v: unknown): GasSource {
  const r = object(v);
  return { source_id: string(r.source_id, 160), url: url(r.url), title: string(r.title, 1000), publisher: string(r.publisher, 300),
    published_on: r.published_on === null ? null : date(r.published_on), retrieved_on: date(r.retrieved_on), sha256: gasHash(r.sha256),
    media_type: choice(r.media_type, ['pdf', 'html']), page_count: integer(r.page_count, 200), reuse_status: choice(r.reuse_status, ['review_pending']), notes: string(r.notes, 10_000) };
}
export function gasRevision(v: unknown): GasRevision {
  const r = object(v), imported = string(r.imported_at, 60);
  if (!Number.isFinite(Date.parse(imported))) invalidGas();
  return { load_id: gasHash(r.load_id), reviewed_on: date(r.reviewed_on), imported_at: imported, complete: choice(r.complete, [false]), reuse_status: choice(r.reuse_status, ['review_pending']) };
}
export function gasContext(v: unknown): GasContext {
  const r = object(v);
  return { sector: choice(r.sector, ['gas']), complete: choice(r.complete, [false]), revision: gasRevision(r.revision),
    geographic_scope: choice(r.geographic_scope, ['source_defined']), geographic_note: string(r.geographic_note), identity_note: string(r.identity_note) };
}
export function gasAudit(v: unknown): GasAudit {
  const r = object(v);
  return { period: gasPeriod(r.period), metric: metric(r.metric), status: auditStatus(r.status), pages: array(r.pages, 200, (x) => integer(x, 200)), sources: array(r.sources, 10, gasSource), note: string(r.note, 10_000) };
}
export function gasPeriodItem(v: unknown): GasPeriod {
  const r = object(v), audit = gasAudit(r.audit), source_audits = sourceAudits(r.source_audits, audit);
  return { audit, source_audits, scope: scope(r.scope), reviewed_retailer_count: integer(r.reviewed_retailer_count) };
}
export function gasMarketer(v: unknown): GasMarketer {
  const r = object(v), identity_status = gasIdentityStatus(r.identity_status);
  if (identity_status === 'source_local_identity') invalidGas();
  return { marketer_id: gasId(r.marketer_id), company_name: string(r.company_name, 500), observed_name: string(r.observed_name, 500), source: gasSource(r.source), mapping_review_note: string(r.mapping_review_note), identity_review_note: string(r.identity_review_note ?? ''), identity_status };
}
function sourceAudit(v: unknown): GasSourceAudit {
  const r = object(v);
  return { source: gasSource(r.source), period: gasPeriod(r.period), metric: metric(r.metric), status: auditStatus(r.status),
    table_review_status: choice(r.table_review_status, ['reviewed', 'partial', 'unavailable', 'not_reviewed', 'source_error']),
    retailer_coverage: choice(r.retailer_coverage, ['reviewed', 'partial', 'unknown', 'unavailable_in_table']),
    geographic_scope: string(r.geographic_scope), pages: array(r.pages, 200, (p) => integer(p, 200)), note: string(r.note, 10_000) };
}
function sourceAudits(v: unknown, audit: GasAudit) {
  const result = array(v ?? [], 10, sourceAudit);
  if (result.some((a) => a.period !== audit.period || a.metric !== audit.metric) || new Set(result.map((a) => a.source.source_id)).size !== result.length) invalidGas();
  return result;
}
function observation(v: unknown): GasObservation {
  const r = object(v), page = integer(r.page, 200);
  if (page === 0) invalidGas();
  const result: GasObservation = { observation_id: string(r.observation_id, 160), mapping_id: string(r.mapping_id, 160), observed_name: string(r.observed_name, 500), mapping_review_note: string(r.mapping_review_note), month: month(r.month), metric: metric(r.metric), scope: scope(r.scope), unit: unit(r.unit), page, table_label: string(r.table_label), source_row: string(r.source_row), raw_value: string(r.raw_value, 500), status: status(r.status), value: decimal(r.value), upper_bound: decimal(r.upper_bound), upper_bound_exclusive: choice(r.upper_bound_exclusive, [true]), review_note: string(r.review_note), original_unit: string(r.original_unit, 100), review_status: cellReview(r.review_status), publication_status: choice(r.publication_status, ['reviewed', 'source_error']) };
  if (result.review_status === 'partial' || ((result.review_status !== 'reviewed' || result.publication_status !== 'reviewed') && (result.value !== null || result.upper_bound !== null))) invalidGas();
  return result;
}
function unresolvedObservation(v: unknown): GasUnresolvedObservation {
  const r = object(v);
  if (r.month !== null || r.value !== null || r.upper_bound !== null || r.status !== 'source_error') invalidGas();
  const { publication_status: _publication, upper_bound_exclusive: _exclusive, ...base } = observation({ ...r, month: '2000-01', publication_status: 'source_error', upper_bound_exclusive: true });
  return { ...base, month: null, period: gasPeriod(r.period), status: 'source_error', value: null, upper_bound: null };
}
function value(v: unknown): GasValue {
  const r = object(v);
  const result: GasValue = { gas_id: gasId(r.gas_id), source: gasSource(r.source), period: gasPeriod(r.period), metric: metric(r.metric), scope: scope(r.scope), status: status(r.status), unit: choice(r.unit, ['clients', 'MWh']), value: decimal(r.value), upper_bound: decimal(r.upper_bound), upper_bound_exclusive: choice(r.upper_bound_exclusive, [true]), original_unit: unit(r.original_unit), original_value: decimal(r.original_value), original_upper_bound: decimal(r.original_upper_bound), missing_months: array(r.missing_months, 3, month), input_statuses: array(r.input_statuses, 100, status), observations: array(r.observations, 100, observation),
    source_audit: r.source_audit == null ? null : sourceAudit(r.source_audit), review_status: cellReview(r.review_status ?? 'reviewed'), withheld_observation_ids: array(r.withheld_observation_ids ?? [], 100, (v) => string(v, 160)), unresolved_observations: array(r.unresolved_observations ?? [], 100, unresolvedObservation) };
  if (result.unit !== (result.metric === 'clients' ? 'clients' : 'MWh') ||
      (['exact', 'zero'].includes(result.status) ? result.value === null : result.value !== null) ||
      (result.status === 'zero' && Number(result.value) !== 0) ||
      (result.status === 'bounded' && result.upper_bound === null) ||
      [...result.observations, ...result.unresolved_observations!].some((o) => o.metric !== result.metric || o.scope !== result.scope)) invalidGas();
  const a = result.source_audit;
  if (a && (a.period !== result.period || a.metric !== result.metric || a.source.source_id !== result.source.source_id || a.source.sha256 !== result.source.sha256)) invalidGas();
  if ((result.review_status !== 'reviewed' || (a && (a.status !== 'reviewed' || a.table_review_status !== 'reviewed' || a.retailer_coverage !== 'reviewed'))) &&
      [result.value, result.upper_bound, result.original_value, result.original_upper_bound].some((v) => v !== null)) invalidGas();
  if ((result.withheld_observation_ids!.length || result.unresolved_observations!.length) && ['exact', 'zero', 'bounded'].includes(result.status)) invalidGas();
  if (['exact', 'zero', 'bounded'].includes(result.status) && result.observations.some((o) => o.review_status !== 'reviewed' || o.publication_status !== 'reviewed')) invalidGas();
  return result;
}
function seriesValue(v: unknown): GasSeriesValue {
  const r = object(v), base = value(v);
  const result: GasSeriesValue = { ...base, denominator: r.denominator === null ? null : value(r.denominator), denominator_status: choice(r.denominator_status, ['matched', 'missing', 'ambiguous', 'unavailable', 'zero', 'inconsistent']), share: decimal(r.share) };
  if (result.share !== null && (Number(result.share) > 1 || !['exact', 'zero'].includes(result.status) || result.denominator_status !== 'matched' || !result.denominator || Number(result.denominator.value) <= 0)) invalidGas();
  if (result.denominator && (result.denominator.metric !== result.metric || result.denominator.scope !== result.scope || result.denominator.period !== result.period || result.denominator.source.source_id !== result.source.source_id)) invalidGas();
  return result;
}
export function gasPoint(v: unknown): GasPoint {
  const r = object(v), audit = gasAudit(r.audit), result = { audit, source_audits: sourceAudits(r.source_audits, audit), availability: choice(r.availability, ['reviewed', 'unreviewed', 'unavailable'] as const), records: array(r.records, 100, seriesValue) };
  if (result.records.some((record) => !record.source_audit && (result.audit.status !== 'reviewed' || result.availability !== 'reviewed'))) invalidGas();
  if (result.records.some((x) => x.period !== result.audit.period || x.metric !== result.audit.metric)) invalidGas();
  return result;
}
export function gasCoverage(v: unknown): GasCoverage {
  const r = object(v);
  return { ...gasRevision(r), coverage: array(r.coverage, 2, (v) => { const c = object(v); return { metric: metric(c.metric), counts: array(c.counts, 6, (v) => { const c = object(v); return { status: auditStatus(c.status), periods: integer(c.periods) }; }), audits_url: auditUrl(c.audits_url) }; }),
    issue_count: integer(r.issue_count), issues: array(r.issues, 10, (v) => { const i = object(v); return { period: gasPeriod(i.period), metric: metric(i.metric), status: auditStatus(i.status), note: string(i.note, 10_000), audit_url: auditUrl(i.audit_url) }; }), issues_truncated: choice(r.issues_truncated, [true, false]) };
}
export function gasReference(v: unknown): GasReference {
  const r = object(v); return { marketer_id: gasId(r.marketer_id), observations: array(r.observations, 100, (v) => { const o = object(v); return { observed_name: string(o.observed_name, 500), designation: choice(o.designation, ['gas_cur']), evidence_on: date(o.evidence_on), page: integer(o.page, 200), review_note: string(o.review_note), source: gasSource(o.source) }; }) };
}
