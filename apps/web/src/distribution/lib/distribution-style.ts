import type { ExpressionSpecification } from 'maplibre-gl';
import type { ProvincePresenceSummary } from '../interfaces/distribution';

export const unknownProvinceColor = '#e5ebef';
export const oneDocumentedColor = '#a7d6c4';
export const multipleDocumentedColor = '#4c9276';
const selectedProvinceColor = '#b9d5ef';

export function documentedColor(count: number): string {
  return count > 1 ? multipleDocumentedColor : oneDocumentedColor;
}

export function documentedFill(items: ProvincePresenceSummary['items']): ExpressionSpecification | string {
  if (!items.length) return unknownProvinceColor;
  const [first, ...rest] = items;
  return [
    'case',
    ['boolean', ['feature-state', 'selected'], false],
    selectedProvinceColor,
    [
      'match',
      ['get', 'cpro'],
      first!.province_code,
      documentedColor(first!.documented_distributor_count),
      ...rest.flatMap((item) => [item.province_code, documentedColor(item.documented_distributor_count)]),
      unknownProvinceColor,
    ],
  ];
}
