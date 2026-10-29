import { useLayoutEffect, useRef, useState } from 'react';
import type { useGasRetail } from '../../../hooks/useGasRetail';
import { EvolutionChart, evolutionColors, quarterIndex } from '../../../../components/custom/EvolutionChart';
import { EvolutionDisplayControls } from '../../../../components/custom/EvolutionDisplayControls';
import { useChartDimensions } from '../../../../components/custom/useChartDimensions';
import { RetryButton } from '../../../../components/custom/RetryButton';
import { gasChartValue, gasPointLabel, gasQuarter, gasScopeLabels } from '../../../lib/retail-format';
import { GasProvenance } from './GasProvenance';

function GasPointTooltip({ name, detail, x, y, width, height }: { name: string; detail: string; x: number; y: number; width: number; height: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    setSize((current) => current.width === node.offsetWidth && current.height === node.offsetHeight
      ? current : { width: node.offsetWidth, height: node.offsetHeight });
  }, [name, detail, width]);
  const left = Math.max(8, Math.min(x - size.width / 2, width - size.width - 8));
  const above = y - size.height - 12;
  const top = Math.max(8, Math.min(above >= 8 ? above : y + 12, height - size.height - 8));
  return <div ref={ref} role="tooltip" className="comparison-tooltip" style={{ left, top }}><strong>{name}</strong><span>{detail}</span></div>;
}

