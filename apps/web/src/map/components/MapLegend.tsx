import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { useCompactMap } from '../hooks/useCompactMap';

export function MapLegend({ children }: { children: ReactNode }) {
  const compact = useCompactMap();
  const [expanded, setExpanded] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const contentId = useId();
  useEffect(() => setExpanded(false), [compact]);
  return <div className="map-legend" onKeyDown={(event) => {
    if (compact && event.key === 'Escape') {
      event.preventDefault(); setExpanded(false); toggle.current?.focus();
    }
  }}>
    {compact && <button ref={toggle} type="button" className="map-legend-toggle" aria-controls={contentId}
      aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Cerrar leyenda' : 'Leyenda'}</button>}
    <div id={contentId} className="map-legend-content" hidden={compact && !expanded}>{children}</div>
  </div>;
}
