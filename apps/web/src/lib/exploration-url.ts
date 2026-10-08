// Page identity lives in the route; query parameters carry shared filters.
export type ExplorationPage = 'mapa' | 'evolucion' | 'referencia';
export type EnergySector = 'electricidad' | 'gas';
export interface Exploration {
  sector: EnergySector;
}

export const explorationPaths: Record<ExplorationPage, string> = {
  mapa: '/',
  evolucion: '/evolution',
  referencia: '/regulated-tariff',
};

export function readExploration(params: URLSearchParams): Exploration {
  return {
    sector: params.get('sector') === 'gas' ? 'gas' : 'electricidad',
  };
}

export function explorationParams(
  params: URLSearchParams,
  state: Exploration,
): URLSearchParams {
  const nextParams = new URLSearchParams(params);
  nextParams.delete('pestana');
  nextParams.delete('active_tab');
  nextParams.delete('anno');
  nextParams.set(
    'sector',
    state.sector === 'electricidad' ? 'electricity' : 'gas',
  );
  if (nextParams.has('period')) nextParams.delete('year');
  return nextParams;
}
