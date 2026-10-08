// Accent-insensitive search over shared name/code options.
import type { SearchOption } from '../interfaces/search-option';

function normalizeSearch(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('es')
    .trim();
}

export function filterOptions<T extends SearchOption>(
  options: readonly T[],
  query: string,
): T[] {
  const words = normalizeSearch(query).split(/\s+/).filter(Boolean);
  return options.filter((territory) => {
    const text = normalizeSearch(`${territory.title} ${territory.code}`);
    return words.every((word) => text.includes(word));
  });
}
