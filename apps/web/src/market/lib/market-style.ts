import type { ExpressionSpecification } from 'maplibre-gl';
import type { CommunityShare } from '../interfaces/market';

export const noDenominatorColor = '#b6bcc4';
export const missingColor = '#e8e7e1';
export function shareColor(share: number | null): string {
  if (share === null) return noDenominatorColor;
  if (share === 0) return '#eef4fb';
  if (share < 0.05) return '#c9dff5';
  if (share < 0.15) return '#91bce6';
  if (share < 0.3) return '#4b90cf';
  return '#195eac';
}
export function marketFill(
  items: CommunityShare[],
): ExpressionSpecification | string {
  if (!items.length) return missingColor;
  const first = items[0]!;
  return [
    'match',
    ['get', 'ccaa_ine'],
    first.community_code,
    shareColor(first.share),
    ...items
      .slice(1)
      .flatMap((item) => [item.community_code, shareColor(item.share)]),
    missingColor,
  ];
}
export function formatShare(share: number | null): string {
  if (share !== null && share > 0 && share < 0.0001) return '<0,01 %';
  return share === null
    ? 'Sin denominador'
    : `${new Intl.NumberFormat('es', { maximumFractionDigits: 2 }).format(share * 100)} %`;
}
