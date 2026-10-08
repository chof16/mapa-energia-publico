import type { Source } from '../interfaces/market';
import { formatRevision } from '../lib/market-format';

export function MarketSource({
  source,
  revision,
}: {
  source: Source;
  revision?: string;
}) {
  return (
    <footer className="market-source">
      <p>{source.attribution}</p>
      {revision && (
        <p>
          Revisión del origen:{' '}
          <time dateTime={revision} title={revision}>
            {formatRevision(revision)}
          </time>
        </p>
      )}
      <a href={source.source_url} target="_blank" rel="noreferrer">
        Fuente CNMC Data
      </a>
      {' · '}
      <a href={source.license_url} target="_blank" rel="noreferrer">
        {source.license_id}
      </a>
      {' · '}
      <a href={source.conditions_url} target="_blank" rel="noreferrer">
        Condiciones de reutilización
      </a>
    </footer>
  );
}
