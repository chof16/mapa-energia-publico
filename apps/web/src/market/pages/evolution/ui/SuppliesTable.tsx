import { useState } from 'react';
import type { SuppliesRow } from '../../../interfaces/evolution';
import { formatQuarter, formatRevision } from '../../../lib/market-format';
import { TableSortControls } from './TableSortControls';

type SortColumn = 'period' | 'supplies' | 'metadata_modified';
const columns: [SortColumn, string][] = [
  ['period', 'Trimestre'],
  ['supplies', 'Suministros'],
  ['metadata_modified', 'Revisión del origen'],
];

export function SuppliesTable({
  rows,
  marketer,
  area,
  selectedPeriod,
  onReset,
}: {
  rows: SuppliesRow[];
  marketer: string;
  area: string;
  selectedPeriod: string;
  onReset: () => void;
}) {
  const [sort, setSort] = useState<{ column: SortColumn; ascending: boolean }>({
    column: 'period',
    ascending: false,
  });
  const filtered = [...rows].sort((a, b) => {
    const left = a[sort.column];
    const right = b[sort.column];
    // Missing observations stay last, including when sorting descending.
    if (left === undefined)
      return right === undefined ? a.period.localeCompare(b.period) : 1;
    if (right === undefined) return -1;
    const comparison =
      typeof left === 'number' && typeof right === 'number'
        ? left - right
        : String(left).localeCompare(String(right));
    return (
      (sort.ascending ? comparison : -comparison) ||
      a.period.localeCompare(b.period)
    );
  });
  return (
    <section
      className="supplies-table-section"
      aria-label="Detalle de suministros"
    >
      <TableSortControls columns={columns} sort={sort} onChange={setSort} />
      <div className="market-table-wrap">
        <table className="supplies-table mobile-stacked-table">
          <caption>
            Suministros de {marketer} · {area}
          </caption>
          <thead>
            <tr>
              {columns.map(([column, label]) => (
                <th
                  key={column}
                  scope="col"
                  aria-sort={
                    sort.column === column
                      ? sort.ascending
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                >
                  <button
                    onClick={() =>
                      setSort({
                        column,
                        ascending:
                          sort.column === column ? !sort.ascending : true,
                      })
                    }
                  >
                    {label}{' '}
                    <span aria-hidden="true">
                      {sort.column === column
                        ? sort.ascending
                          ? '↑'
                          : '↓'
                        : '↕'}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr
                key={row.period}
                aria-current={
                  row.period === selectedPeriod ? 'true' : undefined
                }
              >
                <th scope="row">{formatQuarter(row.period)}</th>
                <td className="supplies-number" data-label="Suministros">
                  {row.supplies === undefined ? (
                    <span className="missing-observation">Sin observación</span>
                  ) : (
                    row.supplies.toLocaleString('es-ES')
                  )}
                </td>
                <td data-label="Revisión del origen">
                  <time
                    dateTime={row.metadata_modified}
                    title={row.metadata_modified}
                  >
                    {formatRevision(row.metadata_modified)}
                  </time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && (
          <p className="table-empty">
            No hay trimestres con estos filtros.{' '}
            <button onClick={onReset}>Restablecer filtros</button>
          </p>
        )}
      </div>
    </section>
  );
}
