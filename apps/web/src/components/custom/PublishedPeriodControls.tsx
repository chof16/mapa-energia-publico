import { SearchSelector } from './SearchSelector';

export function PublishedPeriodControls({
  periods,
  period,
  enabled,
  onChange,
  onPeriodChange,
}: {
  periods: { period: string }[] | undefined;
  period: string;
  enabled: boolean;
  onChange: (period: string) => void;
  onPeriodChange?: () => void;
}) {
  const published = periods?.some((item) => item.period === period);
  const year = period.slice(0, 4);
  const years = [
    ...new Set(periods?.map((item) => item.period.slice(0, 4)) || []),
  ];
  const available =
    periods?.filter((item) => item.period.startsWith(year)) || [];
  const disabled = !enabled || !periods?.length;
  return (
    <>
      <div className="published-year-control">
        <label htmlFor="electricity-year">Año publicado</label>
        <SearchSelector
          id="electricity-year"
          value={year}
          disabled={disabled}
          showCode={false}
          clearable={false}
          label="Año publicado"
          placeholder="Elegir año publicado"
          options={[
            ...(!years.includes(year)
              ? [{ code: year, title: year || 'Cargando años…' }]
              : []),
            ...years.map((value) => ({ code: value, title: value })),
          ]}
          onChange={(value) => {
            const candidates =
              periods?.filter((item) => item.period.startsWith(value)) ||
              [];
            const next =
              candidates.find((item) => item.period.at(-1) === period.at(-1)) ||
              candidates[0];
            if (next) {
              onPeriodChange?.();
              onChange(next.period);
            }
          }}
        />
      </div>
      <div className="published-quarter-control">
        <label htmlFor="electricity-period">Trimestre publicado</label>
        <SearchSelector
          id="electricity-period"
          value={period}
          disabled={disabled}
          showCode={false}
          clearable={false}
          label="Trimestre publicado"
          placeholder="Elegir trimestre publicado"
          options={[
            ...(!published
              ? [
                  {
                    code: period,
                    title: period
                      ? `${period.at(-1)}.º trimestre (no publicado)`
                      : 'Cargando trimestres…',
                  },
                ]
              : []),
            ...available.map((item) => ({
              code: item.period,
              title: `${item.period.at(-1)}.º trimestre`,
            })),
          ]}
          onChange={(value) => {
            onPeriodChange?.();
            onChange(value);
          }}
        />
      </div>
    </>
  );
}
