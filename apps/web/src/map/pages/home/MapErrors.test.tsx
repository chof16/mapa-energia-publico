import { AxiosError } from 'axios';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { appRoutes } from '../../../app.router';
import { territoryLabels } from '../../../test/fixtures/territory-labels';
import { MapBoundary } from '../../../test/maplibre-boundary';
import { marketResponse, marketQuarters } from '../../../test/fixtures/market';
import { choosePublished, openMarketData, selectedTerritory, network, renderRoute, renderExplorer as renderHome } from '../../../test/exploration-route-fixture';

vi.mock('maplibre-gl', async () => {
  const { MapBoundary } = await import('../../../test/maplibre-boundary');
  return {
    Map: MapBoundary,
    NavigationControl: class {},
    AttributionControl: class {},
    addProtocol: vi.fn(),
  };
});

describe('map loading errors', () => {
  it('rejects unpublished periods and invalid codes without requesting their market values', async () => {
    const { router } = await renderHome('/?period=2025T3&marketer=R2-000');
    await screen.findByText(
      'Este trimestre no está publicado. Elige uno de la lista.',
    );
    expect(
      network.mock.calls.filter(
        ([config]) =>
          config.url?.includes('/communities/') ||
          config.url?.includes('/shares'),
      ),
    ).toHaveLength(0);
    expect(router.state.location.search).toBe('?period=2025T3&marketer=R2-000');
    choosePublished('Trimestre publicado', '2025T1');
    await screen.findByText('Código de comercializadora no válido.');
    expect(
      network.mock.calls.filter(([config]) =>
        config.url?.includes('/communities/'),
      ),
    ).toHaveLength(0);
  });

  it('recovers an older published quarter and prevents duplicate retries while a request is pending', async () => {
    let failed = true;
    let completeRetry: (() => void) | undefined;
    network.mockImplementation(async (config) => {
      if (config.url?.endsWith('/shares')) {
        if (failed)
          throw new AxiosError(
            'Unavailable',
            'ERR_BAD_RESPONSE',
            config,
            undefined,
            {
              data: {},
              status: 503,
              statusText: 'Unavailable',
              headers: {},
              config,
            },
          );
        await new Promise<void>((resolve) => {
          completeRetry = resolve;
        });
      }
      const response = config.url?.includes('/v1/market/')
        ? marketResponse(config.url, config.params)
        : territoryLabels;
      return {
        data: JSON.stringify(
          config.url?.endsWith('/quarters')
            ? {
                sector: 'electricity',
                quarters: [{ ...marketQuarters[0], period: '2011T4' }],
              }
            : response,
        ),
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      };
    });
    await renderHome('/?period=2011T4&marketer=R2-001');
    const retry = await screen.findByRole('button', { name: 'Reintentar' });
    const before = network.mock.calls.filter(([config]) =>
      config.url?.endsWith('/shares'),
    ).length;
    failed = false;
    fireEvent.click(retry);
    await waitFor(() => expect(retry).toBeDisabled());
    expect(retry).toHaveAttribute('aria-busy', 'true');
    expect(retry).toHaveTextContent('Reintentando…');
    fireEvent.click(retry);
    expect(
      network.mock.calls.filter(([config]) => config.url?.endsWith('/shares')),
    ).toHaveLength(before + 1);
    await act(async () => {
      completeRetry?.();
    });
    await openMarketData();
    await screen.findByRole('listbox', {
      name: 'Comercializadora · código R2',
    });
    expect(
      screen.getByRole('combobox', { name: 'Trimestre publicado' }),
    ).toHaveValue('4.º trimestre');
    expect(screen.getByRole('combobox', { name: 'Año publicado' })).toHaveValue(
      '2011',
    );
    expect(
      screen.queryByRole('button', { name: 'Reintentar' }),
    ).not.toBeInTheDocument();
  });

  it('offers a retry after unavailable market data and keeps a missing share endpoint pending', async () => {
    let unavailable = true;
    network.mockImplementation(async (config) => {
      const status =
        config.url?.includes('/communities/') && unavailable
          ? 503
          : config.url?.includes('/share-series/')
            ? 404
            : 200;
      if (status !== 200)
        throw new AxiosError(
          'Unavailable',
          'ERR_BAD_RESPONSE',
          config,
          undefined,
          { data: {}, status, statusText: 'Unavailable', headers: {}, config },
        );
      return {
        data: JSON.stringify(
          config.url?.includes('/v1/market/')
            ? marketResponse(config.url, config.params)
            : territoryLabels,
        ),
        status,
        statusText: 'OK',
        headers: {},
        config,
      };
    });
    await renderHome('/?period=2025T4&marketer=R2-001');
    await openMarketData('shares');
    await screen.findByRole('button', { name: 'Reintentar cuotas' });
    expect(
      screen.queryByRole('list', { name: 'Cuotas autonómicas · 2025T4' }),
    ).not.toBeInTheDocument();
    unavailable = false;
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar cuotas' }));
    await screen.findByRole('list', { name: 'Cuotas autonómicas · 2025T4' });
    fireEvent.click(
      screen.getByRole('link', { name: 'Evolución de comercializadoras' }),
    );
    await waitFor(() => expect(
      screen.getByRole('combobox', { name: 'Comercializadora · código R2' }),
    ).toBeEnabled());
    choosePublished('Comercializadora · código R2', 'R2-001');
    fireEvent.click(screen.getByRole('button', { name: 'Cuota' }));
    await screen.findByText(
      /La serie de cuotas está pendiente de activar en esta API/,
    );
    expect(
      screen.queryByRole('img', { name: /Evolución de cuota/ }),
    ).not.toBeInTheDocument();
  });

  it('rejects invalid catalog data before handing it to the map source', async () => {
    network.mockImplementation(async (config) => ({
      data: JSON.stringify({
        ...territoryLabels,
        features: [...territoryLabels.features, territoryLabels.features[0]],
      }),
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }));
    renderRoute(createMemoryRouter(appRoutes));
    await screen.findByText(
      'No se pudieron cargar las zonas. Recarga la página para volver a intentarlo.',
    );
    expect(
      screen.getByRole('combobox', { name: 'Comunidad autónoma' }),
    ).toBeDisabled();
    const mainMap = MapBoundary.instances.find(
      (map) => map.options.cooperativeGestures,
    );
    expect(mainMap?.setData).not.toHaveBeenCalled();
  });

  it('reuses the validated catalog when the route remounts', async () => {
    const first = await renderHome();
    const catalogCalls = () =>
      network.mock.calls.filter(([config]) =>
        config.url?.includes('etiquetas'),
      );
    expect(catalogCalls()).toHaveLength(1);
    first.unmount();
    const second = await renderHome('/?municipality=28005');
    expect(catalogCalls()).toHaveLength(1);
    expect(
      selectedTerritory('Alcalá de Henares'),
    ).toBeVisible();
    const maps = MapBoundary.instances.filter(
      (map) => map.options.cooperativeGestures,
    );
    expect(maps).toHaveLength(2);
    await waitFor(() => expect(maps[1].setData).toHaveBeenCalled());
    second.unmount();
  });
});
