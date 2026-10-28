import type { ReactNode } from 'react';
import { useSearchParams } from 'react-router';
import { GasRedirect } from './GasRedirect';

export function ElectricityRoute({ children }: { children: ReactNode }) {
  const [params] = useSearchParams();
  return params.get('sector') === 'gas' ? <GasRedirect /> : children;
}
