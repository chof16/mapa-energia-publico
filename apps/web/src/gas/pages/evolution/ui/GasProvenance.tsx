import type { GasPoint } from '../../../interfaces/retail';
import { GasRetailSource } from '../../../components/GasRetailSource';
import { gasAuditLabels, gasValueLabel } from '../../../lib/retail-format';

export function GasProvenance({ point }: { point: GasPoint }) {
  return <div className="gas-provenance">
    <p>{gasAuditLabels[point.audit.status]} · {point.audit.note}</p>
    {point.source_audits?.length ? point.source_audits.map((audit) => <div key={audit.source.source_id}>
      <p>Revisión de esta fuente: {gasAuditLabels[audit.status]} · Tabla: {gasAuditLabels[audit.table_review_status]} · Geografía de la fuente: {audit.geographic_scope}.</p>
      <p>{audit.note}</p><GasRetailSource source={audit.source} pages={audit.pages} />
    </div>) : point.audit.sources.map((source) => <GasRetailSource key={source.source_id} source={source} pages={point.audit.pages} />)}
    {point.records.map((record, index) => <div key={index}>
      <p>{gasValueLabel(record, false)} · {gasValueLabel(record, true)}</p>
      <p>Fuente del registro: {record.source.title}. Revisión de celdas: {gasAuditLabels[record.review_status ?? 'reviewed']}.</p>
      <p>Unidad original: {record.original_unit}. Valor original: {record.original_value ?? (record.original_upper_bound !== null ? `<${record.original_upper_bound}` : 'sin valor exacto')}.</p>
      {!!record.missing_months.length && <p>Meses ausentes: {record.missing_months.join(', ')}.</p>}
      {record.observations.map((o) => <div key={o.observation_id}>
        <p>{o.month} · {o.observed_name} · {o.raw_value} {o.original_unit} · {gasAuditLabels[o.review_status]} · <a href={`${record.source.url}#page=${o.page}`} target="_blank" rel="noopener noreferrer">pág. {o.page}</a> · fila {o.source_row} · {o.table_label}</p>
        {o.review_note && <p>{o.review_note}</p>}{o.mapping_review_note && <p>{o.mapping_review_note}</p>}
        {o.publication_status === 'source_error' && <p>Literal conservado como defecto de fuente; no es un valor utilizable.</p>}
      </div>)}
      {!!record.withheld_observation_ids?.length && <p>{record.withheld_observation_ids.length} celdas pendientes de revisión: valores no publicados.</p>}
      {record.unresolved_observations?.map((o) => <div key={o.observation_id}>
        <p>Mes sin resolver · {o.observed_name} · literal original: {o.raw_value} {o.original_unit}. No se asigna a un mes ni se usa como cifra trimestral.</p>
        <p>{o.review_note} · <a href={`${record.source.url}#page=${o.page}`} target="_blank" rel="noopener noreferrer">pág. {o.page}</a> · fila {o.source_row} · {o.table_label}</p>
      </div>)}
      {record.denominator && <details><summary>Total explícito usado como denominador</summary>
        <p>{record.denominator.value} {record.denominator.unit} · {record.denominator.gas_id}</p>
        <GasRetailSource source={record.denominator.source} pages={[...new Set(record.denominator.observations.map((o) => o.page))]} />
        {record.denominator.observations.map((o) => <p key={o.observation_id}>{o.month} · {o.observed_name} · {o.raw_value} {o.unit} · fila {o.source_row}</p>)}
      </details>}
    </div>)}
  </div>;
}
