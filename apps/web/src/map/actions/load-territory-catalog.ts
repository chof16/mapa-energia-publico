import { httpClient } from '../../api/http-client';
import { createTerritoryCatalog } from '../lib/territories';
import { labelsUrl } from '../lib/map-style';

export async function loadTerritoryCatalog(signal: AbortSignal) {
  const { data: text } = await httpClient.get<string>(labelsUrl, {
    signal,
    responseType: 'text',
    // Check size before parsing; do not trust the declared content type.
    transformResponse: [(data: unknown) => data],
  });
  if (typeof text !== 'string') throw new Error('Catálogo no disponible');
  if (text.length > 8 * 1024 * 1024)
    throw new Error('Catálogo demasiado grande');
  const data: unknown = JSON.parse(text);
  return createTerritoryCatalog(data);
}
