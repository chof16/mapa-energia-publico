import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, beforeEach, expect, vi } from 'vitest';
import { httpClient } from '../api/http-client';
import { appRoutes } from '../app.router';
import { territoryLabels } from './fixtures/territory-labels';
import { MapBoundary } from './maplibre-boundary';
import { marketResponse } from './fixtures/market';

export function choosePublished(label: string, value: string) {
  const input = screen.getByRole('combobox', { name: label });
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value } });
  fireEvent.keyDown(input, { key: 'Enter' });
}

export async function openMarketData(section: 'supplies' | 'shares' = 'supplies') {
  if (section === 'supplies') {
    const input = screen.getByRole('combobox', { name: 'Comercializadora · código R2' });
    await waitFor(() => expect(input).toBeEnabled());
    fireEvent.focus(input);
  } else {
    const trigger = screen.getByRole('button', { name: 'Cuotas y fuente' });
    if (trigger.getAttribute('aria-expanded') !== 'true') fireEvent.click(trigger);
  }
}

export function selectedTerritory(name: string) {
  return within(screen.getByRole('group', { name: 'Seleccionar territorio' }))
    .getByText(new RegExp(`^${name} ·`));
}

const originalAdapter = httpClient.defaults.adapter;
export const network = vi.fn(async (config: InternalAxiosRequestConfig) => ({
  data: JSON.stringify(territoryLabels),
  status: 200,
  statusText: 'OK',
  headers: {},
  config,
}));
let queryClient: QueryClient;

export const provinceResponse = {
  sector: 'electricity', province_code: '28', snapshot_date: '2026-10-03',
  scope: 'provincial_presence', complete: false,
  items: [{
    distributor_code: 'R1-001', distributor_name: 'Distribuidora de prueba',
    registry_source_url: 'https://www.boe.es/registro', cor: null,
    corporate_group: {
      group_name: 'Grupo Iberdrola',
      evidence: {
        source_title: 'Estructura de Iberdrola', source_url: 'https://www.iberdrola.com/gobierno-corporativo/estructura',
        published_on: null, checked_on: '2026-10-03',
        relationship_claim: 'Iberdrola identifica a esta distribuidora como filial.',
      },
    },
    evidence: {
      source_title: 'Fuente geográfica de prueba', source_url: 'https://www.boe.es/zona',
      published_on: '2026-01-29', checked_on: '2026-10-03',
      geographic_claim: 'Presencia en una parte de Madrid.',
      confidence: 'official_document',
    },
  }],
};

export const provinceSummaryResponse = {
  sector: 'electricity', snapshot_date: '2026-10-04',
  scope: 'documented_provincial_presence', complete: false,
  items: [
    { province_code: '24', documented_distributor_count: 3 },
    { province_code: '28', documented_distributor_count: 2 },
    { province_code: '46', documented_distributor_count: 1 },
  ],
};

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  network.mockReset();
  network.mockImplementation(async (config) => ({
    data: JSON.stringify(
      config.url?.endsWith('/v1/distribution/provinces')
        ? provinceSummaryResponse
        : config.url?.includes('/v1/market/')
          ? marketResponse(config.url, config.params)
          : territoryLabels,
    ),
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  }));
  httpClient.defaults.adapter = network;
  MapBoundary.instances = [];
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    disconnect() {}
  });
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(900);
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(600);
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: vi.fn(),
  });
});

afterEach(() => {
  queryClient.clear();
  httpClient.defaults.adapter = originalAdapter;
});

export function renderRoute(router: ReturnType<typeof createMemoryRouter>) {
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

export async function renderExplorer(entry = '/') {
  const router = createMemoryRouter(appRoutes, { initialEntries: [entry] });
  const result = renderRoute(router);
  await waitFor(() =>
    expect(screen.getByRole('combobox', {
      name: entry.startsWith('/evolution') ? 'Ámbito territorial' : 'Comunidad autónoma',
    })).toBeEnabled(),
  );
  return { ...result, router };
}

export function mockProvinceResponse(value: unknown = provinceResponse) {
  network.mockImplementation(async (config) => ({
    data: JSON.stringify(config.url?.endsWith('/v1/distribution/provinces')
      ? provinceSummaryResponse
      : config.url?.includes('/v1/distribution/')
        ? value
        : config.url?.includes('/v1/market/')
          ? marketResponse(config.url, config.params)
          : territoryLabels),
    status: 200, statusText: 'OK', headers: {}, config,
  }));
}
