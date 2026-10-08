import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { InternalAxiosRequestConfig } from 'axios';
import { AxiosError } from 'axios';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { appRoutes } from '../../../app.router';
import { httpClient } from '../../../api/http-client';

const catalog = {
  sector: 'electricity', scope: 'reference_marketers', snapshot_date: '2026-10-04',
  designation_source_url: 'https://www.cnmc.es/cor',
  code_source_url: 'https://data.cnmc.es/market',
  code_source_period: '2025T4',
  code_source_metadata_modified: '2026-09-16T09:54:27.287603',
  attribution: 'Origen de los datos: Comisión Nacional de los Mercados y la Competencia',
  items: [
    { marketer_code: 'R2-292', name: 'Empresa de prueba', territorial_limit: null },
    { marketer_code: 'R2-532', name: 'Empresa de Melilla', territorial_limit: 'melilla' },
    { marketer_code: 'R2-530', name: 'Empresa de Ceuta', territorial_limit: 'ceuta' },
  ],
};
const originalAdapter = httpClient.defaults.adapter;
const network = vi.fn(async (config: InternalAxiosRequestConfig) => ({
  data: JSON.stringify(catalog), status: 200, statusText: 'OK', headers: {}, config,
}));
let client: QueryClient;

beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  network.mockReset();
  network.mockImplementation(async (config) => ({
    data: JSON.stringify(catalog), status: 200, statusText: 'OK', headers: {}, config,
  }));
  httpClient.defaults.adapter = network;
});
afterEach(() => { client.clear(); httpClient.defaults.adapter = originalAdapter; });

function renderReference(entry: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [entry] });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

describe('public reference marketer page', () => {
  it('explains CORs, shows only stated limits, sources, and links to clean map/evolution routes', async () => {
    renderReference('/regulated-tariff?sector=electricity&period=2024T1&province=28&campaign=shared');
    expect(await screen.findByRole('heading', { name: 'Comercializadoras de referencia' })).toBeInTheDocument();
    const list = await screen.findByRole('list');
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);
    expect(within(list).getByText('Solo Ceuta')).toBeInTheDocument();
    expect(within(list).getByText('Solo Melilla')).toBeInTheDocument();
    expect(within(list).getByText('Sin límite especial indicado por la CNMC')).toBeInTheDocument();
    expect(screen.getByText(/no vincula una empresa a una distribuidora concreta/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Lista de COR de la CNMC' })).toHaveAttribute('href', catalog.designation_source_url);
    expect(screen.getByRole('link', { name: 'CNMC Data' })).toHaveAttribute('href', catalog.code_source_url);
    expect(screen.getByText(/revisado el/)).toHaveTextContent('4 oct 2026');
    const navigation = screen.getByRole('navigation', { name: 'Navegación principal' });
    expect(within(navigation).getByRole('link', { name: 'Tarifa regulada' })).toHaveAttribute('aria-current', 'page');
    for (const [name, path] of [['Mapa', '/'], ['Evolución de comercializadoras', '/evolution']]) {
      const url = new URL(within(navigation).getByRole('link', { name }).getAttribute('href')!, 'http://localhost');
      expect(url.pathname).toBe(path);
      expect(url.searchParams.has('active_tab')).toBe(false);
      expect(url.search).toBe('');
    }
    expect(network).toHaveBeenCalledTimes(1);
    expect(network.mock.calls[0]?.[0]).toEqual(expect.objectContaining({
      params: { sector: 'electricity' },
    }));
  });

  it('keeps gas pending without querying electricity and returns through the sector control', async () => {
    const router = renderReference('/regulated-tariff?sector=gas&municipality=28079');
    expect(screen.getByRole('heading', { name: 'Gas pendiente' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Comercializadoras de referencia de gas' })).toBeInTheDocument();
    expect(screen.queryByText(/PVPC/)).not.toBeInTheDocument();
    expect(network).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Sector energético' })).getByRole('link', { name: 'Electricidad' }));
    await waitFor(() => expect(router.state.location.search).toContain('sector=electricity'));
    expect(router.state.location.pathname).toBe('/regulated-tariff');
    expect(router.state.location.search).toContain('municipality=28079');
    expect(await screen.findByRole('heading', { name: 'Catálogo verificado' })).toBeInTheDocument();
  });

  it('shows a clear pending state for an old API and retries a transient error', async () => {
    let attempts = 0;
    network.mockImplementation(async (config) => {
      attempts += 1;
      if (attempts === 1) throw new AxiosError('Not found', 'ERR_BAD_RESPONSE', config, undefined, {
        data: '', status: 404, statusText: 'Not found', headers: {}, config,
      });
      return { data: JSON.stringify(catalog), status: 200, statusText: 'OK', headers: {}, config };
    });
    renderReference('/regulated-tariff');
    expect(await screen.findByRole('heading', { name: 'Catálogo pendiente en esta API' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByRole('heading', { name: 'Catálogo verificado' })).toBeInTheDocument();
    expect(network).toHaveBeenCalledTimes(2);
  });
});
