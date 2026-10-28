import { Navigate, type RouteObject } from 'react-router';
import { MapLayout } from './map/layouts/MapLayout';
import { HomePage } from './map/pages/home/HomePage';
import { EvolutionLayout } from './electricity/layouts/EvolutionLayout';
import { EvolutionScreen } from './electricity/pages/evolution/EvolutionScreen';
import { ReferenceLayout } from './electricity/layouts/ReferenceLayout';
import { ReferencePage } from './electricity/pages/reference/ReferencePage';
import { LegalLayout } from './legal/layouts/LegalLayout';
import { CookiesPage } from './legal/pages/CookiesPage';
import { TermsPage } from './legal/pages/TermsPage';
import { GasRedirect } from './components/routes/GasRedirect';
import { ElectricityRoute } from './components/routes/ElectricityRoute';

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
    element: <ElectricityRoute><EvolutionLayout /></ElectricityRoute>,
    children: [{ index: true, element: <EvolutionScreen /> }],
  },
  {
    path: '/regulated-tariff',
    element: <ElectricityRoute><ReferenceLayout /></ElectricityRoute>,
    children: [{ index: true, element: <ReferencePage /> }],
  },
  { path: '/gas', element: <GasRedirect /> },
  { path: '*', element: <Navigate to="/" replace /> },
];
