import { territoryLevels } from '../interfaces/territory';
import type {
  Coordinate,
  TerritoryBounds,
  TerritoryLevel,
  Territory,
  TerritoryCatalog,
} from '../interfaces/territory';

export { territoryLevels } from '../interfaces/territory';
export type {
  Coordinate,
  TerritoryBounds,
  TerritoryLevel,
  Territory,
  TerritoryCatalog,
} from '../interfaces/territory';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isTerritoryLevel(value: unknown): value is TerritoryLevel {
  return value === 'ccaa' || value === 'provincias' || value === 'municipios';
}

function isCoordinate(value: unknown): value is Coordinate {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    value.every(
      (number: unknown) =>
        typeof number === 'number' && Number.isFinite(number),
    ) &&
    Math.abs(value[0]) <= 180 &&
    Math.abs(value[1]) <= 90
  );
}

function isBounds(value: unknown): value is TerritoryBounds {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    isCoordinate(value[0]) &&
    isCoordinate(value[1]) &&
    value[0][0] < value[1][0] &&
    value[0][1] < value[1][1]
  );
}

export function createTerritoryCatalog(data: unknown): TerritoryCatalog {
  if (
    !isRecord(data) ||
    data.type !== 'FeatureCollection' ||
    !Array.isArray(data.features) ||
    data.features.length > 10000
  ) {
    throw new Error('Catálogo territorial inválido');
  }
  const lists: TerritoryCatalog['lists'] = {
    ccaa: [],
    provincias: [],
    municipios: [],
  };
  const indexes: TerritoryCatalog['indexes'] = {
    ccaa: new Map(),
    provincias: new Map(),
    municipios: new Map(),
  };
  const etiquetas: TerritoryCatalog['etiquetas'] = {
    type: 'FeatureCollection',
    features: [],
  };
  for (const feature of data.features as unknown[]) {
    if (
      !isRecord(feature) ||
      feature.type !== 'Feature' ||
      !isRecord(feature.geometry) ||
      feature.geometry.type !== 'Point' ||
      !isCoordinate(feature.geometry.coordinates)
    ) {
      throw new Error('Etiqueta territorial inválida');
    }
    const properties = feature.properties;
    if (!isRecord(properties))
      throw new Error('Propiedades territoriales inválidas');
    const level = properties.capa;
    if (!isTerritoryLevel(level))
      throw new Error('Nivel territorial desconocido');
    const code =
      level === 'ccaa'
        ? properties.ccaa_ine
        : level === 'provincias'
          ? properties.cpro
          : properties.ine_municipio;
    const limites = properties.limites;
    if (
      typeof code !== 'string' ||
      !(level === 'municipios' ? /^\d{5}$/ : /^\d{2}$/).test(code) ||
      typeof properties.nombre !== 'string' ||
      !properties.nombre.trim() ||
      typeof properties.ccaa_ine !== 'string' ||
      !/^\d{2}$/.test(properties.ccaa_ine) ||
      (level !== 'ccaa' &&
        (typeof properties.cpro !== 'string' ||
          !/^\d{2}$/.test(properties.cpro))) ||
      !isBounds(limites) ||
      indexes[level].has(code)
    ) {
      throw new Error('Código, nombre o límites territoriales inválidos');
    }
    const territory: Territory = {
      level,
      code,
      title: properties.nombre,
      ccaa_ine: properties.ccaa_ine,
      cpro: typeof properties.cpro === 'string' ? properties.cpro : null,
      limites,
    };
    lists[level].push(territory);
    indexes[level].set(code, territory);
    etiquetas.features.push({
      type: 'Feature',
      id: `${level}-${code}`,
      geometry: { type: 'Point', coordinates: feature.geometry.coordinates },
      properties: { capa: level, nombre: territory.title },
    });
  }
  if (territoryLevels.some((level) => !lists[level].length))
    throw new Error('Catálogo territorial incompleto');
  for (const province of lists.provincias) {
    if (!indexes.ccaa.has(province.ccaa_ine))
      throw new Error('Provincia sin comunidad');
  }
  for (const municipality of lists.municipios) {
    const province = indexes.provincias.get(municipality.cpro ?? '');
    if (
      !province ||
      province.ccaa_ine !== municipality.ccaa_ine ||
      municipality.code.slice(0, 2) !== province.code
    ) {
      throw new Error('Municipio sin provincia compatible');
    }
  }
  for (const list of Object.values(lists))
    list.sort((a, b) => a.title.localeCompare(b.title, 'es'));
  return { lists, indexes, etiquetas };
}

export function territoryPath(
  catalog: TerritoryCatalog,
  territory: Territory,
): Territory[] {
  const community = catalog.indexes.ccaa.get(territory.ccaa_ine);
  if (!community) throw new Error('Territorio sin comunidad');
  const path = [community];
  if (territory.level !== 'ccaa') {
    const province = catalog.indexes.provincias.get(territory.cpro ?? '');
    if (!province) throw new Error('Territorio sin provincia');
    path.push(province);
  }
  if (territory.level === 'municipios') path.push(territory);
  return path;
}

export function territoryOptions(
  catalog: TerritoryCatalog | null,
  level: TerritoryLevel,
  selection: Territory[],
): Territory[] {
  if (!catalog) return [];
  if (level === 'ccaa') return catalog.lists.ccaa;
  const community = selection.find((item) => item.level === 'ccaa')?.code;
  if (level === 'provincias')
    return catalog.lists.provincias.filter(
      (item) => item.ccaa_ine === community,
    );
  const province = selection.find((item) => item.level === 'provincias')?.code;
  return catalog.lists.municipios.filter((item) => item.cpro === province);
}
