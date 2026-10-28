import { RetryButton } from '../../components/custom/RetryButton';
import { ChoiceSelector } from '../../components/custom/ChoiceSelector';
import { useState } from 'react';
import type { ElectricityState } from '../interfaces/electricity-state';
import type { TerritoryCatalog } from '../../map/lib/territories';
import { formatShare, shareColor } from '../lib/electricity-style';
import { ElectricitySource } from './ElectricitySource';
import { filterOptions } from '../../lib/search-options';

export function ElectricitySummary({
  electricity,
  catalog,
  community,
  onSelectCommunity,
}: {
  electricity: ElectricityState;
  catalog: TerritoryCatalog | null;
  community: string | null;
  onSelectCommunity: (code: string) => void;
}) {
  const [search, setSearch] = useState('');
  const [order, setOrder] = useState('share');
  const [limit, setLimit] = useState(5);
  const context = `${electricity.period}-${electricity.marketer}`;
  const [previousContext, setPreviousContext] = useState(context);
  if (context !== previousContext) {
    setPreviousContext(context);
    setSearch('');
    setLimit(5);
  }
  if (!electricity.enabled)
    return <p className="electricity-note">Gas natural · próximamente</p>;
  const query = electricity.communities;
  const data = query.data;
  const items = filterOptions(
    (data?.items || []).map((item) => ({
      ...item,
      code: item.community_code,
      title:
        catalog?.indexes.ccaa.get(item.community_code)?.title ||
        `Comunidad ${item.community_code}`,
    })),
    search,
  ).sort((a, b) => {
    if (order === 'name') return a.title.localeCompare(b.title, 'es');
    if (order === 'supplies') return b.supplies - a.supplies;
    if (a.share === null)
      return b.share === null ? a.title.localeCompare(b.title, 'es') : 1;
    if (b.share === null) return -1;
    return b.share - a.share || a.title.localeCompare(b.title, 'es');
  });
  return (
    <section className="electricity-summary" aria-label="Cuotas autonómicas">
      <h2>Cuota de {electricity.marketer} por comunidad</h2>
      <p>
        Porcentaje de suministros con comercializadora registrada. Se excluyen
        Consumidor Directo y No Disponible. La CNMC publica esta cuota por
        comunidad, no por provincia ni municipio.
      </p>
      {electricity.published &&
        electricity.codeValid &&
        (query.isError ||
        (query.isFetching && query.errorUpdatedAt > 0 && !query.data) ? (
          <p role="alert">
            No se pudieron cargar las cuotas.{' '}
            <RetryButton
              loading={query.isFetching}
              onClick={() => void query.refetch()}
            >
              Reintentar cuotas
            </RetryButton>
          </p>
        ) : query.isPending ? (
          <p role="status">Cargando cuotas…</p>
        ) : null)}
      {data && (
        <>
          {community && (
            <p>
              Zona seleccionada:{' '}
              {catalog?.indexes.ccaa.get(community)?.title || community}.
              Puedes elegir cualquier comunidad de la lista.
            </p>
          )}
          <div className="electricity-list-controls">
            <label>
              Buscar comunidad
              <input
                type="search"
                value={search}
                placeholder="Nombre o código INE"
                onChange={(event) => {
                  setSearch(event.target.value);
                  setLimit(5);
                }}
              />
            </label>
            <ChoiceSelector
              id="community-share-order"
              label="Ordenar comunidades"
              value={order}
              onChange={setOrder}
              options={[
                { code: 'share', title: 'Mayor cuota primero' },
                { code: 'supplies', title: 'Más suministros primero' },
                { code: 'name', title: 'Nombre: A–Z' },
              ]}
            />
          </div>
          <p className="electricity-list-count">
            {items.length} comunidades · selecciona una para ver su zona
          </p>
          <ul
            className="electricity-card-list"
            aria-label={`Cuotas autonómicas · ${data.period}`}
          >
            {items.slice(0, limit).map((item) => (
              <li key={item.community_code}>
                <button
                  className="community-share-card"
                  aria-pressed={community === item.community_code}
                  disabled={!catalog?.indexes.ccaa.has(item.community_code)}
                  onClick={() => onSelectCommunity(item.community_code)}
                >
                  <strong className="electricity-card-name">{item.title}</strong>
                  <span className="community-share-value">
                    <span
                      className="share-swatch"
                      style={{ background: shareColor(item.share) }}
                    />
                    {formatShare(item.share)}
                  </span>
                  <span className="electricity-card-code">
                    {item.supplies.toLocaleString('es-ES')} suministros
                  </span>
                  {item.share !== null && (
                    <span className="community-share-track" aria-hidden="true">
                      <span
                        style={{
                          width: `${item.share * 100}%`,
                          background: shareColor(item.share),
                        }}
                      />
                    </span>
                  )}
                  <span className="electricity-card-action">
                    {community === item.community_code
                      ? 'Seleccionada'
                      : 'Ver zona →'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {!items.length && (
            <p>No hay comunidades que coincidan con la búsqueda.</p>
          )}
          {items.length > limit && (
            <button
              className="electricity-show-more"
              onClick={() => setLimit(limit + 10)}
            >
              Mostrar más comunidades ({items.length - limit})
            </button>
          )}
          {limit > 5 && (
            <button className="electricity-show-more" onClick={() => setLimit(5)}>
              Mostrar menos comunidades
            </button>
          )}
          {community &&
            !data.items.some((item) => item.community_code === community) && (
              <p>Sin datos para esta comunidad.</p>
            )}
          <details>
            <summary>Denominadores y suministros excluidos</summary>
            {data.items
              .filter((item) => !community || item.community_code === community)
              .map((item) => (
                <p key={item.community_code}>
                  <strong>
                    {catalog?.indexes.ccaa.get(item.community_code)?.title ||
                      item.community_code}
                  </strong>
                  <br />
                  Con comercializadora registrada:{' '}
                  {item.marketer_supplies.toLocaleString('es')}. Consumidor
                  Directo: {item.direct_consumer_supplies.toLocaleString('es')}.
                  No Disponible:{' '}
                  {item.unavailable_supplies.toLocaleString('es')}.
                </p>
              ))}
          </details>
          <ElectricitySource source={data} revision={data.metadata_modified} />
        </>
      )}
    </section>
  );
}
