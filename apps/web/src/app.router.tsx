import { Navigate, useSearchParams, type RouteObject } from 'react-router';
import { MapLayout } from './map/layouts/MapLayout';
import { HomePage } from './map/pages/home/HomePage';
import { EvolutionLayout } from './components/layouts/EvolutionLayout';
import { EvolutionScreen } from './electricity/pages/evolution/EvolutionScreen';
import { ReferenceLayout } from './components/layouts/ReferenceLayout';
import { ReferencePage } from './electricity/pages/reference/ReferencePage';
import { LegalLayout } from './legal/layouts/LegalLayout';
import { CookiesPage } from './legal/pages/CookiesPage';
import { TermsPage } from './legal/pages/TermsPage';
import { GasRedirect } from './components/routes/GasRedirect';
import { GasEvolutionPage } from './gas/pages/evolution/GasEvolutionPage';
import { GasReferencePage } from './gas/pages/reference/GasReferencePage';

function SectorPage({ reference = false }: { reference?: boolean }) {
  const [params] = useSearchParams();
  if (params.get('sector') === 'gas') return reference ? <GasReferencePage /> : <GasEvolutionPage />;
  return reference ? <ReferencePage /> : <EvolutionScreen />;
}

export const appRoutes: RouteObject[] = [
  {
    element: <LegalLayout />,
    children: [
      { path: '/cookies', element: <CookiesPage /> },
      { path: '/terms', element: <TermsPage /> },
    ],
  },
  {
    path: '/',
    element: <MapLayout />,
    children: [{ index: true, element: <HomePage /> }],
  },
  {
    path: '/evolution',
    element: <EvolutionLayout />,
    children: [{ index: true, element: <SectorPage /> }],
  },
  {
    path: '/regulated-tariff',
    element: <ReferenceLayout />,
    children: [{ index: true, element: <SectorPage reference /> }],
  },
  { path: '/gas', element: <GasRedirect /> },
  { path: '*', element: <Navigate to="/" replace /> },
];
