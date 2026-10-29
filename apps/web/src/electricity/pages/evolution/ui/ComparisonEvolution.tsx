import { RetryButton } from '../../../../components/custom/RetryButton';
import { EvolutionChart } from '../../../../components/custom/EvolutionChart';
import { TableSortControls } from './TableSortControls';
import { useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { loadSupplies, loadShareSeries } from '../../../actions/load-electricity';
import type { ElectricityState } from '../../../interfaces/electricity-state';
import { formatMarketerLabel, formatQuarter, formatRevision } from '../../../lib/electricity-format';
import { formatShare } from '../../../lib/electricity-style';
import { ElectricitySource } from '../../../components/ElectricitySource';
import type { ChartDimensions } from '../../../../interfaces/chart-dimensions';
import { shareAxisMaximum } from '../../../lib/share-axis';

const colors = ['#185eaa', '#b24c22', '#6663a8', '#98620c'];
const quarterIndex = (period: string) =>
  Number(period.slice(0, 4)) * 4 + Number(period.at(-1));

export function ComparisonEvolution({
  electricity,
  area,
  view,
  matches,
  dimensions,
}: {
  electricity: ElectricityState;
  area: string;
  view: 'chart' | 'table';
  matches: (period: string) => boolean;
  dimensions: ChartDimensions;
}) {
  const share = electricity.metric === 'share';
  const extras = useQueries({
    queries: electricity.comparison.map((code) => ({
      queryKey: [
        'electricity',
        share ? 'share-series' : 'supplies',
        code,
        electricity.community,
      ],
      queryFn: async ({ signal }: { signal: AbortSignal }) =>
        share
          ? await loadShareSeries(code, electricity.community, signal)
          : await loadSupplies(code, electricity.community, signal),
      staleTime: 300_000,
      retry: false,
    })),
  });
  const queries = [share ? electricity.shareSeries : electricity.supplies, ...extras];
  const codes = [electricity.marketer, ...electricity.comparison];
  const companyLabel = (code: string) => formatMarketerLabel(code, electricity.marketers.data);
  const series = queries.map((query, index) => ({
    code: codes[index],
    query,
    values: new Map(
      query.data?.series.map((row) => [
        row.period,
        {
          value: share && 'share' in row ? row.share : row.supplies,
          revision: row.metadata_modified,
        },
      ]),
    ),
  }));
  const periods = [...(electricity.quarters.data || [])]
    .reverse()
    .filter((row) => matches(row.period));
  const [active, setActive] = useState<{ code: string; period: string } | null>(
    null,
  );
  const [sort, setSort] = useState({ column: 'period', ascending: false });
  const first = quarterIndex(periods[0]?.period || '2011T1');
  const last = quarterIndex(periods.at(-1)?.period || '2011T1');
  const max = share
    ? shareAxisMaximum(
        series.flatMap((item) =>
          periods.map((row) => item.values.get(row.period)?.value),
        ),
      )
    : Math.max(
        1,
        ...series.flatMap((item) =>
          periods.map((row) => item.values.get(row.period)?.value || 0),
        ),
      );
  const x = (period: string) =>
    65 + ((quarterIndex(period) - first) / Math.max(1, last - first)) * (dimensions.width - 110);
  const y = (value: number) =>
    dimensions.height - 75 - (value / max) * (dimensions.height - 120);
  const format = (value: number | null | undefined) =>
    value === undefined
      ? 'Sin observación'
      : share
        ? formatShare(value)
        : value === null
          ? 'Sin denominador'
          : value.toLocaleString('es-ES');
  const activeValue =
    active &&
    series.find((item) => item.code === active.code)?.values.get(active.period)
      ?.value;
  const sourceData = queries.find((query) => query.data?.series.length)?.data;
  const source =
    sourceData &&
    ('source_url' in sourceData ? sourceData : sourceData.series.at(-1));
  const sorted = [...periods].sort((a, b) => {
    if (sort.column === 'period')
      return (sort.ascending ? 1 : -1) * a.period.localeCompare(b.period);
    const values = series.find((item) => item.code === sort.column)?.values;
    const left = values?.get(a.period)?.value,
      right = values?.get(b.period)?.value;
    if (left == null)
      return right == null ? a.period.localeCompare(b.period) : 1;
    if (right == null) return -1;
    return (
      (sort.ascending ? 1 : -1) * (left - right) ||
      a.period.localeCompare(b.period)
    );
  });
  const comparing = electricity.comparison.length > 0;
  const hasPrimaryData = (queries[0].data?.series.length ?? 0) > 0;
  return (
    <section aria-label={comparing ? 'Comparación de comercializadoras' : 'Serie de comercializadora'}>
      <p role="status">
        {comparing
          ? `${periods.length} trimestres · ${codes.length} comercializadoras`
          : `${periods.length} de ${electricity.quarters.data?.length || periods.length} trimestres`}
      </p>
      {view === 'chart' && (
        <div className="comparison-legend" aria-label="Series del gráfico">
          {series.slice(1).map((item, offset) => (
            <span key={item.code} title={companyLabel(item.code)}>
              <i style={{ background: colors[offset + 1] }} />
              {companyLabel(item.code)}
              {item.query.isPending && ' · Cargando…'}
              {item.query.data && !item.query.data.series.length && ' · Sin observaciones'}
            </span>
          ))}
        </div>
      )}
      {view === 'chart' && hasPrimaryData && (
        <EvolutionChart
          {...dimensions}
          periods={periods.map((row) => row.period)}
          series={series}
          max={max}
          share={share}
          x={x}
          y={y}
          onActive={setActive}
          label={comparing
            ? `Comparación de ${share ? 'cuotas' : 'suministros'} en ${area}`
            : `Evolución de ${share ? 'cuota' : 'suministros'} de ${companyLabel(electricity.marketer)} en ${area}`}
          pointLabel={(code, period, value) => comparing
            ? `${companyLabel(code)}: ${formatQuarter(period)}, ${format(value)}${share ? '' : ' suministros'}`
            : `${formatQuarter(period)}: ${format(value)}${share ? '' : ' suministros'}`}
        />
      )}
      {series.map((item) =>
        item.query.isError ||
        (item.query.isFetching &&
          item.query.errorUpdatedAt > 0 &&
          !item.query.data) ? (
          <p key={item.code} role="alert">
            {companyLabel(item.code)}:{' '}
            {share &&
            isAxiosError(item.query.error) &&
            item.query.error.response?.status === 404
              ? 'La serie de cuotas está pendiente de activar en esta API.'
              : 'No se pudo cargar la serie.'}{' '}
            <RetryButton
              loading={item.query.isFetching}
              onClick={() => void item.query.refetch()}
            >
              Reintentar {companyLabel(item.code)}
            </RetryButton>
          </p>
        ) : item.query.isPending ? (
          <p key={item.code} role="status">
            Cargando {companyLabel(item.code)}…
          </p>
        ) : null,
      )}
      {view === 'chart' && active && typeof activeValue === 'number' && (
        <div role="tooltip" className="comparison-tooltip">
          <strong>{companyLabel(active.code)}</strong>
          <span>{formatQuarter(active.period)} · {area}</span>
          <span>{format(activeValue)}{share ? '' : ' suministros'}</span>
        </div>
      )}
      {view === 'table' && (
        <TableSortControls
          columns={['period', ...codes].map((code) => [
            code,
            code === 'period' ? 'Trimestre' : companyLabel(code),
          ])}
          sort={sort}
          onChange={setSort}
        />
      )}
      {view === 'table' && (
        <div className="electricity-table-wrap">
          <table className="supplies-table mobile-stacked-table">
            <caption>
              Comparación de {share ? 'cuotas' : 'suministros'} · {area}
            </caption>
            <thead>
              <tr>
                {['period', ...codes].map((column) => (
                  <th
                    scope="col"
                    key={column}
                    aria-sort={
                      sort.column === column
                        ? sort.ascending
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    <button
                      onClick={() =>
                        setSort({
                          column,
                          ascending:
                            sort.column === column ? !sort.ascending : true,
                        })
                      }
                    >
                      {column === 'period' ? 'Trimestre' : companyLabel(column)}
                      <span aria-hidden="true">
                        {sort.column === column
                          ? sort.ascending
                            ? '↑'
                            : '↓'
                          : '↕'}
                      </span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr key={row.period}>
                  <th scope="row">{formatQuarter(row.period)}</th>
                  {series.map((item) => (
                    <td key={item.code} data-label={companyLabel(item.code)}>
                      {item.query.isError
                        ? 'Error de carga'
                        : item.query.isPending
                          ? 'Cargando…'
                          : format(item.values.get(row.period)?.value)}
                      {item.values.get(row.period) && (
                        <small className="comparison-revision">
                          <time
                            dateTime={item.values.get(row.period)!.revision}
                          >
                            Revisión:{' '}
                            {formatRevision(
                              item.values.get(row.period)!.revision,
                            )}
                          </time>
                        </small>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!periods.length && <p>No hay trimestres con estos filtros.</p>}
      <p>
        Los huecos no equivalen a cero.{' '}
        {share &&
          'Cuotas sobre suministros con comercializadora registrada; Consumidor Directo y No Disponible quedan excluidos.'}
      </p>
      <details>
        <summary>Fuentes de las series comparadas</summary>
        {series.map((item) => {
          const data = item.query.data;
          const source =
            data && ('source_url' in data ? data : data.series.at(-1));
          return (
            source && (
              <div key={item.code}>
                <strong>{companyLabel(item.code)}</strong>
                <ElectricitySource source={source} />
              </div>
            )
          );
        })}
      </details>
      {source && <ElectricitySource source={source} />}
    </section>
  );
}
