export function EvolutionDisplayControls({ value, onChange }: {
  value: 'chart' | 'table';
  onChange: (value: 'chart' | 'table') => void;
}) {
  return <div className="evolution-context evolution-display-controls" role="group" aria-label="Presentación de la evolución">
    <button aria-label="Gráfico" aria-pressed={value === 'chart'} onClick={() => onChange('chart')}>
      <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4v16h16M7 15l4-5 4 3 5-7" /></svg>
    </button>
    <button aria-label="Tabla" aria-pressed={value === 'table'} onClick={() => onChange('table')}>
      <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M3 15h18M10 10v10" /></svg>
    </button>
  </div>;
}
