export function formatNetworkPeriod(period: string) {
  return new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${period}-01T00:00:00Z`));
}
