import type { ReactNode } from 'react';
import { ChoiceSelector } from '../../../../components/custom/ChoiceSelector';
import type {
  EvolutionFiltersState,
  SuppliesRow,
} from '../../../interfaces/evolution';

export function EvolutionFilters({
  rows,
  filters,
  change,
  reset,
  areaFilter,
  supplies = true,
  label = 'Filtros de suministros',
}: {
  rows: SuppliesRow[];
  filters: EvolutionFiltersState;
  change: (changes: Partial<EvolutionFiltersState>) => void;
  reset: () => void;
  areaFilter?: ReactNode;
  supplies?: boolean;
  label?: string;
}) {
  return (
    <div className="table-filters" role="group" aria-label={label}>
      {areaFilter}
      <ChoiceSelector
        id="evolution-filter-year"
        label="Año"
        value={filters.year}
        onChange={(year) => change({ year })}
        options={[
          { code: '', title: 'Todos los años' },
          ...[...new Set(rows.map((row) => row.period.slice(0, 4)))]
            .sort()
            .reverse()
            .map((year) => ({ code: year, title: year })),
        ]}
      />
      <ChoiceSelector
        id="evolution-filter-quarter"
        label="Trimestre"
        value={filters.quarter}
        onChange={(quarter) => change({ quarter })}
        options={[
          { code: '', title: 'Todos los trimestres' },
          ...[1, 2, 3, 4].map((quarter) => ({
            code: String(quarter),
            title: `${quarter}.º trimestre`,
          })),
        ]}
      />
      {supplies && (
        <>
          <ChoiceSelector
            id="evolution-filter-observation"
            label="Observaciones"
            value={filters.observation}
            onChange={(observation) => change({ observation })}
            options={[
              { code: '', title: 'Todas' },
              { code: 'observed', title: 'Con observación' },
              { code: 'zero', title: 'Cero suministros' },
              { code: 'missing', title: 'Sin observación' },
            ]}
          />
          <label>
            Suministros mínimos
            <input
              type="number"
              min="0"
              step="1"
              value={filters.minimum}
              onChange={(event) => change({ minimum: event.target.value })}
            />
          </label>
        </>
      )}
      <button
        aria-label="Limpiar filtros"
        onClick={reset}
        disabled={
          !filters.year &&
          !filters.quarter &&
          !filters.observation &&
          !filters.minimum
        }
      >
        Limpiar
      </button>
    </div>
  );
}
