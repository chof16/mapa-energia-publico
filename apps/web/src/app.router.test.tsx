import { act, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { appRoutes } from './app.router';
import { renderExplorer, renderRoute } from './test/exploration-route-fixture';

vi.mock('maplibre-gl', async () => {
  const { MapBoundary } = await import('./test/maplibre-boundary');
  return {
    Map: MapBoundary,
    NavigationControl: class {},
    AttributionControl: class {},
    addProtocol: vi.fn(),
  };
});

describe('route fallback', () => {
  it.each(['/missing', '/nested/missing?province=28#details', '/missing.txt'])(
    'redirects %s to the unfiltered home page', async (entry) => {
      const { router } = await renderExplorer(entry);
      expect(screen.getByRole('heading', { name: 'Explorar zonas eléctricas' })).toBeVisible();
      expect(router.state.location).toMatchObject({ pathname: '/', search: '', hash: '' });
      expect(router.state.historyAction).toBe('REPLACE');
    },
  );

  it('replaces an unknown history entry so Back returns to the previous page', async () => {
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/cookies'] });
    renderRoute(router);
    await act(async () => { await router.navigate('/missing'); });
    await waitFor(() => expect(router.state.location.pathname).toBe('/'));
    await act(async () => { await router.navigate(-1); });
    expect(router.state.location.pathname).toBe('/cookies');
  });

});
