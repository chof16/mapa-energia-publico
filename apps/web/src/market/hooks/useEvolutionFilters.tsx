import { useState } from 'react';
import type {
  EvolutionFiltersState,
  SuppliesRow,
} from '../interfaces/evolution';

const emptyFilters: EvolutionFiltersState = {
  year: '',
  quarter: '',
  observation: '',
  minimum: '',
};
export function useEvolutionFilters() {
  const [filters, setFilters] = useState(emptyFilters);
  const matchesPeriod = (period: string) =>
    (!filters.year || period.startsWith(filters.year)) &&
    (!filters.quarter || period.endsWith(filters.quarter));
  const matches = (row: SuppliesRow) =>
    matchesPeriod(row.period) &&
    (!filters.observation ||
      (filters.observation === 'missing'
        ? row.supplies === undefined
        : filters.observation === 'zero'
          ? row.supplies === 0
          : row.supplies !== undefined)) &&
    (!filters.minimum ||
      (row.supplies !== undefined && row.supplies >= Number(filters.minimum)));
  return {
    filters,
    matches,
    matchesPeriod,
    change: (changes: Partial<EvolutionFiltersState>) =>
      setFilters((current) => ({ ...current, ...changes })),
    reset: () => setFilters(emptyFilters),
  };
}
