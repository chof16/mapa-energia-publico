import { fireEvent, screen, within } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { appRoutes } from '../../app.router';
import { PROJECT_REPOSITORY } from '../../lib/project-links';
import { network, renderRoute } from '../../test/exploration-route-fixture';
import { MapBoundary } from '../../test/maplibre-boundary';

vi.mock('maplibre-gl', async () => {
  const { MapBoundary } = await import('../../test/maplibre-boundary');
  return {
    Map: MapBoundary,
    NavigationControl: class {},
    AttributionControl: class {},
    addProtocol: vi.fn(),
  };
});

describe('project information and footer', () => {
  it.each(['/?sector=gas', '/evolution?sector=gas', '/regulated-tariff?sector=gas'])(
    'offers legal links and independence notice on %s', (entry) => {
      renderRoute(createMemoryRouter(appRoutes, { initialEntries: [entry] }));
      const footer = within(screen.getByRole('contentinfo'));
      expect(footer.getByText(/sin afiliación con la CNMC, distribuidoras ni comercializadoras/)).toBeVisible();
      expect(footer.getByRole('link', { name: 'Cookies' })).toHaveAttribute('href', '/cookies');
      expect(footer.getByRole('link', { name: 'Términos y condiciones' })).toHaveAttribute('href', '/terms');
      expect(footer.getByRole('link', { name: 'GitHub' })).toHaveAttribute('href', PROJECT_REPOSITORY);
    },
  );

  it.each([
    ['/cookies', 'Cookies y almacenamiento'],
    ['/terms', 'Términos y condiciones'],
  ])('opens %s directly without querying data or mounting maps', (entry, title) => {
    renderRoute(createMemoryRouter(appRoutes, { initialEntries: [entry] }));
    expect(screen.getByRole('heading', { level: 1, name: title })).toBeVisible();
    expect(screen.getByRole('main')).toHaveFocus();
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Back to map' })).toHaveAttribute('href', '/');
    expect(network).not.toHaveBeenCalled();
    expect(MapBoundary.instances).toHaveLength(0);
  });

  it('navigates between policies and preserves source and repository attribution', () => {
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/cookies'] });
    renderRoute(router);
    expect(screen.getByText(/La aplicación no instala cookies/)).toBeVisible();
    expect(screen.getByText(/Google Fonts y las etiquetas del mapa/)).toBeVisible();
    fireEvent.click(within(screen.getByRole('contentinfo')).getByRole('link', { name: 'Términos y condiciones' }));
    expect(router.state.location.pathname).toBe('/terms');
    expect(screen.getByRole('heading', { name: 'Independencia' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'condiciones de CNMC Data' })).toHaveAttribute('href', 'https://data.cnmc.es/condiciones-de-uso');
    expect(screen.getByRole('link', { name: 'repositorio de GitHub' })).toHaveAttribute('href', PROJECT_REPOSITORY);
    expect(screen.getByRole('main')).toHaveFocus();
  });
});
