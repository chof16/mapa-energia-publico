import { SearchSelector } from './SearchSelector';
import type { SearchOption } from '../../interfaces/search-option';
import { useState } from 'react';

export function ComparisonControls({ options, selected, disabled, onChange, labelFor, showCode = true, optionDetail }: {
  options: SearchOption[]; selected: string[]; disabled: boolean;
  onChange: (selected: string[]) => void; labelFor: (code: string) => string; showCode?: boolean;
  optionDetail?: (code: string) => string;
}) {
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
        options={options}
        disabled={disabled || selected.length >= 3}
        showCode={showCode}
        optionDetail={optionDetail}
        placeholder={showCode ? "Buscar empresa por nombre o código" : "Buscar comercializadora"}
        onChange={(code) => {
          if (code) onChange([...selected, code]);
        }}
      />
      {selected.length > 0 && (
        <div className="comparison-selection" data-expanded={expanded}>
          <button
            className="comparison-selection-toggle"
            aria-expanded={expanded}
            aria-controls="comparison-selected-codes"
            onClick={() => setExpanded((current) => !current)}
          >
            {selected.length} {selected.length === 1 ? 'comparada' : 'comparadas'}
            <span aria-hidden="true">{expanded ? '⌃' : '⌄'}</span>
          </button>
          <div id="comparison-selected-codes" className="comparison-codes" aria-label="Comercializadoras comparadas">
            {selected.map((code) => (
              <button
                key={code}
                title={labelFor(code)}
                aria-label={`Quitar ${labelFor(code)} de la comparación`}
                onClick={() =>
                  onChange(selected.filter((item) => item !== code))
                }
              >
                <span>{labelFor(code)}</span>
                <span aria-hidden="true">×</span>
              </button>
            ))}
          </div>
          <button
            className="comparison-clear"
            aria-label="Limpiar comparación"
            onClick={() => onChange([])}
          >
            Limpiar
          </button>
        </div>
      )}
    </div>
  );
}
