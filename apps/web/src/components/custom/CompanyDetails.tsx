import { useEffect, useRef, useState, type ReactNode } from 'react';

export function CompanyDetails({ search, summary, label, children, enabled = true, status, selectionKey }: {
  search: ReactNode; summary: ReactNode; label: string; children: ReactNode; enabled?: boolean; status?: ReactNode; selectionKey: string;
}) {
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => setOpen(false), [selectionKey]);
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (event.target instanceof Node && !panel.current?.contains(event.target) && !trigger.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);
  return <div className="marketer-control company-search" onKeyDown={(event) => {
    if (event.key === 'Escape' && !event.defaultPrevented && open) { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
  }}>
    {search}
    <div className="company-search-summary"><span id="company-search-context">{summary}</span>{enabled && <button ref={trigger} className="company-details-trigger" type="button"
      aria-expanded={open} aria-controls="company-data" onClick={() => setOpen(!open)}>{label} <span aria-hidden="true">{open ? '⌃' : '⌄'}</span></button>}</div>
    {status}
    {open && enabled && <div ref={panel} id="company-data" className="company-data" role="region" aria-label="Datos de la comercializadora">{children}</div>}
  </div>;
}
