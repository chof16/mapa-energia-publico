import { useEffect, useRef, useState } from 'react';
import { useCompactMap } from '../hooks/useCompactMap';
import { ElectricityControls } from '../../electricity/components/ElectricityControls';
import { formatQuarter } from '../../electricity/lib/electricity-format';
import type { MapExplorer } from '../interfaces/map-explorer';
import { PeriodTimeline } from './PeriodTimeline';
import { TerritoryFilters } from './TerritoryFilters';
import { MapCompanySearch } from './MapCompanySearch';
import { formatNetworkPeriod } from '../../gas/lib/distribution-format';

export function MapToolbar({ explorer }: { explorer: MapExplorer }) {
  const { sector, electricity } = explorer;
  const [filtersOpen, setFiltersOpen] = useState(
    () => window.innerWidth >= 1100 && window.innerHeight > 600,
  );
  const filterToggle = useRef<HTMLButtonElement>(null);
  const [playing, setPlaying] = useState(false);
  const compact = useCompactMap(1099);
  useEffect(() => {
    if (compact) { setFiltersOpen(false); setPlaying(false); }
  }, [compact]);
  return (
    <div className={`map-toolbar${filtersOpen ? '' : ' map-filters-collapsed'}`} data-sector={sector}>
      <div className="toolbar-title">
        <h1>
          {sector === 'electricidad' && electricity.layer === 'market'
            ? 'Cuota de una comercializadora'
            : sector === 'gas' ? 'Explorar zonas de gas' : 'Explorar zonas eléctricas'}
        </h1>
        <p id="estado-periodo">
          {sector === 'electricidad' && electricity.layer === 'market'
              ? 'Porcentaje de suministros por comunidad autónoma · límites actuales'
              : 'Límites actuales · presencias documentadas al elegir provincia'}
        </p>
      </div>
      {sector === 'electricidad' && <div className="map-toolbar-actions">
        <div className="map-layer-switch" aria-label="Vista del mapa">
          <button
            aria-pressed={electricity.layer === 'distribution'}
            onClick={() => {
              setPlaying(false);
              electricity.change({ layer: 'distribution' });
            }}
          >
            Explorar zonas
          </button>
          <button
            aria-pressed={electricity.layer === 'market'}
            onClick={() => electricity.change({ layer: 'market' })}
          >
            Cuota comercializadora
          </button>
        </div>
      </div>}
      <button
        type="button"
        ref={filterToggle}
        className="map-filters-toggle"
        aria-expanded={filtersOpen}
        aria-controls="map-filter-fields"
        onClick={() => {
          setPlaying(false);
          setFiltersOpen((open) => !open);
        }}
      >
        <span>{filtersOpen ? 'Cerrar filtros' : 'Filtros'}</span>
        <span>
          {sector === 'gas'
            ? `${explorer.current?.title || 'España'}${explorer.gasProvinceSummary.data ? ` · ${formatNetworkPeriod(explorer.gasProvinceSummary.data.source.period)}` : ''}`
            : electricity.quarters.isError || electricity.marketers.isError
            ? 'Revisar carga de datos'
            : `${explorer.current?.title || 'España'} · ${formatQuarter(electricity.period)}${electricity.marketer ? ` · ${electricity.marketer}` : ''}`}
        </span>
        <span aria-hidden="true">{filtersOpen ? '⌃' : '⌄'}</span>
      </button>
      <div
        id="map-filter-fields"
        className="map-filter-fields"
        onKeyDown={(event) => {
          if (
            event.key === 'Escape' &&
            !event.defaultPrevented &&
            filterToggle.current?.getClientRects().length
          ) {
            setFiltersOpen(false);
            filterToggle.current.focus();
          }
        }}
      >
        {sector === 'electricidad' && <ElectricityControls
          electricity={electricity}
          onPeriodChange={() => setPlaying(false)}
          companySearch={<MapCompanySearch explorer={explorer} />}
        />}
        <TerritoryFilters explorer={explorer} context={sector === 'gas' ? 'Evidencia provincial histórica; no acredita cobertura municipal ni la red actual.' : undefined} />
        <button
          type="button"
          className="map-filters-done"
          onClick={() => {
            setFiltersOpen(false);
            filterToggle.current?.focus();
          }}
        >
          Ver mapa
        </button>
      </div>
      {sector === 'electricidad' && electricity.layer === 'market' && (
        <PeriodTimeline playing={playing} setPlaying={setPlaying}
          periods={[...(electricity.quarters.data || [])].reverse().map((item) => item.period)}
          period={electricity.period} published={electricity.published}
          available={electricity.enabled && electricity.codeValid && electricity.published}
          ready={electricity.communities.isSuccess && electricity.marketers.isSuccess && (!electricity.community || electricity.areaMarketers.isSuccess)}
          loadError={electricity.communities.isError || electricity.marketers.isError || (!!electricity.community && electricity.areaMarketers.isError)}
          contextKey={`${electricity.marketer}:${electricity.community}`}
          preloadPeriod={electricity.preloadPeriod}
          changePeriod={(period, replace) => electricity.change({ period }, { replace })} />
      )}
    </div>
  );
}
