import type { Marketer } from '../interfaces/market';

export function formatMarketerLabel(code: string, marketers?: Marketer[]) {
  const name = marketers?.find((item) => item.marketer_code === code)?.observed_name;
  return `${name || 'Nombre no disponible'} · ${code}`;
}

export function formatQuarter(period: string) {
  return `${period.at(-1)}.º trimestre de ${period.slice(0, 4)}`;
}

// CNMC revisions without an offset carry a calendar date, not a local timezone.
export function formatRevision(revision: string) {
  const date = new Date(`${revision.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime())
    ? 'Fecha no disponible'
    : new Intl.DateTimeFormat('es-ES', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC',
      }).format(date);
}
