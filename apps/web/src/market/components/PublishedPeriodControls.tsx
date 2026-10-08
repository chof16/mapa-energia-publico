import type { MarketState } from '../interfaces/market-state';
import { SearchSelector } from '../../components/custom/SearchSelector';

export function PublishedPeriodControls({
  market,
  onPeriodChange,
}: {
  market: MarketState;
  onPeriodChange?: () => void;
}) {
  const { enabled, quarters, period, published, change } = market;
  const year = period.slice(0, 4);
  const years = [
    ...new Set(quarters.data?.map((item) => item.period.slice(0, 4)) || []),
  ];
  const available =
    quarters.data?.filter((item) => item.period.startsWith(year)) || [];
  const disabled = !enabled || !quarters.data?.length;
  return (
    <>
      <div className="published-year-control">
        <label htmlFor="market-year">Año publicado</label>
        <SearchSelector
          id="market-year"
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
              quarters.data?.filter((item) => item.period.startsWith(value)) ||
              [];
            const next =
              candidates.find((item) => item.period.at(-1) === period.at(-1)) ||
              candidates[0];
            if (next) {
              onPeriodChange?.();
              change({ period: next.period });
            }
          }}
        />
      </div>
      <div className="published-quarter-control">
        <label htmlFor="market-period">Trimestre publicado</label>
        <SearchSelector
          id="market-period"
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
            change({ period: value });
          }}
        />
      </div>
    </>
  );
}
