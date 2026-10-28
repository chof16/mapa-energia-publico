import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SuppliesTable } from './SuppliesTable';
import { EvolutionFilters } from './EvolutionFilters';
import { useEvolutionFilters } from '../../../hooks/useEvolutionFilters';
import type { ComponentProps } from 'react';

function chooseFilter(label: string, value: string) {
  const input = screen.getByRole('combobox', { name: label });
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value } });
  fireEvent.keyDown(input, { key: 'Enter' });
}

function FilteredSuppliesTable(
  props: Omit<ComponentProps<typeof SuppliesTable>, 'onReset'>,
) {
  const filter = useEvolutionFilters();
  return (
    <>
      <EvolutionFilters rows={props.rows} {...filter} />
      <SuppliesTable
        {...props}
        rows={props.rows.filter(filter.matches)}
        onReset={filter.reset}
      />
    </>
  );
}

describe('supplies table exploration', () => {
  it('filters years and sorts revision dates chronologically while preserving machine dates', () => {
    render(
      <FilteredSuppliesTable
        marketer="R2-001"
        area="España"
        selectedPeriod="2025T1"
        rows={[
          {
            period: '2024T4',
            supplies: 10,
            metadata_modified: '2026-02-01T01:00:00',
          },
          {
            period: '2025T1',
            supplies: 0,
            metadata_modified: '2025-12-31T23:50:00',
          },
          { period: '2025T2', metadata_modified: '2026-01-03T10:00:00' },
        ]}
      />,
    );
    const table = screen.getByRole('table');
    fireEvent.click(
      within(table).getByRole('button', { name: /Revisión del origen/ }),
    );
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent(
      '1.º trimestre de 2025',
    );
    const revision = screen.getByText('31 dic 2025');
    expect(revision).toHaveAttribute('datetime', '2025-12-31T23:50:00');
    fireEvent.click(
      within(table).getByRole('button', { name: /Revisión del origen/ }),
    );
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent(
      '4.º trimestre de 2024',
    );
    chooseFilter('Ordenar por', 'Suministros');
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent(
      '4.º trimestre de 2024',
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Orden descendente. Cambiar orden' }),
    );
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent(
      '1.º trimestre de 2025',
    );
    expect(within(table).getAllByRole('row').at(-1)).toHaveTextContent(
      'Sin observación',
    );
    chooseFilter('Año', '2025');
    expect(within(table).getAllByRole('row')).toHaveLength(3);
    expect(table).not.toHaveTextContent('2024');
    chooseFilter('Observaciones', 'missing');
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(table).toHaveTextContent('Sin observación');
    fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    fireEvent.click(within(table).getByRole('button', { name: /Trimestre/ }));
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent(
      '4.º trimestre de 2024',
    );
  });
});
