import { RetryButton } from '../../../components/custom/RetryButton';
import type { ReactNode } from 'react';
import type { ElectricityState } from '../../interfaces/electricity-state';
import { ElectricitySource } from '../../components/ElectricitySource';
import { ShareEvolution } from './ui/ShareEvolution';
import { SuppliesTable } from './ui/SuppliesTable';
import { formatMarketerLabel, formatQuarter, formatRevision } from '../../lib/electricity-format';
import { PublishedPeriodControls } from '../../components/PublishedPeriodControls';
import { useSearchParams } from 'react-router';
import { useEvolutionFilters } from '../../hooks/useEvolutionFilters';
import { EvolutionFilters } from './ui/EvolutionFilters';
import { ComparisonEvolution } from './ui/ComparisonEvolution';
import { useChartDimensions } from '../../hooks/useChartDimensions';

export function EvolutionPage({
  electricity,
  area,
  areaFilter,
}: {
  electricity: ElectricityState;
  area: string;
  areaFilter?: ReactNode;
}) {
  const [params, setParams] = useSearchParams();
  const view = params.get('display') === 'table' ? 'table' : 'chart';
  const filter = useEvolutionFilters();
  const chart = useChartDimensions();
  const companyLabel = formatMarketerLabel(electricity.marketer, electricity.marketers.data);
  const data =
    electricity.enabled && electricity.published && electricity.codeValid
      ? electricity.supplies.data
      : undefined;
  const periods = [...(electricity.quarters.data || [])].reverse();
  const values = new Map(data?.series.map((item) => [item.period, item]));
  const allPoints = periods.map((quarter) => ({
    ...quarter,
    ...values.get(quarter.period),
    supplies: values.get(quarter.period)?.supplies,
  }));
  const points = allPoints.filter(filter.matches);
  const latest = electricity.quarters.data?.[0];
  return (
    <section
      className="evolution-view"
      aria-label="Evolución de comercializadoras"
      data-display={view}
    >
      {electricity.enabled && !electricity.published && electricity.quarters.data?.length && (
        <div className="electricity-controls">
          <PublishedPeriodControls electricity={electricity} />
        </div>
      )}
      {electricity.enabled && (
        <>
          <h2 className="evolution-filter-heading">Filtros de la serie</h2>
          <EvolutionFilters
            rows={allPoints}
            {...filter}
            areaFilter={areaFilter}
            supplies={electricity.metric === 'supplies' && !electricity.comparison.length}
            label={
              electricity.metric === 'share'
                ? 'Filtros de cuotas'
                : 'Filtros de suministros'
            }
          />
          {latest && (
            <p className="evolution-updated">
              Último trimestre publicado: {formatQuarter(latest.period)} ·
              Actualización del origen:{' '}
              <time dateTime={latest.metadata_modified}>
                {formatRevision(latest.metadata_modified)}
              </time>
            </p>
          )}
        </>
      )}
      {electricity.enabled &&
        electricity.metric === 'supplies' &&
        !electricity.comparison.length &&
        electricity.codeValid &&
        electricity.published &&
        (electricity.supplies.isError ||
        (electricity.supplies.isFetching &&
          electricity.supplies.errorUpdatedAt > 0 &&
          !electricity.supplies.data) ? (
          <p role="alert">
            No se pudo cargar la serie.{' '}
            <RetryButton
              loading={electricity.supplies.isFetching}
              onClick={() => void electricity.supplies.refetch()}
            >
              Reintentar serie
            </RetryButton>
          </p>
        ) : electricity.supplies.isPending ? (
          <p role="status">Cargando suministros…</p>
        ) : null)}
      <div className="evolution-results" ref={chart.ref}>
        {electricity.enabled && (
          <div className="evolution-results-controls">
            <div className="evolution-context" role="group" aria-label="Dato de evolución">
              <button
                aria-pressed={electricity.metric === 'supplies'}
                onClick={() => electricity.change({ metric: 'supplies' })}
              >
                Suministros
              </button>
              <button
                aria-pressed={electricity.metric === 'share'}
                onClick={() => electricity.change({ metric: 'share' })}
              >
                Cuota
              </button>
            </div>
            <div className="evolution-context" role="group" aria-label="Presentación de la evolución">
              {(['chart', 'table'] as const).map((value) => (
                <button
                  key={value}
                  aria-pressed={view === value}
                  onClick={() => {
                    const next = new URLSearchParams(params);
                    next.set('display', value);
                    setParams(next);
                  }}
                >
                  {value === 'chart' ? 'Gráfico' : 'Tabla'}
                </button>
              ))}
            </div>
          </div>
        )}
        {!electricity.enabled && (
          <p>Todavía no hay una serie de gas incorporada a esta vista.</p>
        )}
        {electricity.enabled && electricity.codeValid && (
          <p className="evolution-company">
            {view === 'chart' && <i className="evolution-company-swatch" aria-hidden="true" />}
            {companyLabel}
          </p>
        )}
        {electricity.enabled && !electricity.marketer && (
          <div className="evolution-empty">
            <h3>Elige una comercializadora para ver la evolución.</h3>
            <p>
              Busca la empresa que te factura la electricidad. Después podrás comparar suministros
              y cuotas en España o en una comunidad autónoma.
            </p>
            <button
              onClick={() => document.getElementById('electricity-marketer')?.focus()}
              disabled={!electricity.published || !electricity.marketers.data}
            >
              Buscar comercializadora
            </button>
          </div>
        )}
        {electricity.enabled &&
          electricity.codeValid &&
          electricity.published &&
          (view === 'chart' || !!electricity.comparison.length) && (
            <ComparisonEvolution
              electricity={electricity}
              area={area}
              view={view}
              matches={filter.matchesPeriod}
              dimensions={chart.dimensions}
            />
          )}
        {electricity.enabled &&
          electricity.metric === 'share' &&
          !electricity.comparison.length &&
          view === 'table' && (
            <ShareEvolution
              electricity={electricity}
              area={area}
              matches={filter.matchesPeriod}
            />
          )}
        {data && electricity.metric === 'supplies' && !electricity.comparison.length && view === 'table' && (
          <div className="single-evolution-results">
            <p role="status">
              {points.length} de {allPoints.length} trimestres
            </p>
            <p>
              Los trimestres sin observación quedan como huecos; no se
              interpretan como cero.
            </p>
            {view === 'table' && (
              <SuppliesTable
                key={`${electricity.marketer}-${area}`}
                rows={points}
                marketer={companyLabel}
                area={area}
                selectedPeriod={electricity.period}
                onReset={filter.reset}
              />
            )}
            <ElectricitySource source={data} />

            <details>
              <summary>Notas y fuentes por trimestre</summary>
              <p>
                {electricity.enabled
                  ? `Datos de ${companyLabel}. El nombre es el publicado para el trimestre seleccionado. Cada código identifica una empresa; no se suman automáticamente las empresas de un mismo grupo.`
                  : 'Todavía no hay una serie de gas incorporada a esta vista.'}
              </p>
              <p>
                La fuente enlazada corresponde al último trimestre; cada
                trimestre y su revisión se consultan en el catálogo publicado.
              </p>
              {periods.map((quarter) => (
                <p key={quarter.period}>
                  <a href={quarter.source_url} target="_blank" rel="noreferrer">
                    {formatQuarter(quarter.period)}
                  </a>{' '}
                  · {quarter.license_id} ·{' '}
                  {formatRevision(quarter.metadata_modified)}
                </p>
              ))}
            </details>
          </div>
        )}
      </div>
    </section>
  );
}
