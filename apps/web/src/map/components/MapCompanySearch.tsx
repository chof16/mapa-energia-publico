import { useEffect, useRef, useState } from 'react';
import { SearchSelector } from '../../components/custom/SearchSelector';
import { RetryButton } from '../../components/custom/RetryButton';
import { MarketSummary } from '../../market/components/MarketSummary';
import { MarketSource } from '../../market/components/MarketSource';
import { formatQuarter } from '../../market/lib/market-format';
import type { MapExplorer } from '../interfaces/map-explorer';

export function MapCompanySearch({ explorer }: { explorer: MapExplorer }) {
  const { market, community } = explorer;
  const query = community ? market.areaMarketers : market.marketers;
  const [detailsOpen, setDetailsOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const items = [...(query.data || [])].sort(
    (a, b) => b.supplies - a.supplies || a.marketer_code.localeCompare(b.marketer_code),
  );
  const selected = items.find((item) => item.marketer_code === market.marketer);
  const quarter = market.quarters.data?.find(
    (item) => item.period === market.period,
  );
  const options = items.map((item) => ({
    code: item.marketer_code,
    title: item.observed_name || 'Sin nombre observado',
  }));
  if (market.codeValid && !selected) {
    options.unshift({
      code: market.marketer,
      title:
        market.marketers.data?.find((item) => item.marketer_code === market.marketer)
          ?.observed_name || 'Código seleccionado (sin nombre observado)',
    });
  }

  useEffect(() => {
    if (!detailsOpen) return;
    function closeOutside(event: PointerEvent) {
      if (
        event.target instanceof Node &&
        !panel.current?.contains(event.target) &&
        !trigger.current?.contains(event.target)
      ) setDetailsOpen(false);
    }
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [detailsOpen]);

  return (
    <div
      className="marketer-control company-search"
      onKeyDown={(event) => {
        if (event.key === 'Escape' && !event.defaultPrevented && detailsOpen) {
          event.preventDefault();
          setDetailsOpen(false);
          trigger.current?.focus();
        }
      }}
    >
      <label htmlFor="market-marketer">Comercializadora · código R2</label>
      <SearchSelector
        id="market-marketer"
        label="Comercializadora · código R2"
        value={market.marketer}
        options={options}
        disabled={!market.enabled || !market.published || !query.data}
        placeholder="Buscar empresa y ver suministros"
        describedBy="company-search-context"
        optionDetail={(code) => {
          const item = items.find((entry) => entry.marketer_code === code);
          return item
            ? `${item.supplies.toLocaleString('es-ES')} suministros`
            : 'Sin observaciones en este ámbito';
        }}
        onChange={(marketer) => {
          setDetailsOpen(false);
          market.change({ marketer, ...(marketer ? { layer: 'market' } : {}) });
        }}
      />
      <div className="company-search-summary">
        <span id="company-search-context">
          {community?.title || 'España'} · {formatQuarter(market.period)}
          {market.enabled && market.published && query.isSuccess && (
            <strong>
              {selected
                ? `${selected.supplies.toLocaleString('es-ES')} suministros`
                : market.marketer
                  ? 'Sin observaciones en este ámbito'
                  : `${items.length} comercializadoras · más suministros primero`}
            </strong>
          )}
        </span>
        {market.enabled && market.published && quarter && (
          <button
            ref={trigger}
            type="button"
            className="company-details-trigger"
            aria-expanded={detailsOpen}
            aria-controls="company-data"
            onClick={() => setDetailsOpen((open) => !open)}
          >
            {market.codeValid ? 'Cuotas y fuente' : 'Fuente CNMC'} <span aria-hidden="true">{detailsOpen ? '⌃' : '⌄'}</span>
          </button>
        )}
      </div>
      {market.enabled && market.published && community && query.isPending && (
        <p role="status" className="market-note">Cargando suministros de la comunidad…</p>
      )}
      {market.enabled && market.published && community && (query.isError || (query.isFetching && query.errorUpdatedAt > 0 && !query.data)) && (
        <p role="alert" className="market-note">
          No se pudieron cargar las comercializadoras de la zona.{' '}
          <RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>
            Reintentar comercializadoras
          </RetryButton>
        </p>
      )}
      {detailsOpen && market.enabled && market.published && quarter && (
        <div
          ref={panel}
          id="company-data"
          className="company-data"
          role="region"
          aria-label="Datos de la comercializadora"
        >
          {market.codeValid ? (
            <MarketSummary
              market={market}
              catalog={explorer.catalog}
              community={community?.code || null}
              onSelectCommunity={(code) => explorer.changeTerritory('ccaa', code)}
            />
          ) : (
            <>
              <p className="market-note">
                Suministros de España o de toda la comunidad autónoma, también al
                seleccionar una provincia o municipio. No indican cobertura de distribuidoras.
              </p>
              <MarketSource source={quarter} revision={quarter.metadata_modified} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
