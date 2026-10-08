import { RetryButton } from '../../components/custom/RetryButton';
import type { Territory } from '../../map/interfaces/territory';
import { useProvincePresence } from '../hooks/useProvincePresence';
import type { CoverageEvidence } from '../interfaces/distribution';
import '../styles.css';

const confidenceLabels: Record<CoverageEvidence['confidence'], string> = {
  official_document: 'Documento oficial',
  group_first_party_reported: 'Declarado por el grupo empresarial',
  other_operator_reported: 'Mencionado por otra empresa del sector',
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${value}T00:00:00Z`));
}

function isBoeSource(value: string) {
  const hostname = new URL(value).hostname;
  return hostname === 'boe.es' || hostname === 'www.boe.es';
}

export function ProvinceEvidence({ selection }: { selection: Territory[] }) {
  const province = selection.find((item) => item.level === 'provincias');
  const municipality = selection.find((item) => item.level === 'municipios');
  const query = useProvincePresence(province?.code ?? null);

  if (!province) return (
    <aside className="province-evidence province-prompt" aria-label="Evidencia de distribuidoras" tabIndex={0}>
      <strong>Distribuidoras · evidencia provincial</strong>
      <span>El mapa marca provincias con presencias documentadas. Elige una para consultar sus fuentes. No hay una cobertura completa para {selection.length ? 'toda la comunidad' : 'España'}.</span>
    </aside>
  );

  return (
    <aside className="province-evidence" aria-label={`Evidencia de distribuidoras en ${province.title}`} tabIndex={0}>
      <div className="province-evidence-heading">
        <div>
          <span className="province-evidence-kicker">Distribuidoras · electricidad</span>
          <h2>{province.title} · {province.code}</h2>
        </div>
        <span className="province-evidence-scope">Presencias provinciales parciales</span>
      </div>
      {municipality && (
        <p className="province-evidence-warning">
          Has seleccionado {municipality.title}. Esta evidencia es provincial y no prueba cobertura en ese municipio.
        </p>
      )}
      {query.isPending && <p role="status">Cargando evidencia provincial…</p>}
      {query.isError && (
        <div className="province-evidence-error" role="alert">
          <p>No se pudo cargar o validar la evidencia provincial.</p>
          <RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>Reintentar evidencia</RetryButton>
        </div>
      )}
      {query.data && !query.isError && (
        <>
          {query.data.items.length === 0 ? (
            <p role="status">Cobertura desconocida en esta provincia: todavía no hay presencias documentadas en esta lista parcial.</p>
          ) : (
            <ul className="province-evidence-list">
              {query.data.items.map((item) => {
                const group = item.corporate_group;
                return (
                <li key={item.distributor_code}>
                  <h3>{item.distributor_name} <span>· {item.distributor_code}</span></h3>
                  {group && (
                    <p>
                      <strong>Grupo empresarial:</strong> {group.group_name}. {group.evidence.relationship_claim}{' '}
                      <a href={group.evidence.source_url} target="_blank" rel="noopener noreferrer" aria-label={`Fuente del grupo empresarial de ${item.distributor_name}`}>{group.evidence.source_title}</a>
                      {' '}· {group.evidence.published_on ? `publicada el ${formatDate(group.evidence.published_on)} · ` : ''}comprobada el {formatDate(group.evidence.checked_on)}
                    </p>
                  )}
                  <p className="province-evidence-claim">{item.evidence.geographic_claim}</p>
                  <p><strong>Confianza:</strong> {confidenceLabels[item.evidence.confidence]}</p>
                  <p><strong>Fuente:</strong> <a href={item.evidence.source_url} target="_blank" rel="noopener noreferrer">{item.evidence.source_title}</a></p>
                  <p><strong>Publicada:</strong> {item.evidence.published_on ? formatDate(item.evidence.published_on) : 'Fecha no indicada'} · <strong>Comprobada:</strong> {formatDate(item.evidence.checked_on)}</p>
                  <p><a href={item.registry_source_url} target="_blank" rel="noopener noreferrer">Fuente del código y nombre registral R1</a></p>
                  {(isBoeSource(item.registry_source_url) || isBoeSource(item.evidence.source_url)) && (
                    <p className="province-evidence-attribution">
                      {isBoeSource(item.evidence.source_url) ? 'Afirmación geográfica y datos registrales: ' : 'Código y nombre R1: '}
                      Basado en datos de la <a href="https://www.boe.es/" target="_blank" rel="noopener noreferrer">Agencia Estatal Boletín Oficial del Estado</a>. Síntesis elaborada por este proyecto.
                    </p>
                  )}
                </li>
                );
              })}
            </ul>
          )}
          <p className="province-evidence-note">Lista incompleta: no indica ausencia de otras distribuidoras, exclusividad ni cobertura de toda la provincia. El grupo empresarial no identifica una COR ni añade cobertura. Instantánea comprobada el {formatDate(query.data.snapshot_date)}; no es una fecha de inicio ni un histórico.</p>
        </>
      )}
    </aside>
  );
}
