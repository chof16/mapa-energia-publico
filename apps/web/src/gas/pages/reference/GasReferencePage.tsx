import { useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { RetryButton } from '../../../components/custom/RetryButton';
import { loadGasReferences } from '../../actions/load-gas-retail';
import { useGasQuery } from '../../hooks/useGasQuery';
import { GasRetailSource } from '../../components/GasRetailSource';
import '../../styles.css';

export function GasReferencePage() {
  const [params, setParams] = useSearchParams();
  useEffect(() => { if (params.toString() !== 'sector=gas') setParams({ sector: 'gas' }, { replace: true }); }, [params, setParams]);
  const query = useGasQuery(['retail', 'reference-marketers'], loadGasReferences);
  const data = query.data;
  return <div className="reference-page gas-reference-page">
    <div className="reference-intro"><div><p className="reference-kicker">Gas · tarifa regulada</p><h1>Comercializadoras de último recurso</h1><p className="reference-lead">Son las empresas identificadas como comercializadoras de último recurso (CUR) de gas en las fuentes consultadas. La tarifa regulada de gas se denomina TUR. Esta página no publica precios.</p></div>
      <aside className="reference-explainer" aria-label="Cómo interpretar el catálogo"><strong>Cómo leer esta lista</strong><p>Catálogo de gas independiente de las COR eléctricas y de las series estadísticas. No vincula las empresas a distribuidoras, grupos ni territorios.</p><p>Las fechas acreditan la evidencia consultada, no el inicio legal de una designación. Se conservan las variantes de nombre observadas.</p></aside></div>
    {query.isPending ? <section className="reference-loading" role="status"><span>Cargando catálogo de último recurso…</span><div className="reference-placeholder" aria-hidden="true" /></section>
      : query.isError ? <section className="reference-state" role="alert"><h2>No se pudo cargar el catálogo de gas</h2><p>La evidencia puede no estar incorporada a esta API. Comprueba la conexión y vuelve a intentarlo.</p><RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>Reintentar</RetryButton></section>
      : data && !data.items.length ? <section className="reference-state" role="status"><h2>Sin entradas publicadas</h2><p>No hay comercializadoras de último recurso de gas en esta revisión.</p></section>
      : data ? <>
        <section className="reference-catalog" aria-labelledby="gas-reference-title"><div className="reference-catalog-heading"><div><h2 id="gas-reference-title">Catálogo con evidencia fechada</h2><p>{data.items.length} comercializadoras · revisión: <time dateTime={data.revision.reviewed_on}>{data.revision.reviewed_on}</time></p></div><span className="reference-count">{data.items.length.toString().padStart(2, '0')}</span></div>
          <ul className="reference-list">{data.items.map((item) => <li className="reference-entry" key={item.marketer_id}><div className="reference-entry-main"><h3>{item.observations.at(-1)?.observed_name || 'Sin denominación observada'}</h3><span className="reference-code">CUR · gas</span></div>
            <details><summary>Denominaciones observadas, fechas y fuentes</summary>{item.observations.map((o, i) => <div key={`${o.source.source_id}-${i}`}><h4>{o.observed_name}</h4><p>Designación observada: CUR de gas · evidencia del <time dateTime={o.evidence_on}>{o.evidence_on}</time>.</p><p>{o.review_note}</p><GasRetailSource source={o.source} pages={o.page ? [o.page] : []} /></div>)}</details>
          </li>)}</ul><p className="reference-list-note">La lista conserva evidencia fechada e incompleta; no acredita cobertura geográfica, exclusividad ni continuidad histórica de las empresas.</p></section>
        <section className="reference-sources"><h2>Fuentes y revisión</h2><p>Las guías y páginas de gas tienen condiciones de reutilización propias, pendientes de revisión. No se aplican automáticamente las condiciones de CNMC Data.</p><details><summary>Identificador de revisión</summary><code>{data.revision.load_id}</code></details></section>
      </> : null}
  </div>;
}
