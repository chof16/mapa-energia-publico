import type { GasAuditStatus, GasPoint, GasSeriesValue } from '../interfaces/retail';

export const gasScopeLabels = { whole_market: 'Mercado completo', liberalised: 'Mercado liberalizado', regulated: 'Mercado regulado' };
export const gasAuditLabels: Record<GasAuditStatus, string> = { reviewed: 'Revisado', partial: 'Revisión parcial', located: 'Informe localizado, valores pendientes', not_reviewed: 'Sin revisar', unavailable: 'Tabla no disponible', source_error: 'Defecto en la fuente' };
export const gasQuarter = (period: string) => `T${period.at(-1)} ${period.slice(0, 4)}`;
export const gasNumber = (value: string) => Number(value).toLocaleString('es-ES', { maximumFractionDigits: 6 });
const denominatorLabels = { matched: 'Valor no exacto', missing: 'Sin total explícito', ambiguous: 'Total ambiguo', unavailable: 'Total no disponible', zero: 'Total igual a cero', inconsistent: 'Valor superior al total' };
export function gasValueLabel(record: GasSeriesValue, share: boolean): string {
  if (share) return record.share !== null ? `${(Number(record.share) * 100).toLocaleString('es-ES', { maximumFractionDigits: 4 })} %` : `Sin cuota · ${denominatorLabels[record.denominator_status]}`;
  const unit = record.unit === 'clients' ? 'clientes' : 'MWh';
  if (record.status === 'bounded' && record.upper_bound !== null) return `<${gasNumber(record.upper_bound)} ${unit}`;
  if (record.value !== null && ['exact', 'zero'].includes(record.status)) return `${gasNumber(record.value)} ${unit}`;
  return { missing: 'Sin observación', suppressed: 'Dato suprimido', source_error: 'Defecto en la fuente', exact: 'Sin observación', zero: 'Sin observación', bounded: 'Límite no disponible' }[record.status];
}
export function gasPointLabel(point: GasPoint | undefined, share: boolean): string {
  if (!point) return 'Sin observación';
  if (!point.records.length) return point.audit.status === 'reviewed' ? 'Sin observación' : gasAuditLabels[point.audit.status];
  return point.records.map((r) => gasValueLabel(r, share)).join(' · ');
}
export function gasChartValue(point: GasPoint | undefined, share: boolean): number | null {
  if (!point || point.records.length !== 1) return null;
  const record = point.records[0];
  if (record.source_audit ? record.source_audit.status !== 'reviewed' || record.source_audit.table_review_status !== 'reviewed' || record.source_audit.retailer_coverage !== 'reviewed' : point.audit.status !== 'reviewed' || point.availability !== 'reviewed') return null;
  if (record.review_status && record.review_status !== 'reviewed') return null;
  if (!['exact', 'zero'].includes(record.status)) return null;
  const value = share ? record.share : record.value;
  return value === null ? null : Number(value);
}
