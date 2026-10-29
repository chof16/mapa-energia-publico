// Dated editorial context keyed by API identity; never used to join or rename series.
const companyContext: Record<string, { summary: string; detail: string; source: string; publisher: string }> = {
  'gas-eni-plenitude': {
    summary: 'Plenitude · hogares y empresas',
    detail: 'Eni presenta Plenitude como comercializadora de luz y gas para hogares y empresas. Se distingue de Eni España Comercializadora de Gas.',
    source: 'https://www.eni.com/es-ES/operaciones/plenitude.html', publisher: 'Eni · Plenitude',
  },
  'gas-company-8b97b3e0f7b732176cf4': {
    summary: 'Eni España Comercializadora de Gas · industria, pymes y mayoristas',
    detail: 'Eni España Comercializadora de Gas suministra al sector industrial, pymes, sector eléctrico y mercado mayorista. Su serie permanece separada de Plenitude.',
    source: 'https://www.eni.com/es-ES/operaciones/eni-espana.html', publisher: 'Eni · Eni España',
  },
  'gas-cepsa-gas': {
    summary: 'Serie de la comercializadora de gas · no es el grupo completo',
    detail: 'Cepsa Gas / Moeve identifica aquí una serie estadística de comercializadora, no el conjunto del grupo. La web de Moeve identifica por separado a Cepsa Gas Comercializadora para el suministro de gas.',
    source: 'https://www.moeve.es/es/utilidades/catalogo/natural-gas', publisher: 'Moeve · Gas natural',
  },
  'gas-cepsa-commercial': {
    summary: 'Cepsa Comercial Petróleo · actualmente Moeve Commercial',
    detail: 'El BOE de 27/02/2026 identifica a Moeve Commercial, SAU como antes Cepsa Comercial Petróleo (A80298896). Esta serie histórica es distinta de Cepsa Gas.',
    source: 'https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-4522', publisher: 'BOE · denominación anterior y actual',
  },
};

export const gasCompanyDetail = (id: string) => companyContext[id]?.summary || '';

export function GasCompanyContext({ selected }: { selected: { code: string; title: string }[] }) {
  const explained = selected.filter(({ code }) => companyContext[code]);
  if (!explained.length) return null;
  return <details className="gas-company-context">
    <summary>Contexto actual de las empresas seleccionadas · <time dateTime="2026-10-29">29/10/2026</time></summary>
    <p>Contexto consultado en esa fecha: no describe los segmentos de clientes de toda la serie histórica ni establece nuevas continuidades. Un cambio de marca no demuestra una fusión legal.</p>
    {explained.map(({ code, title }) => <p key={code}><strong>{title}:</strong> {companyContext[code].detail} <a href={companyContext[code].source} target="_blank" rel="noopener noreferrer">{companyContext[code].publisher}</a>.</p>)}
  </details>;
}
