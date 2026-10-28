import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { appRoutes } from '../../app.router';
import { network, renderRoute } from '../../test/exploration-route-fixture';
import { gasDistributionResponse, gasNetworkSource } from '../../test/fixtures/gas-distribution';
import { MapBoundary } from '../../test/maplibre-boundary';

vi.mock('maplibre-gl', async () => {
  const { MapBoundary } = await import('../../test/maplibre-boundary');
  return { Map: MapBoundary, NavigationControl: class {}, AttributionControl: class {}, addProtocol: vi.fn() };
});

function openMap(entry = '/?sector=gas&province=28') {
  const router = createMemoryRouter(appRoutes, { initialEntries: [entry] });
  renderRoute(router);
  return router;
}

describe('historical gas presence map', () => {
  it('paints provincial evidence, pins detail to its revision and shows observed names and zero', async () => {
    const router = openMap();
    const panel = screen.getByRole('complementary', { name: 'Presencia provincial de gas' });
    expect(await within(panel).findByText('Red sintética A SA')).toBeVisible();
    expect(panel).toHaveTextContent('0 puntos de suministro');
    expect(panel).toHaveTextContent('junio de 2019');
    expect(panel).toHaveTextContent('sin exclusividad');
    expect(within(panel).getByRole('link', { name: 'Consultar anexo municipal' })).toHaveAttribute('href', gasNetworkSource.download_url);
    expect(network).toHaveBeenCalledWith(expect.objectContaining({ url: '/v1/gas/distribution/provinces/28', params: { limit: 100, offset: 0, load_id: gasNetworkSource.load_id } }));
    const map = MapBoundary.instances.find((map) => map.options.cooperativeGestures)!;
    expect(map.setLayoutProperty).toHaveBeenCalledWith('distribution-fill', 'visibility', 'visible');
    expect(map.layers.get('distribution-fill')).toMatchObject({ 'source-layer': 'provincias', maxzoom: 8.2 });
    expect(map.setPaintProperty).toHaveBeenCalledWith('distribution-fill', 'fill-color', [
      'case', ['boolean', ['feature-state', 'selected'], false], '#b9d5ef',
      ['match', ['get', 'cpro'], '28', '#4c9276', '46', '#a7d6c4', '#e5ebef'],
    ]);
    await act(() => router.navigate('/?sector=gas&province=28&municipality=28079'));
    expect(panel).toHaveTextContent('no acredita cobertura en este municipio');
    expect(network.mock.calls.filter(([config]) => config.url?.endsWith('/distribution/provinces/28'))).toHaveLength(1);
    expect(network.mock.calls.some(([config]) => config.url?.startsWith('/v1/distribution/') || config.url?.startsWith('/v1/electricity/'))).toBe(false);
  });

  it('treats absent evidence as unknown and keeps the Canaries inset', async () => {
    const original = network.getMockImplementation()!;
    network.mockImplementation(async (config) => {
      if (config.url?.endsWith('/distribution/provinces/28')) return { data: JSON.stringify({ ...gasDistributionResponse(config.url), total: 0, items: [] }), status: 200, statusText: 'OK', headers: {}, config };
      return original(config);
    });
    openMap();
    expect(await screen.findByText(/cobertura desconocida/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Explorar Canarias en el mapa principal' })).toBeVisible();
  });

  it('hides colors on invalid evidence and recovers through retry', async () => {
    const original = network.getMockImplementation()!;
    let invalid = true;
    network.mockImplementation(async (config) => {
      if (config.url?.endsWith('/distribution/provinces') && invalid) return { data: JSON.stringify({ ...gasDistributionResponse(config.url), complete: true }), status: 200, statusText: 'OK', headers: {}, config };
      return original(config);
    });
    openMap('/gas');
    const retry = await screen.findByRole('button', { name: 'Reintentar mapa de gas' });
    const map = MapBoundary.instances.find((map) => map.options.cooperativeGestures)!;
    expect(map.setLayoutProperty.mock.calls.filter(([id]) => id === 'distribution-fill').at(-1)).toEqual(['distribution-fill', 'visibility', 'none']);
    invalid = false;
    fireEvent.click(retry);
    await waitFor(() => expect(map.setLayoutProperty).toHaveBeenCalledWith('distribution-fill', 'visibility', 'visible'));
  });
});
