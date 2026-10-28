import { loadGasNetworkDistributors, loadGasNetworkProvinces } from '../actions/load-gas-distribution';
import { useGasQuery } from './useGasQuery';

export function useGasProvinceSummary(enabled: boolean) {
  return useGasQuery(['distribution', 'provinces'], loadGasNetworkProvinces, enabled);
}

export function useGasProvinceDistributors(code: string | null, loadId: string | null) {
  return useGasQuery(['distribution', 'province', code, loadId],
    (signal) => loadGasNetworkDistributors(code!, loadId!, signal), !!code && !!loadId);
}
