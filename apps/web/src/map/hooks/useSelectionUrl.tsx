// Hook that keeps the territory selection in the URL.
import { useLocation, useSearchParams } from 'react-router';
import { useEffect } from 'react';
import { gasMapParams } from '../../gas/lib/navigation';
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
  useEffect(() => {
    if (exploration.sector !== 'gas') return;
    const next = gasMapParams(params);
    if (next.toString() !== params.toString()) setParams(next, { replace: true });
  }, [exploration.sector, params, setParams]);

  function navigate(selection: Territory[], view: TerritoryView = 'peninsula') {
    const nextParams = explorationParams(
      selectionParams(params, selection, view),
      exploration,
    );
    if (nextParams.toString() !== params.toString()) setParams(nextParams);
  }

  const explorationLink = (changes: Partial<Exploration> & { page?: ExplorationPage }) => {
    if (changes.page) return exploration.sector === 'gas' ? '/?sector=gas' : explorationPaths[changes.page];
    if (changes.sector && changes.sector !== exploration.sector) {
      return changes.sector === 'gas' ? '/?sector=gas' : location.pathname;
    }
    const nextParams = explorationParams(params, { ...exploration, ...changes });
    return `${location.pathname}?${nextParams}`;
  };
  return { ...state, ...exploration, navigate, explorationLink };
}
