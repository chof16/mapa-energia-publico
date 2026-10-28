export function shareAxisMaximum(values: Array<number | null | undefined>): number {
  const peak = Math.max(0, ...values.map((value) => value ?? 0));
  return Math.min(1, Math.max(0.05, Math.ceil(peak * 22) / 20));
}
