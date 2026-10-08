import type {
  TerritoryBounds,
  TerritoryLevel,
} from '../../map/interfaces/territory';

// A small, coherent IGN-shaped catalog. Bounds and anchors are illustrative test data.
function label(
  level: TerritoryLevel,
  name: string,
  community: string,
  province: string | null,
  municipality: string | null,
  bounds: TerritoryBounds,
) {
  return {
    type: 'Feature',
    geometry: {
      type: 'Point',
      coordinates: [
        (bounds[0][0] + bounds[1][0]) / 2,
        (bounds[0][1] + bounds[1][1]) / 2,
      ],
    },
    properties: {
      capa: level,
      nombre: name,
      ccaa_ine: community,
      cpro: province,
      ine_municipio: municipality,
      limites: bounds,
    },
  };
}

export const territoryLabels = {
  type: 'FeatureCollection',
  features: [
    label('ccaa', 'Comunidad de Madrid', '13', null, null, [
      [-4.6, 39.8],
      [-3, 41.2],
    ]),
    label('provincias', 'Madrid', '13', '28', null, [
      [-4.6, 39.8],
      [-3, 41.2],
    ]),
    label('municipios', 'Madrid', '13', '28', '28079', [
      [-3.9, 40.3],
      [-3.5, 40.7],
    ]),
    label('municipios', 'Alcalá de Henares', '13', '28', '28005', [
      [-3.5, 40.4],
      [-3.2, 40.6],
    ]),
    label('ccaa', 'Canarias', '05', null, null, [
      [-18.3, 27.5],
      [-13.3, 29.5],
    ]),
    label('provincias', 'Las Palmas', '05', '35', null, [
      [-16, 27.7],
      [-13.3, 29.5],
    ]),
    label('municipios', 'Las Palmas de Gran Canaria', '05', '35', '35016', [
      [-15.6, 28],
      [-15.3, 28.2],
    ]),
  ],
};
