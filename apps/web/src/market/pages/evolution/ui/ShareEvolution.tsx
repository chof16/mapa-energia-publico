import { RetryButton } from '../../../../components/custom/RetryButton';
import { isAxiosError } from 'axios';
import type { MarketState } from '../../../interfaces/market-state';
import { formatShare } from '../../../lib/market-style';
import { MarketSource } from '../../../components/MarketSource';
import { formatMarketerLabel, formatQuarter, formatRevision } from '../../../lib/market-format';

export function ShareEvolution({
  market,
  area,
  matches,
}: {
  market: MarketState;
  area: string;
  matches: (period: string) => boolean;
}) {
  const query = market.shareSeries;
  const companyLabel = formatMarketerLabel(market.marketer, market.marketers.data);
  if (!market.codeValid || !market.published)
    return <p>Elige una comercializadora y un trimestre publicado.</p>;
  if (
    query.isError ||
    (query.isFetching && query.errorUpdatedAt > 0 && !query.data)
  )
    return (
      <p role="status">
        {isAxiosError(query.error) && query.error.response?.status === 404
          ? 'La serie de cuotas está pendiente de activar en esta API.'
          : 'No se pudo cargar la serie de cuotas.'}{' '}
        <RetryButton
          loading={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Reintentar cuotas históricas
        </RetryButton>
      </p>
    );
  if (!query.data) return <p role="status">Cargando cuotas históricas…</p>;
  const rows = query.data.series.filter((row) => matches(row.period));
  return (
    <>
      <p role="status">
        {rows.length} de {query.data.series.length} trimestres
      </p>
      <p>
        Denominador: suministros con comercializadora registrada. Consumidor
        Directo y No Disponible quedan excluidos. Sin denominador se muestra un
        hueco; 0 % es un valor medido.
      </p>
      <div className="market-table-wrap">
        <table className="mobile-stacked-table share-detail-table">
          <caption>
            Cuota de {companyLabel} · {area}
          </caption>
          <thead>
            <tr>
              <th>Trimestre</th>
              <th>Cuota</th>
              <th>Suministros / denominador</th>
              <th>Excluidos: directo / no disponible</th>
              <th>Origen y revisión</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.period}>
                <th scope="row">{formatQuarter(row.period)}</th>
                <td data-label="Cuota">{formatShare(row.share)}</td>
                <td data-label="Suministros / denominador">
                  {row.supplies.toLocaleString('es')} /{' '}
                  {row.marketer_supplies.toLocaleString('es')}
                </td>
                <td data-label="Excluidos: directo / no disponible">
                  {row.direct_consumer_supplies.toLocaleString('es')} /{' '}
                  {row.unavailable_supplies.toLocaleString('es')}
                </td>
                <td data-label="Origen y revisión">
                  <a href={row.source_url} target="_blank" rel="noreferrer">
                    Fuente {row.period}
                  </a>
                  <br />
                  <time dateTime={row.metadata_modified}>
                    {formatRevision(row.metadata_modified)}
                  </time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {query.data.series.at(-1) && (
        <MarketSource source={query.data.series.at(-1)!} />
      )}
    </>
  );
}