export function GasEvolutionResults({ state, labelFor }: { state: ReturnType<typeof useGasRetail>; labelFor: (id: string) => string }) {
  const { filters, ids, series: queries } = state;
  const chart = useChartDimensions({ stableHeight: true });
  const [active, setActive] = useState<{ code: string; period: string } | null>(null);
  const share = filters.measure === 'share';
  const periods = (state.periods.data?.items || []).map((p) => p.audit.period).filter((p) => (!filters.start_period || p >= filters.start_period) && (!filters.end_period || p <= filters.end_period)).sort();
  const series = queries.map((query, i) => ({ code: ids[i], query, points: new Map(query.data?.items.map((p) => [p.audit.period, p])), values: new Map(query.data?.items.map((p) => [p.audit.period, { value: gasChartValue(p, share), continuity: `${ids[i]}:${filters.scope}:${filters.metric}` }])) }));
  const maximum = Math.max(share ? 0.01 : 1, ...series.flatMap((s) => [...s.values.values()].map((p) => p.value ?? 0)));
  const compact = chart.dimensions.width < 600;
  const maxLabel = share ? `${(maximum * 100).toLocaleString('es-ES', { maximumFractionDigits: 1 })} %` : Math.round(maximum).toLocaleString('es-ES');
  const left = compact ? Math.max(40, maxLabel.length * 6 + 10) : 65;
  const right = compact ? 12 : 45, bottom = compact ? 52 : 75, top = compact ? 35 : 45;
  const first = quarterIndex(periods[0] || '2003T4'), last = quarterIndex(periods.at(-1) || '2003T4');
  const x = (p: string) => left + ((quarterIndex(p) - first) / Math.max(1, last - first)) * (chart.dimensions.width - left - right);
  const y = (v: number) => chart.dimensions.height - bottom - (v / maximum) * (chart.dimensions.height - bottom - top);
  const activePoint = active && series.find((s) => s.code === active.code)?.points.get(active.period);
  const activeValue = activePoint ? gasChartValue(activePoint, share) : null;
  const title = `${share ? 'Cuota de ' : ''}${filters.metric === 'clients' ? 'clientes' : 'ventas (MWh)'} · ${gasScopeLabels[filters.scope]}`;
  return <div className="evolution-results" ref={chart.ref}>
    <div className="evolution-results-controls">
      <div className="evolution-context" role="group" aria-label="Dato de evolución">
        <button aria-pressed={!share} onClick={() => state.change({ measure: 'absolute' })}>Valor absoluto</button>
        <button aria-pressed={share} onClick={() => state.change({ measure: 'share' })}>Cuota</button>
      </div>
      <EvolutionDisplayControls value={filters.display} onChange={(display) => state.change({ display })} />
    </div>
    {!ids.length ? <div className="evolution-empty"><h3>Elige una comercializadora para ver la evolución.</h3><p>Una selección reúne la historia revisada de esa empresa entre informes. Puedes comparar hasta cuatro comercializadoras.</p><button disabled={!state.marketers.data?.items.length} onClick={() => document.getElementById('gas-marketer')?.focus()}>Buscar comercializadora</button></div> : <>
      <div className="gas-chart-summary"><p role="status">{periods.length} trimestres · {ids.length} {ids.length === 1 ? 'comercializadora' : 'comercializadoras'}</p>
      <div className="comparison-legend" aria-label="Series del gráfico">{ids.map((id, i) => <span key={id}><i style={{ background: evolutionColors[i] }} />{labelFor(id)}</span>)}</div>
      </div>
      {series.map(({ code, query }) => query.isError ? <p role="alert" key={code}>{labelFor(code)}: No se pudo cargar la serie. El identificador puede no estar revisado en esta carga. <RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>Reintentar serie</RetryButton></p> : query.isPending ? <p role="status" key={code}>Cargando {labelFor(code)}…</p> : null)}
      {filters.display === 'chart' && <>
        <div className="gas-chart-frame">
        <EvolutionChart periods={periods} series={series} {...chart.dimensions} left={left} right={right} bottom={bottom} max={maximum} share={share} x={x} y={y} label={`Evolución de ${title}`} valueLabel={share ? `Cuota de ${filters.metric === 'clients' ? 'clientes' : 'ventas'} (%)` : filters.metric === 'clients' ? 'Clientes (último mes)' : 'Ventas trimestrales (MWh)'} onActive={setActive}
          pointLabel={(id, p) => `${labelFor(id)} · ${gasQuarter(p)} · ${gasPointLabel(series.find((s) => s.code === id)?.points.get(p), share)}`} />
        {active && activePoint && activeValue != null && periods.includes(active.period) && <GasPointTooltip name={labelFor(active.code)} detail={`${gasQuarter(active.period)} · ${gasPointLabel(activePoint, share)}`} x={x(active.period)} y={y(activeValue)} {...chart.dimensions} />}
        </div>
        {series.every((s) => [...s.values.values()].every((v) => v.value === null)) && queries.every((q) => q.isSuccess) && <p>No hay valores exactos para dibujar con estos filtros. Consulta los límites y estados en la tabla y las fuentes.</p>}
      </>}
      {filters.display === 'table' && <div className="electricity-table-wrap"><table className="supplies-table mobile-stacked-table"><caption>Comparación de {title}</caption><thead><tr><th scope="col">Trimestre</th>{ids.map((id) => <th scope="col" key={id}>{labelFor(id)}</th>)}</tr></thead><tbody>{[...periods].reverse().map((p) => <tr key={p}><th scope="row">{gasQuarter(p)}</th>{series.map((s) => <td key={s.code} data-label={labelFor(s.code)} title={gasPointLabel(s.points.get(p), false)}>{s.query.isError ? 'Error de carga' : s.query.isPending ? 'Cargando…' : gasPointLabel(s.points.get(p), share)}</td>)}</tr>)}</tbody></table></div>}
      {!periods.length && <p>No hay trimestres con estos filtros.</p>}
      <details><summary>Valores, notas y fuentes por trimestre</summary>{series.map((s) => <section key={s.code}><h3>{labelFor(s.code)}</h3>{[...s.points].map(([p, point]) => <details key={p}><summary>{gasQuarter(p)} · {gasPointLabel(point, share)}</summary><GasProvenance point={point} /></details>)}</section>)}</details>
    </>}
  </div>;
}
