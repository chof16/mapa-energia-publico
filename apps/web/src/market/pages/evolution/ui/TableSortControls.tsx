import { useId } from 'react';
import { ChoiceSelector } from '../../../../components/custom/ChoiceSelector';

export function TableSortControls<Column extends string>({
  columns,
  sort,
  onChange,
}: {
  columns: [Column, string][];
  sort: { column: Column; ascending: boolean };
  onChange: (sort: { column: Column; ascending: boolean }) => void;
}) {
  const id = useId();
  return (
    <div className="compact-table-sort">
      <ChoiceSelector
        id={id}
        label="Ordenar por"
        options={columns.map(([code, title]) => ({ code, title }))}
        value={sort.column}
        onChange={(value) => {
          const column = columns.find(([code]) => code === value)?.[0];
          if (column) onChange({ ...sort, column });
        }}
      />
      <button
        type="button"
        aria-label={`Orden ${sort.ascending ? 'ascendente' : 'descendente'}. Cambiar orden`}
        onClick={() => onChange({ ...sort, ascending: !sort.ascending })}
      >
        <span aria-hidden="true">{sort.ascending ? '↑' : '↓'}</span>{' '}
        {sort.ascending ? 'Ascendente' : 'Descendente'}
      </button>
    </div>
  );
}
