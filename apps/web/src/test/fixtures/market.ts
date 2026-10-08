// Synthetic API fixtures; no company or market facts are asserted by these values.
export const marketSource = {
  source_url: 'https://data.cnmc.es/test',
  attribution:
    'Origen de los datos: Comisión Nacional de los Mercados y la Competencia',
  license_id: 'CC-BY-SA-4.0',
  license_url: 'https://creativecommons.org/licenses/by-sa/4.0/',
  conditions_url: 'https://data.cnmc.es/condiciones-de-uso',
};
export const marketRevision = '2026-09-16T09:54:27.287603';
export const marketQuarters = ['2025T4', '2025T2', '2025T1'].map((period) => ({
  ...marketSource,
  period,
  metadata_modified: marketRevision,
}));
export function marketResponse(
  url: string,
  params: Record<string, unknown> = {},
) {
  const period = String(params.period || '2025T4');
  if (url.endsWith('/quarters'))
    return { sector: 'electricity', quarters: marketQuarters };
  if (url.endsWith('/shares'))
    return {
      sector: 'electricity',
      period,
      community_code: params.community_code || null,
      items: [
        {
          marketer_code: 'R2-001',
          observed_name: 'Comercializadora de prueba',
          supplies: 25,
          share: 0.25,
        },
        {
          marketer_code: 'R2-002',
          observed_name: 'Otra comercializadora de prueba',
          supplies: 75,
          share: 0.75,
        },
      ],
    };
  if (url.includes('/communities/'))
    return {
      ...marketSource,
      sector: 'electricity',
      period,
      marketer_code: url.split('/').at(-1),
      metadata_modified: marketRevision,
      denominator: 'supplies_with_registered_marketer',
      items: [
        {
          community_code: '13',
          supplies: period === '2025T1' ? 25 : 0,
          marketer_supplies: 100,
          share: period === '2025T1' ? 0.25 : 0,
          direct_consumer_supplies: 2,
          unavailable_supplies: 3,
        },
        {
          community_code: '05',
          supplies: 0,
          marketer_supplies: 0,
          share: null,
          direct_consumer_supplies: 5,
          unavailable_supplies: 0,
        },
      ],
    };
  if (url.includes('/share-series/'))
    return {
      sector: 'electricity',
      marketer_code: url.split('/').at(-1),
      community_code: params.community_code || null,
      denominator: 'supplies_with_registered_marketer',
      series: marketQuarters.map((quarter, index) => ({
        ...quarter,
        supplies:
          index === 1
            ? 0
            : url.endsWith('R2-002')
              ? index === 2
                ? 75
                : 10
              : index === 2
                ? 25
                : 0,
        marketer_supplies: index === 1 ? 0 : 100,
        share:
          index === 1
            ? null
            : url.endsWith('R2-002')
              ? index === 2
                ? 0.75
                : 0.1
              : index === 2
                ? 0.25
                : 0,
        direct_consumer_supplies: 2,
        unavailable_supplies: 3,
      })),
    };
  if (url.includes('/series/'))
    return {
      ...marketSource,
      sector: 'electricity',
      marketer_code: url.split('/').at(-1),
      community_code: params.community_code || null,
      series: [
        {
          period: '2025T1',
          supplies: url.endsWith('R2-002') ? 75 : 25,
          metadata_modified: marketRevision,
        },
        {
          period: '2025T4',
          supplies: url.endsWith('R2-002') ? 10 : 0,
          metadata_modified: marketRevision,
        },
      ],
    };
  throw new Error(`Unexpected market request ${url}`);
}
