import { RetryButton } from '../../components/custom/RetryButton';
import type { MapExplorer } from '../../map/interfaces/map-explorer';
import { useGasProvinceDistributors } from '../hooks/useGasDistribution';
import { formatNetworkPeriod } from '../lib/distribution-format';
import { ProvinceEvidencePanel } from '../../distribution/components/ProvinceEvidencePanel';

export function GasProvinceEvidence({ explorer }: { explorer: MapExplorer }) {
  const province = explorer.selection.find((item) => item.level === 'provincias');
  const municipality = explorer.selection.find((item) => item.level === 'municipios');
  const summary = explorer.gasProvinceSummary;
  const query = useGasProvinceDistributors(province?.code ?? null, summary.isError ? null : summary.data?.source.load_id ?? null);
  return <ProvinceEvidencePanel province={province} label="Presencia provincial de gas" sector="gas natural"
    scope={summary.data && !summary.isError ? `Datos históricos · ${formatNetworkPeriod(summary.data.source.period)}` : 'Presencias provinciales parciales'}
    prompt={<>El mapa marca provincias con presencias documentadas. Elige una para consultar sus fuentes.
      {summary.data && !summary.isError && <> Datos históricos de {formatNetworkPeriod(summary.data.source.period)}; no describen la red actual.</>}</>}>
    {municipality && <p className="province-evidence-warning">Has seleccionado {municipality.title}. La evidencia provincial no acredita cobertura en este municipio ni en una dirección.</p>}
    {province && query.isFetching && !query.data && <p role="status">Cargando distribuidoras de gas…</p>}
    {province && query.isError && <p role="alert">No se pudo cargar el detalle de gas. <RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>Reintentar detalle de gas</RetryButton></p>}
    {province && query.data && !query.isError && <>
      {query.data.items.length === 0 ? <p role="status">Sin evidencia en esta fuente: cobertura desconocida. No significa que no exista red.</p> :
        <ul className="province-evidence-list">{query.data.items.map((item) => <li key={item.distributor_name}>
          <h3>{item.distributor_name}</h3>
          <p>{item.supply_points.toLocaleString('es-ES')} {item.supply_points === 1 ? 'punto' : 'puntos'} de suministro · {item.source_row_count.toLocaleString('es-ES')} {item.source_row_count === 1 ? 'fila municipal' : 'filas municipales'} en el anexo.</p>
        </li>)}</ul>}
      <p className="province-evidence-note">Nombres publicados en {formatNetworkPeriod(query.data.source.period)}; no se han equiparado a las empresas actuales. Red de gas natural de presión ≤4 bar. Presencia parcial, sin exclusividad ni cobertura completa provincial.</p>
      <p><a href={query.data.source.source_url} target="_blank" rel="noopener noreferrer">Informe oficial de la CNMC</a> · <a href={query.data.source.download_url} target="_blank" rel="noopener noreferrer">Consultar anexo municipal</a></p>
      <p><strong>Confianza:</strong> Documento oficial. Condiciones de reutilización pendientes de revisión.</p>
      <p className="province-evidence-attribution">{query.data.source.attribution}. Publicado el {query.data.source.published_on}.</p>
    </>}
  </ProvinceEvidencePanel>;
}
