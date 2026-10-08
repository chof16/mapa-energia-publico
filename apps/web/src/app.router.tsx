import type { RouteObject } from 'react-router';
import { MapLayout } from './map/layouts/MapLayout';
import { HomePage } from './map/pages/home/HomePage';
import { EvolutionLayout } from './market/layouts/EvolutionLayout';
import { EvolutionScreen } from './market/pages/evolution/EvolutionScreen';
import { ReferenceLayout } from './market/layouts/ReferenceLayout';
import { ReferencePage } from './market/pages/reference/ReferencePage';
import { LegalLayout } from './legal/layouts/LegalLayout';
import { CookiesPage } from './legal/pages/CookiesPage';
import { TermsPage } from './legal/pages/TermsPage';

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
    children: [{ index: true, element: <EvolutionScreen /> }],
  },
  {
    path: '/regulated-tariff',
    element: <ReferenceLayout />,
    children: [{ index: true, element: <ReferencePage /> }],
  },
];
