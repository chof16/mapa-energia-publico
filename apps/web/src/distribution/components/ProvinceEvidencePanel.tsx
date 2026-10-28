import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import type { Territory } from '../../map/interfaces/territory';
import { useCompactMap } from '../../map/hooks/useCompactMap';
import '../styles.css';

export function ProvinceEvidencePanel({ province, label, sector, scope, prompt, children }: {
  province?: Territory; label: string; sector: string; scope: string; prompt: ReactNode; children: ReactNode;
}) {
  const compact = useCompactMap();
  const [expanded, setExpanded] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const contentId = useId();
  useEffect(() => setExpanded(false), [province?.code, compact]);
  return <aside className={`province-evidence${province ? '' : ' province-prompt'}`} aria-label={label}
    tabIndex={compact ? undefined : 0} data-expanded={expanded} onKeyDown={(event) => {
      if (compact && expanded && event.key === 'Escape') {
        event.preventDefault(); setExpanded(false); toggle.current?.focus();
      }
    }}>
    {compact && <button ref={toggle} type="button" className="province-evidence-toggle"
      aria-expanded={expanded} aria-controls={contentId} onClick={() => setExpanded(!expanded)}>
      <span><strong>Distribuidoras</strong>{' '}<span>{province ? `${province.title} · ${province.code}` : 'Cómo leer el mapa'}</span></span>{' '}
      <span>{expanded ? 'Cerrar' : 'Ver detalles'} <span aria-hidden="true">{expanded ? '⌄' : '⌃'}</span></span>
    </button>}
    <div id={contentId} className="province-evidence-content" hidden={compact && !expanded}>
      {province ? <><div className="province-evidence-heading"><div>
        <span className="province-evidence-kicker">Distribuidoras · {sector}</span>
        <h2>{province.title} · {province.code}</h2>
      </div><span className="province-evidence-scope">{scope}</span></div>{children}</>
        : <><strong>Distribuidoras · evidencia provincial</strong><span>{prompt}</span></>}
    </div>
  </aside>;
}
