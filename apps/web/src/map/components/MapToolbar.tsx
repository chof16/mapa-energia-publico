import { useRef, useState } from 'react';
import { MarketControls } from '../../market/components/MarketControls';
import { formatQuarter } from '../../market/lib/market-format';
import type { MapExplorer } from '../interfaces/map-explorer';
import { PeriodTimeline } from './PeriodTimeline';
import { TerritoryFilters } from './TerritoryFilters';
import { MapCompanySearch } from './MapCompanySearch';

export function MapToolbar({ explorer }: { explorer: MapExplorer }) {
  const { sector, market } = explorer;
  const [filtersOpen, setFiltersOpen] = useState(
    () => window.innerWidth >= 1100 && window.innerHeight > 600,
  );
  const filterToggle = useRef<HTMLButtonElement>(null);
  const [playing, setPlaying] = useState(false);
  return (
    <div className={`map-toolbar${filtersOpen ? '' : ' map-filters-collapsed'}`}>
      <div className="toolbar-title">
        <h1>
          {market.layer === 'market'
            ? 'Cuota de una comercializadora'
            : 'Explorar zonas eléctricas'}
        </h1>
        <p id="estado-periodo">
          {sector === 'gas'
            ? 'Gas: datos y periodo pendientes'
            : market.layer === 'market'
              ? 'Porcentaje de suministros por comunidad autónoma · límites actuales'
              : 'Límites actuales · presencias documentadas al elegir provincia'}
        </p>
      </div>
      <div className="map-toolbar-actions">
        <div className="map-layer-switch" aria-label="Vista del mapa">
          <button
            aria-pressed={market.layer === 'distribution'}
            onClick={() => {
              setPlaying(false);
              market.change({ layer: 'distribution' });
            }}
          >
            Explorar zonas
          </button>
          <button
            disabled={sector === 'gas'}
            aria-pressed={market.layer === 'market'}
            onClick={() => market.change({ layer: 'market' })}
          >
            Cuota comercializadora
          </button>
        </div>
      </div>
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
          {market.quarters.isError || market.marketers.isError
            ? 'Revisar carga de datos'
            : sector === 'gas'
              ? 'Gas pendiente'
              : `${explorer.current?.title || 'España'} · ${formatQuarter(market.period)}${market.marketer ? ` · ${market.marketer}` : ''}`}
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
        <MarketControls
          market={market}
          onPeriodChange={() => setPlaying(false)}
          companySearch={<MapCompanySearch explorer={explorer} />}
        />
        <TerritoryFilters explorer={explorer} />
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
      {sector === 'electricidad' && market.layer === 'market' && (
        <PeriodTimeline market={market} playing={playing} setPlaying={setPlaying} />
      )}
    </div>
  );
}
