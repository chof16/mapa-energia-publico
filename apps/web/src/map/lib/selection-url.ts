// Territory selection synchronization with the URL.
import { territoryPath } from './territories.ts';
import type { TerritoryCatalog, Territory } from './territories.ts';

export type TerritoryView = 'peninsula' | 'canarias';
export interface UrlSelection {
  selection: Territory[];
  view: TerritoryView;
}

const territoryParams = {
  ccaa: 'autonomous_community',
  provincias: 'province',
  municipios: 'municipality',
};

export function selectionParams(
  params: URLSearchParams,
  selection: Territory[],
  view: TerritoryView = 'peninsula',
): URLSearchParams {
  const nextParams = new URLSearchParams(params);
  for (const name of [
    ...Object.values(territoryParams),
    'view',
    'ccaa',
    'provincia',
    'municipio',
    'vista',
  ])
    nextParams.delete(name);
  for (const territory of selection)
    nextParams.set(territoryParams[territory.level], territory.code);
  if (!selection.length && view === 'canarias')
    nextParams.set('view', 'canary_islands');
  return nextParams;
}

export function readUrlSelection(
  catalog: TerritoryCatalog | null,
  params: URLSearchParams,
): UrlSelection {
  if (!catalog) return { selection: [], view: 'peninsula' };
  const community = catalog.indexes.ccaa.get(
    params.get('autonomous_community') ?? '',
  );
  const province = catalog.indexes.provincias.get(params.get('province') ?? '');
  const municipality = catalog.indexes.municipios.get(
    params.get('municipality') ?? '',
  );
  const compatibleCommunity = (territory: Territory) =>
    !params.has('autonomous_community') ||
    community?.code === territory.ccaa_ine;
  let territory = community;
  if (province && compatibleCommunity(province)) territory = province;
  if (
    municipality &&
    compatibleCommunity(municipality) &&
    (!params.has('province') || province?.code === municipality.cpro)
  )
    territory = municipality;
  const selection = territory ? territoryPath(catalog, territory) : [];
  const view =
    !selection.length && params.get('view') === 'canary_islands'
      ? 'canarias'
      : 'peninsula';
  return { selection, view };
}
