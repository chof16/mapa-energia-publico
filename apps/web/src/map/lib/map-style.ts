import { addProtocol } from 'maplibre-gl';
import type {
  Map as MapLibreMap,
  FillLayerSpecification,
  LayerSpecification,
  LineLayerSpecification,
  SymbolLayerSpecification,
} from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import { territoryLevels } from './territories';
import type { TerritoryBounds } from './territories';
export const TILE_URL =
  import.meta.env.VITE_ADMIN_PMTILES_URL || '/data/administrativo.pmtiles';
export const labelsUrl =
  import.meta.env.VITE_ADMIN_LABELS_URL ||
  TILE_URL.replace(/\.pmtiles(?=\?|$)/, '.etiquetas.geojson');
export const SOURCE_ID = 'territorio';
export const LEVELS = territoryLevels;
export const canaryBounds: TerritoryBounds = [
  [-18.3, 27.5],
  [-13.3, 29.5],
];
export const mainlandBounds: TerritoryBounds = [
  [-9.6, 35.1],
  [4.4, 43.9],
];
const levelZooms = {
  ccaa: [0, 5.8],
  provincias: [5.8, 8.2],
  municipios: [8.2, 24],
};
export const LAYER_INFO = {
  ccaa: {
    title: 'Comunidad autónoma',
    label: 'Comunidad autónoma',
    nextZoom: 6.2,
  },
  provincias: { title: 'Provincia', label: 'Provincia', nextZoom: 8.6 },
  municipios: { title: 'Municipio', label: 'Municipio', nextZoom: 10.4 },
};

let protocolRegistered = false;

export function registerPmtiles() {
  if (protocolRegistered) return;
  const protocol = new Protocol();
  addProtocol('pmtiles', protocol.tile);
  protocolRegistered = true;
}

export function geometryLayers(): LayerSpecification[] {
  return [
    ...LEVELS.map<FillLayerSpecification>((level) => ({
      id: `${level}-fill`,
      type: 'fill',
      source: SOURCE_ID,
      'source-layer': level,
      minzoom: levelZooms[level][0],
      maxzoom: levelZooms[level][1],
      paint: {
        'fill-color': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          '#b9d5ef',
          level === 'ccaa'
            ? '#e5ebef'
            : level === 'provincias'
              ? '#ebeff2'
              : '#f0f2f3',
        ],
        'fill-opacity': 0.92,
      },
    })),
    // Provincial tint means documented presence somewhere within a province.
    // It stops before municipal zoom because these claims are not municipal data.
    {
      id: 'distribution-fill', type: 'fill', source: SOURCE_ID, 'source-layer': 'provincias',
      minzoom: 0, maxzoom: levelZooms.municipios[0],
      layout: { visibility: 'none' },
      paint: { 'fill-color': '#e5ebef', 'fill-opacity': 0.78 },
    },
    // Market data belongs only to autonomous communities, at every zoom.
    {
      id: 'market-fill', type: 'fill', source: SOURCE_ID, 'source-layer': 'ccaa',
      layout: { visibility: 'none' }, paint: { 'fill-color': '#e8e7e1', 'fill-opacity': 1 },
    },
    // Draw parent boundaries above all fills and fine lines.
    ...[...LEVELS].reverse().map<LineLayerSpecification>((level) => ({
      id: `${level}-line`,
      type: 'line',
      source: SOURCE_ID,
      'source-layer': level,
      minzoom: levelZooms[level][0],
      paint: {
        'line-color':
          level === 'ccaa'
            ? '#3c638a'
            : level === 'provincias'
              ? '#819bb3'
              : '#b3c2d0',
        'line-width':
          level === 'ccaa'
            ? ['interpolate', ['linear'], ['zoom'], 4, 1.5, 8, 2.4, 13, 3.5]
            : level === 'provincias'
              ? 1.1
              : 0.6,
      },
    })),
    ...LEVELS.map<SymbolLayerSpecification>((level) => ({
      id: `${level}-label`,
      type: 'symbol',
      source: 'etiquetas',
      filter: ['==', ['get', 'capa'], level],
      minzoom: levelZooms[level][0],
      maxzoom: levelZooms[level][1],
      layout: {
        'text-field': ['coalesce', ['get', 'nombre'], ['get', 'nameunit']],
        'text-font': ['Open Sans Regular'],
        'text-size': level === 'ccaa' ? 12 : level === 'provincias' ? 11 : 10,
        'text-max-width': 9,
        'text-allow-overlap': false,
        'symbol-placement': 'point',
      },
      paint: {
        'text-color': '#2a4058',
        'text-halo-color': '#fffefa',
        'text-halo-width': 1.4,
      },
    })),
  ];
}

export function fitTerritory(
  map: MapLibreMap,
  bounds: TerritoryBounds,
  duration = 650,
  maxZoom = 5.6,
) {
  if (!map.getContainer().clientWidth || !map.getContainer().clientHeight)
    return;
  const compact = map.getContainer().clientHeight < 450;
  map.fitBounds(bounds, {
    padding: { top: 40, bottom: compact ? 95 : 180, left: 28, right: 28 },
    maxZoom,
    duration: duration,
  });
}
