import { isAxiosError } from 'axios';
import { RetryButton } from '../../../components/custom/RetryButton';
import { useSelectionUrl } from '../../../map/hooks/useSelectionUrl';
import { useReferenceMarketers } from '../../hooks/useReferenceMarketers';
import { formatQuarter, formatRevision } from '../../lib/market-format';
import type { ReferenceMarketer } from '../../interfaces/reference-marketers';

function ReferenceEntry({ item }: { item: ReferenceMarketer }) {
  const territory = item.territorial_limit === 'ceuta'
    ? 'Solo Ceuta'
    : item.territorial_limit === 'melilla'
      ? 'Solo Melilla'
      : 'Sin límite especial indicado por la CNMC';
  return (
    <li className="reference-entry">
      <div className="reference-entry-main">
        <h3>{item.name}</h3>
        <span className="reference-code">{item.marketer_code}</span>
      </div>
      <p className={item.territorial_limit ? 'reference-territory is-limited' : 'reference-territory'}>
        {territory}
      </p>
    </li>
  );
}

export function ReferencePage() {
  const { sector } = useSelectionUrl(null);
  const query = useReferenceMarketers(sector === 'electricidad');
  const data = query.data;
  const pendingApi = isAxiosError(query.error) && query.error.response?.status === 404;

  return (
    <div className="reference-page">
      <div className={sector === 'gas' ? 'reference-intro is-gas' : 'reference-intro'}>
        <div>
          <p className="reference-kicker">{sector === 'gas' ? 'Gas · pendiente' : 'Electricidad · tarifa regulada'}</p>
          <h1>{sector === 'gas' ? 'Comercializadoras de referencia de gas' : 'Comercializadoras de referencia'}</h1>
          <p className="reference-lead">
            {sector === 'gas'
              ? 'El catálogo de gas llegará en una fase posterior del proyecto.'
              : 'Son las empresas designadas para ofrecer la tarifa regulada de electricidad (PVPC). Puedes elegir comercializadora; tu distribuidora gestiona la red de tu zona.'}
          </p>
        </div>
        {sector === 'electricidad' && <aside className="reference-explainer" aria-label="Cómo interpretar el catálogo">
          <strong>Cómo leer esta lista</strong>
          <p>La designación como COR no vincula una empresa a una distribuidora concreta ni indica cobertura provincial o municipal.</p>
          <p>Es una instantánea revisada. No describe qué empresas tenían esta designación en trimestres anteriores.</p>
        </aside>}
      </div>

      {sector === 'gas' ? (
        <section className="reference-state" role="status">
          <h2>Gas pendiente</h2>
          <p>El catálogo de comercializadoras de referencia de gas aún no está disponible.</p>
        </section>
      ) : query.isPending ? (
        <section className="reference-loading" role="status" aria-label="Cargando comercializadoras de referencia">
          <span>Cargando catálogo verificado…</span>
          <div className="reference-placeholder" aria-hidden="true" />
          <div className="reference-placeholder" aria-hidden="true" />
          <div className="reference-placeholder" aria-hidden="true" />
        </section>
      ) : query.isError ? (
        <section className="reference-state" role="alert">
          <h2>{pendingApi ? 'Catálogo pendiente en esta API' : 'No se pudo cargar el catálogo'}</h2>
          <p>{pendingApi ? 'Esta versión de la API aún no publica las comercializadoras de referencia.' : 'Comprueba la conexión y vuelve a intentarlo.'}</p>
          <RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>Reintentar</RetryButton>
        </section>
      ) : data && data.items.length === 0 ? (
        <section className="reference-state" role="status">
          <h2>Sin entradas publicadas</h2>
          <p>La API no ha publicado comercializadoras de referencia para electricidad en esta instantánea.</p>
        </section>
      ) : data ? (
        <>
          <section className="reference-catalog" aria-labelledby="reference-catalog-title">
            <div className="reference-catalog-heading">
              <div>
                <h2 id="reference-catalog-title">Catálogo verificado</h2>
                <p>{data.items.length} comercializadoras · revisado el <time dateTime={data.snapshot_date}>{formatRevision(data.snapshot_date)}</time></p>
              </div>
              <span className="reference-count" aria-label={`${data.items.length} comercializadoras`}>{data.items.length.toString().padStart(2, '0')}</span>
            </div>
            <ul className="reference-list">
              {data.items.map((item) => <ReferenceEntry key={item.marketer_code} item={item} />)}
            </ul>
            <p className="reference-list-note">«Sin límite especial indicado» significa que la lista de la CNMC no expresa una restricción territorial para esa COR. No acredita exclusividad ni cobertura de una provincia.</p>
          </section>
          <section className="reference-sources" aria-labelledby="reference-sources-title">
            <h2 id="reference-sources-title">Fuentes y revisión</h2>
            <p><a href={data.designation_source_url} target="_blank" rel="noopener noreferrer">Lista de COR de la CNMC</a>: designación y límites expresos de Ceuta y Melilla.</p>
            <p><a href={data.code_source_url} target="_blank" rel="noopener noreferrer">CNMC Data</a>: códigos R2 cotejados con {formatQuarter(data.code_source_period)}; última modificación de ese conjunto el <time dateTime={data.code_source_metadata_modified}>{formatRevision(data.code_source_metadata_modified)}</time>.</p>
            <p>{data.attribution}. Revisión del catálogo: <time dateTime={data.snapshot_date}>{formatRevision(data.snapshot_date)}</time>.</p>
          </section>
        </>
      ) : null}
    </div>
  );
}
