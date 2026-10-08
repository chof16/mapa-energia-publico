import { RetryButton } from '../../components/custom/RetryButton';
import type { MarketState } from '../interfaces/market-state';
import { SearchSelector } from '../../components/custom/SearchSelector';
import { PublishedPeriodControls } from './PublishedPeriodControls';
import type { ReactNode } from 'react';

export function MarketControls({
  market,
  showPeriod = true,
  onPeriodChange,
  companySearch,
}: {
  market: MarketState;
  showPeriod?: boolean;
  onPeriodChange?: () => void;
  companySearch?: ReactNode;
}) {
  const {
    enabled,
    quarters,
    marketers,
    published,
    marketer,
    codeValid,
    change,
  } = market;
  const retryQuery =
    quarters.isError || (!quarters.data && quarters.errorUpdatedAt > 0)
      ? quarters
      : marketers;
  const options = (marketers.data || []).map((item) => ({
    code: item.marketer_code,
    title: item.observed_name || 'Sin nombre observado',
  }));
  // Keep a shareable registered code when it has no observations in this quarter.
  if (codeValid && !options.some((item) => item.code === marketer))
    options.unshift({
      code: marketer,
      title: 'Código seleccionado (sin nombre observado)',
    });
  return (
    <div className="market-controls">
      {showPeriod && (
        <PublishedPeriodControls market={market} onPeriodChange={onPeriodChange} />
      )}
      {companySearch ?? (
        <div className="marketer-control">
          <label htmlFor="market-marketer">Comercializadora · código R2</label>
          <SearchSelector
            id="market-marketer"
            label="Comercializadora · código R2"
            value={marketer}
            options={options}
            disabled={!enabled || !published || !marketers.data}
            placeholder="Buscar nombre o código R2"
            onChange={(value) => change({ marketer: value })}
          />
        </div>
      )}
      {enabled && (
        <div
          className={`market-control-status${showPeriod && quarters.isSuccess && marketers.isSuccess && published && codeValid && marketer ? ' market-control-hint' : ''}`}
          role="status"
        >
          {quarters.isError
            ? 'No se pudieron cargar los trimestres.'
            : quarters.isPending
              ? null
              : !quarters.data?.length
                ? 'Todavía no hay trimestres publicados.'
                : !published
                  ? 'Este trimestre no está publicado. Elige uno de la lista.'
                  : marketers.isError
                    ? 'No se pudieron cargar las comercializadoras.'
                    : marketers.isPending
                      ? null
                      : !codeValid && marketer
                        ? 'Código de comercializadora no válido.'
                        : companySearch
                          ? null
                          : !marketer
                            ? 'Elige una comercializadora para ver sus cuotas.'
                            : showPeriod
                              ? 'Nombres observados en el trimestre. Series por código, sin grupos empresariales.'
                              : null}
          {(quarters.isError ||
            marketers.isError ||
            (quarters.isFetching &&
              quarters.errorUpdatedAt > 0 &&
              !quarters.data) ||
            (marketers.isFetching &&
              marketers.errorUpdatedAt > 0 &&
              !marketers.data)) && (
            <RetryButton
              loading={retryQuery.isFetching}
              onClick={() => void retryQuery.refetch()}
            >
              Reintentar
            </RetryButton>
          )}
        </div>
      )}
    </div>
  );
}
