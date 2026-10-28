import { useSyncExternalStore } from 'react';

function subscribe(onChange: () => void) {
  window.addEventListener('resize', onChange);
  return () => window.removeEventListener('resize', onChange);
}

export function useCompactMap(maxWidth = 700) {
  return useSyncExternalStore(subscribe,
    () => window.innerWidth <= maxWidth || window.innerHeight <= 600,
    () => false);
}
