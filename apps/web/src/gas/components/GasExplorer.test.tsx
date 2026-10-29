import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { appRoutes } from '../../app.router';
import { choosePublished, network, renderRoute } from '../../test/exploration-route-fixture';
import { MapBoundary } from '../../test/maplibre-boundary';

vi.mock('maplibre-gl', async () => {
  const { MapBoundary } = await import('../../test/maplibre-boundary');
  return { Map: MapBoundary, NavigationControl: class {}, AttributionControl: class {}, addProtocol: vi.fn() };
});

function open(entry = '/?sector=gas') {
  const router = createMemoryRouter(appRoutes, { initialEntries: [entry] });
  renderRoute(router);
  return router;
}

describe('gas distributor map', () => {
  it('keeps shared geography and map controls without retailer or period controls on the map', async () => {
    open('/?sector=gas&province=28');
    expect(await screen.findByText('Red sintética A SA')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Madrid · 28' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Explorar Canarias en el mapa principal' })).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Provincia' })).toBeEnabled();
    expect(screen.queryByRole('combobox', { name: /Comercializadora|publicado/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cuota comercializadora' })).not.toBeInTheDocument();
    expect(screen.queryByRole('group', { name: 'Línea temporal del mapa' })).not.toBeInTheDocument();
    const navigation = screen.getByRole('navigation', { name: 'Navegación principal' });
    expect(within(navigation).getAllByRole('link')).toHaveLength(3);
    expect(within(navigation).getByRole('link', { name: 'Evolución' })).toHaveAttribute('href', '/evolution?sector=gas');
    expect(within(navigation).getByRole('link', { name: 'Tarifa regulada' })).toHaveAttribute('href', '/regulated-tariff?sector=gas');
    expect(within(navigation).getByRole('link', { name: 'Mapa' })).toHaveAttribute('href', '/?sector=gas');
    expect(network.mock.calls.filter(([config]) => config.url?.startsWith('/v1/')).every(([config]) => config.url?.startsWith('/v1/gas/distribution/'))).toBe(true);
    expect(MapBoundary.instances).toHaveLength(2);
  });

  it.each(['/gas?view=regulated'])('redirects gas alias %s to the map with replacement', async (entry) => {
    const router = open(entry + '&province=28&dataset=ds_1937_1&period=2020&map_layer=market&observed_name=Old');
    expect(await screen.findByText('Red sintética A SA')).toBeVisible();
    expect(router.state.location.pathname).toBe('/');
    const params = new URLSearchParams(router.state.location.search);
    expect([...params.keys()].sort()).toEqual(['province', 'sector']);
    expect(params.get('province')).toBe('28');
    expect(router.state.historyAction).toBe('REPLACE');
    expect(network.mock.calls.filter(([config]) => config.url?.startsWith('/v1/')).every(([config]) => config.url?.startsWith('/v1/gas/distribution/'))).toBe(true);
  });

  it('cleans retired filters on shared map links while preserving leading zeros and unrelated link context', async () => {
    const router = open('/?sector=gas&province=01&dataset=ds_1947_1&metric=clients&map_layer=market&role=marketer&snapshot_id=old&campaign=shared');
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).has('dataset')).toBe(false));
    expect(router.state.location.search).toBe('?sector=gas&province=01&campaign=shared');
    expect(screen.getByRole('complementary', { name: 'Presencia provincial de gas' })).toBeVisible();
    expect(network.mock.calls.some(([config]) => /\/gas\/(shares|companies|periods|observations|regulated-suppliers)/.test(config.url || ''))).toBe(false);
  });

  it('keeps territory, Canarias and browser history working without statistical filters', async () => {
    const router = open();
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Comunidad autónoma' })).toBeEnabled());
    choosePublished('Comunidad autónoma', 'Madrid');
    choosePublished('Provincia', 'Madrid');
    expect(await screen.findByText('Red sintética A SA')).toBeVisible();
    const before = router.state.location.search;
    fireEvent.click(screen.getByRole('button', { name: 'Explorar Canarias en el mapa principal' }));
    expect(new URLSearchParams(router.state.location.search).get('view')).toBe('canary_islands');
    expect(new URLSearchParams(router.state.location.search).has('province')).toBe(false);
    await act(() => router.navigate(-1));
    expect(router.state.location.search).toBe(before);
    expect(screen.getByRole('heading', { name: 'Madrid · 28' })).toBeVisible();
  });

  it('switches sectors on evolution without carrying filters and restores electricity filters on back', async () => {
    const router = open('/evolution?marketer=R2-001&period=2025T4');
    fireEvent.click(screen.getByRole('link', { name: 'Gas' }));
    expect(router.state.location.pathname).toBe('/evolution');
    expect(router.state.location.search).toBe('?sector=gas');
    expect(screen.getByRole('group', { name: 'Métrica de gas' })).toBeVisible();
    fireEvent.click(screen.getByRole('link', { name: 'Electricidad' }));
    expect(router.state.location.search).toBe('');
    expect(screen.getByRole('link', { name: 'Evolución' })).toHaveAttribute('href', '/evolution');
    expect(screen.queryByRole('group', { name: 'Métrica de gas' })).not.toBeInTheDocument();
    await act(() => router.navigate(-2));
    expect(router.state.location.pathname).toBe('/evolution');
    expect(new URLSearchParams(router.state.location.search).get('marketer')).toBe('R2-001');
  });
});
