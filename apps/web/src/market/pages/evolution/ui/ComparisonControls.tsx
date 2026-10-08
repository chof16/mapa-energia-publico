import { SearchSelector } from '../../../../components/custom/SearchSelector';
import type { MarketState } from '../../../interfaces/market-state';
import { formatMarketerLabel } from '../../../lib/market-format';
import { useState } from 'react';

export function ComparisonControls({ market }: { market: MarketState }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="comparison-controls">
      <label htmlFor="comparison-code">
        Añadir comercializadora a la comparación
      </label>
      <SearchSelector
        id="comparison-code"
        label="Añadir comercializadora a la comparación"
        value=""
        options={(market.marketers.data || [])
          .filter(
            (item) =>
              item.marketer_code !== market.marketer &&
              !market.comparison.includes(item.marketer_code),
          )
          .map((item) => ({
            code: item.marketer_code,
            title: item.observed_name || 'Sin nombre observado',
          }))}
        disabled={
          !market.enabled ||
          !market.codeValid ||
          !market.marketers.data ||
          market.comparison.length >= 3
        }
        placeholder="Buscar empresa por nombre o código"
        onChange={(code) => {
          if (code) market.change({ comparison: [...market.comparison, code] });
        }}
      />
      {market.comparison.length > 0 && (
        <div className="comparison-selection" data-expanded={expanded}>
          <button
            className="comparison-selection-toggle"
            aria-expanded={expanded}
            aria-controls="comparison-selected-codes"
            onClick={() => setExpanded((current) => !current)}
          >
            {market.comparison.length} {market.comparison.length === 1 ? 'comparada' : 'comparadas'}
            <span aria-hidden="true">{expanded ? '⌃' : '⌄'}</span>
          </button>
          <div id="comparison-selected-codes" className="comparison-codes" aria-label="Comercializadoras comparadas">
            {market.comparison.map((code) => (
              <button
                key={code}
                title={formatMarketerLabel(code, market.marketers.data)}
                aria-label={`Quitar ${formatMarketerLabel(code, market.marketers.data)} de la comparación`}
                onClick={() =>
                  market.change({
                    comparison: market.comparison.filter((item) => item !== code),
                  })
                }
              >
                <span>{formatMarketerLabel(code, market.marketers.data)}</span>
                <span aria-hidden="true">×</span>
              </button>
            ))}
          </div>
          <button
            className="comparison-clear"
            aria-label="Limpiar comparación"
            onClick={() => market.change({ comparison: [] })}
          >
            Limpiar
          </button>
        </div>
      )}
    </div>
  );
}
