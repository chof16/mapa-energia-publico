// Territory catalog model shared by the map and selectors.
export const territoryLevels = ['ccaa', 'provincias', 'municipios'] as const;
export type TerritoryLevel = (typeof territoryLevels)[number];
export type Coordinate = [number, number];
export type TerritoryBounds = [Coordinate, Coordinate];

export interface Territory {
  level: TerritoryLevel;
  code: string;
  title: string;
  ccaa_ine: string;
  cpro: string | null;
  limites: TerritoryBounds;
}

interface TerritoryLabel {
  type: 'Feature';
  id: string;
  geometry: { type: 'Point'; coordinates: Coordinate };
  properties: { capa: TerritoryLevel; nombre: string };
}

export interface TerritoryCatalog {
  lists: Record<TerritoryLevel, Territory[]>;
  indexes: Record<TerritoryLevel, Map<string, Territory>>;
  etiquetas: { type: 'FeatureCollection'; features: TerritoryLabel[] };
}
