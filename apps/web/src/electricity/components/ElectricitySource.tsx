import type { Source } from '../interfaces/electricity';
import { formatRevision } from '../lib/electricity-format';

export function ElectricitySource({
  source,
  revision,
}: {
  source: Source;
  revision?: string;
}) {
  return (
    <footer className="electricity-source">
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
