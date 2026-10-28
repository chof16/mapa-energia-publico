import { RetryButton } from '../../components/custom/RetryButton';
import { oneDocumentedColor, multipleDocumentedColor, unknownProvinceColor } from '../../distribution/lib/distribution-style';
import type { MapExplorer } from '../../map/interfaces/map-explorer';
import { formatNetworkPeriod } from '../lib/distribution-format';

export function GasNetworkLegend({ query }: { query: MapExplorer['gasProvinceSummary'] }) {
  return <>
    <strong>Distribuidoras de gas · presencia provincial</strong>
    {query.data && !query.isError ? <>
      <span><i className="share-swatch" style={{ background: oneDocumentedColor }} />1 distribuidora</span>
      <span><i className="share-swatch" style={{ background: multipleDocumentedColor }} />2 o más</span>
      <span><i className="share-swatch" style={{ background: unknownProvinceColor }} />Sin evidencia (desconocido)</span>
      <span className="distribution-legend-note">Datos históricos: {formatNetworkPeriod(query.data.source.period)}. Gas natural ≤4 bar. El color indica presencia en alguna zona provincial, sin delimitar la red. Se oculta al acercarse a municipios.</span>
    </> : query.isError ? <span className="distribution-legend-note">No se pudo cargar la evidencia de gas. <RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>Reintentar mapa de gas</RetryButton></span>
      : <span role="status">Cargando evidencia territorial de gas…</span>}
    <span>Límites actuales · <a href="https://www.ign.es/" target="_blank" rel="noreferrer">IGN</a>/<a href="https://www.cnig.es/" target="_blank" rel="noreferrer">CNIG</a></span>
  </>;
}
