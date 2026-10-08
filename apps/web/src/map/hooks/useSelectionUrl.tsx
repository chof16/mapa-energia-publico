// Hook that keeps the territory selection in the URL.
import { useLocation, useSearchParams } from 'react-router';
import { readUrlSelection, selectionParams } from '../lib/selection-url.ts';
import type { TerritoryView } from '../lib/selection-url.ts';
import type { TerritoryCatalog, Territory } from '../lib/territories.ts';
import { readExploration, explorationParams, explorationPaths } from '../../lib/exploration-url.ts';
import type { Exploration, ExplorationPage } from '../../lib/exploration-url.ts';

export function useSelectionUrl(catalog: TerritoryCatalog | null) {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const state = readUrlSelection(catalog, params);
  const exploration = readExploration(params);

  function navigate(selection: Territory[], view: TerritoryView = 'peninsula') {
    const nextParams = explorationParams(
      selectionParams(params, selection, view),
      exploration,
    );
    if (nextParams.toString() !== params.toString()) setParams(nextParams);
  }

  const explorationLink = (changes: Partial<Exploration> & { page?: ExplorationPage }) => {
    if (changes.page) return explorationPaths[changes.page];
    const nextParams = explorationParams(params, { ...exploration, ...changes });
    return `${location.pathname}?${nextParams}`;
  };
  return { ...state, ...exploration, navigate, explorationLink };
}
