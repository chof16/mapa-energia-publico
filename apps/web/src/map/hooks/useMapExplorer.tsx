import { useEffect, useEffectEvent, useRef, useState } from 'react';
import {
  Map as MapLibreMap,
  NavigationControl,
  AttributionControl,
} from 'maplibre-gl';
import type { GeoJSONSource } from 'maplibre-gl';
import { isTerritoryLevel, territoryPath } from '../lib/territories';
import type { TerritoryLevel, Territory } from '../lib/territories';
import { useSelectionUrl } from './useSelectionUrl';
import { useTerritoryCatalog } from './useTerritoryCatalog';
import { useMarket } from '../../market/hooks/useMarket';
import { marketFill } from '../../market/lib/market-style';
import { useProvinceSummary } from '../../distribution/hooks/useProvinceSummary';
import { documentedFill } from '../../distribution/lib/distribution-style';
import {
  TILE_URL,
  SOURCE_ID,
  LEVELS,
  canaryBounds,
  mainlandBounds,
  LAYER_INFO,
  registerPmtiles,
  geometryLayers,
  fitTerritory,
} from '../lib/map-style';
export function useMapExplorer() {
  const mapNode = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const selectedId = useRef<[TerritoryLevel, string] | null>(null);
  const { data: catalog = null, isError: catalogError } = useTerritoryCatalog();
  const { selection, view, navigate, sector } =
    useSelectionUrl(catalog);
  const [mapStatus, setMapStatus] = useState<'loading' | 'ready' | 'missing'>(
    'loading',
  );
  const statusMessage =
    mapStatus === 'missing'
      ? 'Todavía no está disponible el archivo de límites.'
      : mapStatus === 'ready'
        ? 'Límites oficiales cargados'
        : 'Cargando límites administrativos…';
  const [viewingCanaries, setViewingCanaries] = useState(false);

  const current = selection.at(-1) || null;
  const community = selection.find((item) => item.level === 'ccaa') || null;
  const market = useMarket(
    sector === 'electricidad',
    false,
    community?.code || null,
  );
  const distributionEnabled = sector === 'electricidad' && market.layer === 'distribution';
  const provinceSummary = useProvinceSummary(distributionEnabled);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapStatus !== 'ready') return;
    map.setPaintProperty(
      'distribution-fill',
      'fill-color',
      documentedFill(provinceSummary.data?.items || []),
    );
    map.setLayoutProperty(
      'distribution-fill',
      'visibility',
      distributionEnabled && !!provinceSummary.data && !provinceSummary.isError ? 'visible' : 'none',
    );
  }, [mapStatus, distributionEnabled, provinceSummary.data, provinceSummary.isError]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapStatus !== 'ready') return;
    map.setPaintProperty(
      'market-fill',
      'fill-color',
      marketFill(market.enabled ? market.communities.data?.items || [] : []),
    );
    map.setLayoutProperty(
      'market-fill',
      'visibility',
      market.enabled && market.layer === 'market' && !!market.communities.data
        ? 'visible'
        : 'none',
    );
  }, [mapStatus, market.enabled, market.layer, market.communities.data]);

  function clearSelectedFeature() {
    const map = mapRef.current;
    if (selectedId.current && map?.getSource(SOURCE_ID)) {
      const [level, id] = selectedId.current;
      map.setFeatureState(
        { source: SOURCE_ID, sourceLayer: level, id },
        { selected: false },
      );
    }
    selectedId.current = null;
  }

  function selectTerritory(territory: Territory | undefined) {
    const map = mapRef.current;
    if (!territory || !catalog || !map?.getLayer(`${territory.level}-fill`))
      return;
    navigate(territoryPath(catalog, territory));
    if (current?.level === territory.level && current.code === territory.code) {
      fitTerritory(
        map,
        territory.limites,
        650,
        LAYER_INFO[territory.level].nextZoom,
      );
    }
  }

  const selectFromMap = useEffectEvent(
    (level: TerritoryLevel, code: string) => {
      selectTerritory(catalog?.indexes[level].get(code));
    },
  );

  useEffect(() => {
    if (!catalog || mapStatus !== 'ready') return;
    mapRef.current
      ?.getSource<GeoJSONSource>('etiquetas')
      ?.setData(catalog.etiquetas);
  }, [catalog, mapStatus]);

  useEffect(() => {
    const map = mapRef.current;
    if (!catalog || mapStatus !== 'ready' || !map) return;
    map.resize();
    clearSelectedFeature();
    if (current) {
      map.setFeatureState(
        { source: SOURCE_ID, sourceLayer: current.level, id: current.code },
        { selected: true },
      );
      selectedId.current = [current.level, current.code];
      fitTerritory(
        map,
        current.limites,
        650,
        LAYER_INFO[current.level].nextZoom,
      );
    } else {
      fitTerritory(map, view === 'canarias' ? canaryBounds : mainlandBounds);
    }
  }, [catalog, mapStatus, current, view]);

  function changeTerritory(level: TerritoryLevel, code: string) {
    if (code) {
      selectTerritory(catalog?.indexes[level].get(code));
      return;
    }
    const parent = selection.find(
      (item) => item.level === LEVELS[LEVELS.indexOf(level) - 1],
    );
    if (parent) selectTerritory(parent);
    else showOverview(false);
  }

  useEffect(() => {
    if (!mapNode.current) return;
    registerPmtiles();
    const map = new MapLibreMap({
      container: mapNode.current,
      center: [-3.7, 40.2],
      zoom: 4.45,
      minZoom: 2,
      maxZoom: 13,
      renderWorldCopies: false,
      trackResize: false,
      style: {
        version: 8,
        glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
        sources: {
          [SOURCE_ID]: {
            type: 'vector',
            url: `pmtiles://${new URL(TILE_URL, window.location.href).href}`,
            promoteId: {
              ccaa: 'ccaa_ine',
              provincias: 'cpro',
              municipios: 'ine_municipio',
            },
            attribution: '© IGN/CNIG',
          },
          etiquetas: {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          },
        },
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: { 'background-color': '#f4f2ec' },
          },
        ],
      },
      attributionControl: false,
      cooperativeGestures: true,
    });
    mapRef.current = map;
    fitTerritory(map, mainlandBounds, 0);
    // Observe each frame during panel transitions and redraw after resizing.
    let previousWidth = mapNode.current.clientWidth;
    let previousHeight = mapNode.current.clientHeight;
    const observer = new ResizeObserver(() => {
      const node = mapNode.current;
      if (!node) return;
      const width = node.clientWidth;
      const height = node.clientHeight;
      if (
        !width ||
        !height ||
        (width === previousWidth && height === previousHeight)
      )
        return;
      previousWidth = width;
      previousHeight = height;
      map.resize();
      map.redraw();
    });
    observer.observe(mapNode.current);
    map.on('moveend', () => {
      const center = map.getCenter();
      setViewingCanaries(center.lng < -12 && center.lat < 32);
    });

    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new AttributionControl({ compact: true }), 'bottom-right');

    map.on('load', () => {
      geometryLayers().forEach((layer) => map.addLayer(layer));
      setMapStatus('ready');
    });
    map.on('error', (event) => {
      const message = event.error?.message || '';
      if (
        /404|Failed to fetch|NetworkError|Not Found|Wrong magic number|Invalid PMTiles/i.test(
          message,
        )
      ) {
        setMapStatus('missing');
      }
    });

    map.on('click', (event) => {
      const visible = LEVELS.filter((level) => map.getLayer(`${level}-fill`));
      const features = map.queryRenderedFeatures(event.point, {
        layers: visible.map((level) => `${level}-fill`),
      });
      const feature = features[0];
      if (!feature) return;
      const level =
        'source-layer' in feature.layer
          ? feature.layer['source-layer']
          : undefined;
      if (!isTerritoryLevel(level)) return;
      const properties = feature.properties || {};
      const featureId =
        level === 'ccaa'
          ? properties.ccaa_ine
          : level === 'provincias'
            ? properties.cpro
            : properties.ine_municipio;
      if (typeof featureId === 'string') selectFromMap(level, featureId);
    });

    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  function showOverview(canaries = false) {
    navigate([], canaries ? 'canarias' : 'peninsula');
    if (!current && mapRef.current)
      fitTerritory(mapRef.current, canaries ? canaryBounds : mainlandBounds);
  }

  function goBack() {
    if (selection.length <= 1) {
      showOverview(viewingCanaries);
      return;
    }
    selectTerritory(selection.at(-2));
  }

  function goToBreadcrumb(index: number) {
    if (index === selection.length - 1) return;
    if (index < 0) {
      showOverview(false);
      return;
    }
    selectTerritory(selection[index]);
  }

  return {
    mapNode,
    market,
    provinceSummary,
    community,
    catalog,
    catalogError,
    selection,
    current,
    mapStatus,
    statusMessage,
    sector,
    changeTerritory,
    showOverview,
    goBack,
    goToBreadcrumb,
  };
}
