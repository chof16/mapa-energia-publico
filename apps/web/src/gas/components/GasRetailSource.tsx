import type { GasSource } from '../interfaces/retail';

export function GasRetailSource({ source, pages = [] }: { source: GasSource; pages?: number[] }) {
  return <div className="gas-source">
    <a href={`${source.url}${source.media_type === 'pdf' && pages[0] ? `#page=${pages[0]}` : ''}`} target="_blank" rel="noopener noreferrer">{source.title}</a>
    <span> · {source.publisher}{pages.length ? ` · pág. ${pages.join(', ')}` : ''}</span>
    <p>{source.published_on ? <>Publicación: <time dateTime={source.published_on}>{source.published_on}</time>. </> : 'Sin fecha de publicación declarada. '}
      Consulta: <time dateTime={source.retrieved_on}>{source.retrieved_on}</time>.</p>
    {source.notes && <p>{source.notes}</p>}
    <details><summary>Identificación de la fuente</summary><p>SHA-256: <code>{source.sha256}</code></p><p>Reutilización pendiente de revisión independiente.</p></details>
  </div>;
}
