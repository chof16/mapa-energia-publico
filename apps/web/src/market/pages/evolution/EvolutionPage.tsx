import { RetryButton } from '../../../components/custom/RetryButton';
import type { ReactNode } from 'react';
import type { MarketState } from '../../interfaces/market-state';
import { MarketSource } from '../../components/MarketSource';
import { ShareEvolution } from './ui/ShareEvolution';
import { SuppliesTable } from './ui/SuppliesTable';
import { formatMarketerLabel, formatQuarter, formatRevision } from '../../lib/market-format';
import { PublishedPeriodControls } from '../../components/PublishedPeriodControls';
import { useSearchParams } from 'react-router';
import { useEvolutionFilters } from '../../hooks/useEvolutionFilters';
import { EvolutionFilters } from './ui/EvolutionFilters';
import { ComparisonEvolution } from './ui/ComparisonEvolution';
import { useChartDimensions } from '../../hooks/useChartDimensions';

export function EvolutionPage({
  market,
  area,
  areaFilter,
}: {
  market: MarketState;
  area: string;
  areaFilter?: ReactNode;
}) {
  const [params, setParams] = useSearchParams();
  const view = params.get('display') === 'table' ? 'table' : 'chart';
  const filter = useEvolutionFilters();
  const chart = useChartDimensions();
  const companyLabel = formatMarketerLabel(market.marketer, market.marketers.data);
  const data =
    market.enabled && market.published && market.codeValid
      ? market.supplies.data
      : undefined;
  const periods = [...(market.quarters.data || [])].reverse();
  const values = new Map(data?.series.map((item) => [item.period, item]));
  const allPoints = periods.map((quarter) => ({
    ...quarter,
    ...values.get(quarter.period),
    supplies: values.get(quarter.period)?.supplies,
  }));
  const points = allPoints.filter(filter.matches);
  const latest = market.quarters.data?.[0];
  return (
    <section
      className="evolution-view"
      aria-label="Evolución de comercializadoras"
      data-display={view}
    >
      {market.enabled && !market.published && market.quarters.data?.length && (
        <div className="market-controls">
          <PublishedPeriodControls market={market} />
        </div>
      )}
      {market.enabled && (
        <>
          <h2 className="evolution-filter-heading">Filtros de la serie</h2>
          <EvolutionFilters
            rows={allPoints}
            {...filter}
            areaFilter={areaFilter}
            supplies={market.metric === 'supplies' && !market.comparison.length}
            label={
              market.metric === 'share'
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
      {market.enabled &&
        market.metric === 'supplies' &&
        !market.comparison.length &&
        market.codeValid &&
        market.published &&
        (market.supplies.isError ||
        (market.supplies.isFetching &&
          market.supplies.errorUpdatedAt > 0 &&
          !market.supplies.data) ? (
          <p role="alert">
            No se pudo cargar la serie.{' '}
            <RetryButton
              loading={market.supplies.isFetching}
              onClick={() => void market.supplies.refetch()}
            >
              Reintentar serie
            </RetryButton>
          </p>
        ) : market.supplies.isPending ? (
          <p role="status">Cargando suministros…</p>
        ) : null)}
      <div className="evolution-results" ref={chart.ref}>
        {market.enabled && (
          <div className="evolution-results-controls">
            <div className="evolution-context" role="group" aria-label="Dato de evolución">
              <button
                aria-pressed={market.metric === 'supplies'}
                onClick={() => market.change({ metric: 'supplies' })}
              >
                Suministros
              </button>
              <button
                aria-pressed={market.metric === 'share'}
                onClick={() => market.change({ metric: 'share' })}
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
        {!market.enabled && (
          <p>Todavía no hay una serie de gas incorporada a esta vista.</p>
        )}
        {market.enabled && market.codeValid && (
          <p className="evolution-company">
            {view === 'chart' && <i className="evolution-company-swatch" aria-hidden="true" />}
            {companyLabel}
          </p>
        )}
        {market.enabled && !market.marketer && (
          <div className="evolution-empty">
            <h3>Elige una comercializadora para ver la evolución.</h3>
            <p>
              Busca la empresa que te factura la electricidad. Después podrás comparar suministros
              y cuotas en España o en una comunidad autónoma.
            </p>
            <button
              onClick={() => document.getElementById('market-marketer')?.focus()}
              disabled={!market.published || !market.marketers.data}
            >
              Buscar comercializadora
            </button>
          </div>
        )}
        {market.enabled &&
          market.codeValid &&
          market.published &&
          (view === 'chart' || !!market.comparison.length) && (
            <ComparisonEvolution
              market={market}
              area={area}
              view={view}
              matches={filter.matchesPeriod}
              dimensions={chart.dimensions}
            />
          )}
        {market.enabled &&
          market.metric === 'share' &&
          !market.comparison.length &&
          view === 'table' && (
            <ShareEvolution
              market={market}
              area={area}
              matches={filter.matchesPeriod}
            />
          )}
        {data && market.metric === 'supplies' && !market.comparison.length && view === 'table' && (
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
                key={`${market.marketer}-${area}`}
                rows={points}
                marketer={companyLabel}
                area={area}
                selectedPeriod={market.period}
                onReset={filter.reset}
              />
            )}
            <MarketSource source={data} />

            <details>
              <summary>Notas y fuentes por trimestre</summary>
              <p>
                {market.enabled
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
