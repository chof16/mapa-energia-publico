import { SearchSelector } from '../../../components/custom/SearchSelector';
import { ComparisonControls } from '../../../components/custom/ComparisonControls';
import { RetryButton } from '../../../components/custom/RetryButton';
import { useGasRetail } from '../../hooks/useGasRetail';
import { gasQuarter, gasScopeLabels } from '../../lib/retail-format';
import type { GasScope } from '../../interfaces/retail';
import { GasEvolutionResults } from './ui/GasEvolutionResults';
import { GasCompanyContext, gasCompanyDetail } from './ui/GasCompanyContext';
import '../../styles.css';

export function GasEvolutionPage() {
  const state = useGasRetail();
  const { filters, change, revision, periods, marketers } = state;
  const options = marketers.data?.items.map((m) => ({ code: m.marketer_id, title: m.company_name || m.observed_name })) || [];
  // Identical labels are distinct identities, never a reason to merge API entries.
  const labelCounts = new Map<string, number>();
  options.forEach((o) => labelCounts.set(o.title, (labelCounts.get(o.title) || 0) + 1));
  options.forEach((o) => { if (labelCounts.get(o.title)! > 1) o.title += ` · ${o.code}`; });
  const selectedOptions = state.ids.map((code, index) => {
    return { code, title: options.find((o) => o.code === code)?.title || state.series[index]?.data?.company_name || code };
  });
  const labelFor = (id: string) => selectedOptions.find((o) => o.code === id)?.title || options.find((o) => o.code === id)?.title || id;
  const quarters = (periods.data?.items || []).map((p) => p.audit.period).sort();
  const coverage = revision.data?.coverage.find((c) => c.metric === filters.metric);
  const reviewed = coverage?.counts.find((c) => c.status === 'reviewed')?.periods ?? 0;
  const total = coverage?.counts.reduce((sum, c) => sum + c.periods, 0) ?? 0;
  return <>
    <div className="evolution-toolbar gas-evolution-toolbar">
      <div className="toolbar-title"><h1>Evolución de comercializadoras</h1><p>Gas · clientes y ventas de tablas revisadas. Compara hasta cuatro comercializadoras.</p></div>
      <div className="electricity-controls"><div className="marketer-control"><label htmlFor="gas-marketer">Comercializadora observada</label><SearchSelector id="gas-marketer" label="Comercializadora observada" options={[...options, ...selectedOptions.filter((s) => s.code === filters.marketer && !options.some((o) => o.code === s.code))]} value={filters.marketer} showCode={false} disabled={!marketers.data} placeholder="Buscar comercializadora" onChange={(marketer) => change({ marketer })} optionDetail={gasCompanyDetail} /></div></div>
      <ComparisonControls options={options.filter((o) => !state.ids.includes(o.code))} selected={filters.compare} disabled={!filters.marketer || !options.length} onChange={(compare) => change({ compare })} labelFor={labelFor} showCode={false} optionDetail={gasCompanyDetail} />
    </div>
    <section className="evolution-view gas-evolution" aria-label="Evolución de gas" data-display={filters.display}>
      <div className="gas-context-note">
        <p><strong>Geografía definida por cada fuente.</strong> No se presupone comparabilidad nacional histórica.</p>
      </div>
      {state.retiredSelection && <p role="status">La selección anterior usaba identificadores de documentos. Elige ahora la empresa para ver su historia conjunta.</p>}
      <h2 className="evolution-filter-heading">Filtros de la serie</h2>
      <div className="gas-controls-row">
      <div className="evolution-context gas-metric" role="group" aria-label="Métrica de gas">
        <button aria-pressed={filters.metric === 'clients'} onClick={() => change({ metric: 'clients' })}>Clientes</button>
        <button aria-pressed={filters.metric === 'sales'} onClick={() => change({ metric: 'sales' })}>Ventas (MWh)</button>
      </div>
      <div className="gas-series-filters">
        <label>Ámbito histórico del mercado<select value={filters.scope} onChange={(event) => change({ scope: event.target.value as GasScope })}>{Object.entries(gasScopeLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <label>Desde el trimestre<select value={filters.start_period} disabled={!quarters.length} onChange={(event) => change({ start_period: event.target.value })}><option value="">Primer trimestre</option>{quarters.filter((p) => !filters.end_period || p <= filters.end_period).map((p) => <option value={p} key={p}>{gasQuarter(p)}</option>)}</select></label>
        <label>Hasta el trimestre<select value={filters.end_period} disabled={!quarters.length} onChange={(event) => change({ end_period: event.target.value })}><option value="">Último trimestre</option>{quarters.filter((p) => !filters.start_period || p >= filters.start_period).map((p) => <option value={p} key={p}>{gasQuarter(p)}</option>)}</select></label>
      </div>
      </div>
      {revision.isPending && <p role="status">Cargando revisión de gas…</p>}
      {revision.isError && <p role="alert">No se pudo cargar la revisión de gas. <RetryButton loading={revision.isFetching} onClick={() => void revision.refetch()}>Reintentar revisión</RetryButton></p>}
      {revision.isSuccess && !revision.data && <p role="status">Todavía no hay una revisión minorista de gas publicada en esta API.</p>}
      {revision.data && <>
        <p className="evolution-updated">{reviewed}/{total} resúmenes revisados · <time dateTime={revision.data.reviewed_on}>{revision.data.reviewed_on}</time> · Cobertura incompleta.{filters.load_id && ' Revisión fijada en este enlace.'}</p>
        {[{ query: periods, label: 'periodos' }, { query: marketers, label: 'comercializadoras' }].map(({ query, label }) => query.isError ? <p role="alert" key={label}>No se pudieron cargar {label}. <RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>Reintentar {label}</RetryButton></p> : query.isPending ? <p role="status" key={label}>Cargando {label}…</p> : null)}
        {marketers.data && !marketers.data.items.length && <p role="status">No hay comercializadoras revisadas para esta métrica y ámbito.</p>}
        {periods.data && !periods.data.items.length && <p role="status">No hay periodos de auditoría para estos filtros.</p>}
      </>}
      <GasEvolutionResults key={`${filters.metric}-${filters.scope}-${filters.measure}-${filters.start_period}-${filters.end_period}-${filters.marketer}-${filters.compare.join(',')}`} state={state} labelFor={labelFor} />
      <GasCompanyContext selected={selectedOptions} />
    </section>
  </>;
}
