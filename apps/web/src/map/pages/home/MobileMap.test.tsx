import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { appRoutes } from '../../../app.router';
import { mockProvinceResponse, renderRoute } from '../../../test/exploration-route-fixture';
import { MapBoundary } from '../../../test/maplibre-boundary';

vi.mock('maplibre-gl', async () => {
  const { MapBoundary } = await import('../../../test/maplibre-boundary');
  return { Map: MapBoundary, NavigationControl: class {}, AttributionControl: class {}, addProtocol: vi.fn() };
});

function viewport(width: number, height: number) {
  vi.stubGlobal('innerWidth', width);
  vi.stubGlobal('innerHeight', height);
  act(() => window.dispatchEvent(new Event('resize')));
}

describe('compact map workspace', () => {
  it.each([
    { entry: '/?sector=gas&province=28', label: 'Presencia provincial de gas', company: 'Red sintética A SA' },
    { entry: '/?province=28', label: 'Evidencia de distribuidoras en Madrid', company: 'Distribuidora de prueba' },
  ])('keeps the $label panel out of the map until requested', async ({ entry, label, company }) => {
    viewport(390, 844);
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
    if (!entry.includes('sector=gas')) mockProvinceResponse();
    const router = createMemoryRouter(appRoutes, { initialEntries: [entry] });
    renderRoute(router);
    const panel = await screen.findByRole('complementary', { name: label });
    const result = await within(panel).findByText(company);
    expect(result).not.toBeVisible();
    const details = within(panel).getByRole('button', { name: /Distribuidoras Madrid · 28 Ver detalles/ });
    expect(details).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByRole('button', { name: /^Filtros/ })).toHaveAttribute('aria-expanded', 'false');
    expect(MapBoundary.instances.find((map) => map.options.interactive !== false)?.options.cooperativeGestures).toBe(false);

    fireEvent.click(details);
    expect(result).toBeVisible();
    fireEvent.keyDown(details, { key: 'Escape' });
    expect(result).not.toBeVisible();
    expect(details).toHaveFocus();

    const legend = screen.getByRole('button', { name: 'Leyenda' });
    expect(legend).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(legend);
    const legendContent = document.getElementById(legend.getAttribute('aria-controls')!)!;
    expect(legendContent).toBeVisible();
    fireEvent.keyDown(legend, { key: 'Escape' });
    expect(legendContent).not.toBeVisible();
    expect(legend).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: /^Filtros/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Ver mapa' }));
    expect(screen.getByRole('button', { name: /^Filtros/ })).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(screen.getByRole('button', { name: 'Explorar Canarias en el mapa principal' }));
    expect(new URLSearchParams(router.state.location.search).get('view')).toBe('canary_islands');
    expect(MapBoundary.instances).toHaveLength(2);
  });

  it('collapses overlays on rotation and selection changes without recreating the maps', async () => {
    viewport(1440, 900);
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/?sector=gas&province=28'] });
    renderRoute(router);
    expect(await screen.findByText('Red sintética A SA')).toBeVisible();
    viewport(390, 844);
    expect(screen.getByText('Red sintética A SA')).not.toBeVisible();
    expect(screen.getByRole('button', { name: /^Filtros/ })).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(screen.getByRole('button', { name: /Distribuidoras Madrid · 28 Ver detalles/ }));
    expect(screen.getByText('Red sintética A SA')).toBeVisible();
    await act(() => router.navigate('/?sector=gas&province=46'));
    await waitFor(() => expect(screen.getByRole('button', { name: /Distribuidoras.*Ver detalles/ })).toHaveAttribute('aria-expanded', 'false'));
    viewport(1440, 900);
    expect(screen.queryByRole('button', { name: /Distribuidoras.*Ver detalles/ })).not.toBeInTheDocument();
    expect(MapBoundary.instances).toHaveLength(2);
  });
});
