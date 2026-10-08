import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
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

describe('map home route', () => {
  it('renders the public layout and loaded map', async () => {
    const { router } = await renderHome();
    expect(
      screen.getByRole('heading', {
        name: 'Explorar zonas eléctricas',
      }),
    ).toBeVisible();
    expect(
      screen.getByRole('group', { name: 'Seleccionar territorio' }),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByRole('combobox', { name: 'Trimestre publicado' }),
      ).toHaveValue('4.º trimestre'),
    );
    expect(screen.getByRole('combobox', { name: 'Provincia' })).toBeDisabled();
    expect(
      screen.getByRole('button', {
        name: 'Explorar Canarias en el mapa principal',
      }),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: 'IGN' })).toHaveAttribute(
      'href',
      'https://www.ign.es/',
    );
    expect(router.state.location.pathname).toBe('/');
    expect(router.state.location.search).toBe('');
    expect(router.state.historyAction).toBe('POP');
    expect(network).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/data/administrativo.etiquetas.geojson',
        signal: expect.any(AbortSignal),
        responseType: 'text',
      }),
    );
    expect(MapBoundary.instances).toHaveLength(2);
    const mainMap = MapBoundary.instances.find(
      (map) => map.options.cooperativeGestures,
    );
    expect(mainMap?.layers.has('municipios-label')).toBe(true);
    expect(mainMap?.setData).toHaveBeenCalledWith(
      expect.objectContaining({ features: expect.any(Array) }),
    );
  });

  it('restores partial links, searches within parents and starts other routes without map filters', async () => {
    const { router } = await renderHome(
      '/?municipality=28079&year=2020&campaign=shared',
    );
    expect(selectedTerritory('Madrid')).toBeVisible();
    expect(
      screen.getByRole('combobox', { name: 'Comunidad autónoma' }),
    ).toHaveValue('Comunidad de Madrid · 13');
    expect(screen.getByRole('combobox', { name: 'Provincia' })).toHaveValue(
      'Madrid · 28',
    );
    expect(router.state.location.search).toBe(
      '?municipality=28079&year=2020&campaign=shared',
    );
    expect(router.state.historyAction).toBe('POP');
    const municipality = screen.getByRole('combobox', { name: 'Municipio' });
    fireEvent.focus(municipality);
    fireEvent.change(municipality, { target: { value: 'alcala' } });
    const options = screen.getByRole('listbox', { name: 'Municipio' });
    expect(within(options).getAllByRole('option')).toHaveLength(1);
    fireEvent.keyDown(municipality, { key: 'Enter' });
    await waitFor(() => expect(selectedTerritory('Alcalá de Henares')).toBeVisible());
    expect(
      new URLSearchParams(router.state.location.search).get('municipality'),
    ).toBe('28005');
    expect(
      new URLSearchParams(router.state.location.search).get(
        'autonomous_community',
      ),
    ).toBe('13');
    expect(
      new URLSearchParams(router.state.location.search).get('province'),
    ).toBe('28');
    expect(
      new URLSearchParams(router.state.location.search).get('campaign'),
    ).toBe('shared');
    await act(() => router.navigate(-1));
    expect(selectedTerritory('Madrid')).toBeVisible();
    expect(router.state.location.search).toBe(
      '?municipality=28079&year=2020&campaign=shared',
    );
    await act(() => router.navigate(1));
    expect(
      selectedTerritory('Alcalá de Henares'),
    ).toBeVisible();
    choosePublished('Trimestre publicado', '2025T1');
    fireEvent.click(
      screen.getByRole('link', { name: 'Evolución de comercializadoras' }),
    );
    expect(screen.getByRole('group', { name: 'Dato de evolución' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Suministros · España' })).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/evolution');
    expect(router.state.location.search).toBe('');
    fireEvent.click(screen.getByRole('link', { name: 'Gas Próximamente' }));
    expect(
      screen.getByRole('combobox', { name: 'Comercializadora · código R2' }),
    ).toBeDisabled();
    expect(
      new URLSearchParams(router.state.location.search).get('sector'),
    ).toBe('gas');
    await act(() => router.navigate(-1));
    expect(
      screen.queryByRole('combobox', { name: 'Trimestre publicado' }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'Mapa' }));
    expect(router.state.location.pathname).toBe('/');
    expect(router.state.location.search).toBe('');
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Explorar Canarias en el mapa principal',
      }),
    );
    expect(new URLSearchParams(router.state.location.search).get('view')).toBe(
      'canary_islands',
    );
    expect(
      new URLSearchParams(router.state.location.search).has('municipality'),
    ).toBe(false);
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Ver Península, Baleares, Ceuta y Melilla',
      }),
    );
    expect(new URLSearchParams(router.state.location.search).has('view')).toBe(
      false,
    );
  });

  it('derives a valid selection and defaults from inconsistent parameters without rewriting the link', async () => {
    const entry =
      '/?autonomous_community=13&province=35&municipality=35016&year=invalid&sector=unknown&active_tab=unknown';
    const { router } = await renderHome(entry);
    expect(
      selectedTerritory('Comunidad de Madrid'),
    ).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Provincia' })).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Municipio' })).toBeDisabled();
    await waitFor(() =>
      expect(
        screen.getByRole('combobox', { name: 'Trimestre publicado' }),
      ).toHaveValue('4.º trimestre'),
    );
    expect(screen.getByRole('link', { name: 'Electricidad' })).toHaveAttribute(
      'aria-current',
      'true',
    );
    expect(
      screen.getByRole('heading', {
        name: 'Explorar zonas eléctricas',
      }),
    ).toBeVisible();
    expect(router.state.location.search).toBe(entry.slice(1));
    expect(router.state.historyAction).toBe('POP');
  });

  it('starts mobile with compact filters and retains territory when closing them', async () => {
    vi.stubGlobal('innerWidth', 390);
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ['/?autonomous_community=05'],
    });
    renderRoute(router);
    const filters = screen.getByRole('button', { name: /^Filtros/ });
    expect(filters).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(filters);
    expect(screen.getByRole('button', { name: /^Cerrar filtros/ }))
      .toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('complementary', { name: 'Evidencia de distribuidoras' })).toBeVisible();
    expect(
      await screen.findByRole('combobox', { name: 'Comunidad autónoma' }),
    ).toHaveValue('Canarias · 05');
    fireEvent.click(screen.getByRole('button', { name: 'Ver mapa' }));
    expect(filters).toHaveAttribute('aria-expanded', 'false');
    expect(filters).toHaveFocus();
    expect(router.state.location.search).toBe('?autonomous_community=05');
    fireEvent.click(filters);
    expect(screen.getByRole('combobox', { name: 'Comunidad autónoma' })).toHaveValue('Canarias · 05');
  });

  it('synchronizes map clicks and parent changes without a sidebar', async () => {
    const { router } = await renderHome();
    const mainMap = MapBoundary.instances.find(
      (map) => map.options.cooperativeGestures,
    );
    expect(mainMap).toBeDefined();
    mainMap!.features = [
      {
        layer: { 'source-layer': 'municipios' },
        properties: { ine_municipio: '28079' },
      },
    ];
    act(() => mainMap!.handlers.get('click')?.({ point: { x: 100, y: 100 } }));
    expect(selectedTerritory('Madrid')).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Municipio' })).toHaveValue(
      'Madrid · 28079',
    );
    expect(screen.getByRole('complementary', { name: 'Evidencia de distribuidoras en Madrid' })).toHaveTextContent('no prueba cobertura en ese municipio');
    expect(selectedTerritory('Madrid')).toBeVisible();
    const community = screen.getByRole('combobox', {
      name: 'Comunidad autónoma',
    });
    fireEvent.focus(community);
    fireEvent.change(community, { target: { value: '05' } });
    fireEvent.keyDown(community, { key: 'Enter' });
    expect(selectedTerritory('Canarias')).toBeVisible();
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get('autonomous_community')).toBe('05');
    expect(params.has('province')).toBe(false);
    expect(params.has('municipality')).toBe(false);
    expect(screen.getByRole('combobox', { name: 'Municipio' })).toBeDisabled();
    const province = screen.getByRole('combobox', { name: 'Provincia' });
    fireEvent.focus(province);
    expect(
      within(screen.getByRole('listbox', { name: 'Provincia' })).getAllByRole(
        'option',
      ),
    ).toHaveLength(1);
    expect(
      screen.getByRole('option', { name: /Las Palmas\s*35/ }),
    ).toBeVisible();
  });

  it('uses current query parameters and selection in the existing map click listener', async () => {
    const { router } = await renderHome(
      '/?municipality=28079&year=2020&campaign=shared',
    );
    let mainMap = MapBoundary.instances.find(
      (map) => map.options.cooperativeGestures,
    );
    if (!mainMap) throw new Error('Main map was not initialized');
    let click = mainMap.handlers.get('click');
    if (!click) throw new Error('Map click listener was not registered');

    choosePublished('Trimestre publicado', '2025T1');
    fireEvent.click(screen.getByRole('link', { name: 'Gas Próximamente' }));
    await waitFor(() =>
      expect(mainMap!.getLayer('municipios-fill')).toBeDefined(),
    );
    mainMap.features = [
      {
        layer: { 'source-layer': 'municipios' },
        properties: { ine_municipio: '28005' },
      },
    ];
    act(() => click({ point: { x: 100, y: 100 } }));

    expect(
      selectedTerritory('Alcalá de Henares'),
    ).toBeVisible();
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get('municipality')).toBe('28005');
    expect(params.get('period')).toBe('2025T1');
    expect(params.get('sector')).toBe('gas');
    expect(params.has('active_tab')).toBe(false);
    expect(params.get('campaign')).toBe('shared');
    expect(MapBoundary.instances).toHaveLength(2);
    expect(mainMap.handlers.get('click')).toBe(click);

    // Clicking the current territory refits it without navigating again.
    const selectedUrl = router.state.location.search;
    mainMap.fitBounds.mockClear();
    act(() => click({ point: { x: 100, y: 100 } }));
    expect(router.state.location.search).toBe(selectedUrl);
    expect(mainMap.fitBounds).toHaveBeenCalledTimes(1);
    expect(mainMap.fitBounds).toHaveBeenCalledWith(
      [
        [-3.5, 40.4],
        [-3.2, 40.6],
      ],
      expect.objectContaining({ maxZoom: 10.4 }),
    );

    await act(() => router.navigate(-1));
    expect(selectedTerritory('Madrid')).toBeVisible();
    expect(mainMap.setFeatureState).toHaveBeenLastCalledWith(
      { source: 'territorio', sourceLayer: 'municipios', id: '28079' },
      { selected: true },
    );
  });

  it('resets a search draft on history changes, preserves focus and scrolls keyboard options', async () => {
    const { router } = await renderHome('/?autonomous_community=13');
    const community = screen.getByRole('combobox', {
      name: 'Comunidad autónoma',
    });
    const bounds = vi
      .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
      .mockImplementation(function (this: HTMLElement) {
        return {
          top: this.getAttribute('role') === 'option' ? 760 : 0,
          bottom: this.getAttribute('role') === 'option' ? 800 : 600,
          left: 0,
          right: 300,
          width: 300,
          height: 40,
          x: 0,
          y: 0,
          toJSON: () => ({}),
        };
      });
    act(() => community.focus());
    fireEvent.change(community, { target: { value: 'canar' } });
    expect(community).toHaveValue('canar');
    fireEvent.keyDown(community, { key: 'ArrowDown' });
    const highlighted = document.getElementById(
      community.getAttribute('aria-activedescendant')!,
    );
    expect(highlighted).toHaveTextContent('Canarias');
    expect(screen.getByRole('listbox').scrollTop).toBeGreaterThan(0);
    expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
    bounds.mockRestore();
    await act(() => router.navigate('/?autonomous_community=05'));
    expect(community).toHaveFocus();
    expect(community).toHaveValue('Canarias · 05');
    expect(community).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    await act(() => router.navigate(-1));
    expect(community).toHaveValue('Comunidad de Madrid · 13');
    fireEvent.click(community);
    expect(screen.getByRole('listbox')).toBeVisible();
    fireEvent.keyDown(community, { key: 'ArrowUp' });
    expect(community).toHaveAttribute('aria-activedescendant');
    fireEvent.keyDown(community, { key: 'Escape' });
    expect(community).toHaveValue('Comunidad de Madrid · 13');
    expect(community).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(community);
    fireEvent.change(community, { target: { value: 'draft' } });
    const mainMap = MapBoundary.instances.find(
      (map) => map.options.cooperativeGestures,
    );
    act(() =>
      mainMap?.handlers.get('error')?.({
        error: new Error('Failed to fetch'),
      }),
    );
    expect(community).toBeDisabled();
    expect(community).toHaveValue('Comunidad de Madrid · 13');
    expect(community).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('selects published quarters and restores them through history', async () => {
    const { router } = await renderHome('/?period=2025T4&campaign=shared');
    const select = screen.getByRole('combobox', {
      name: 'Trimestre publicado',
    });
    await waitFor(() => expect(select).toBeEnabled());
    fireEvent.focus(select);
    expect(
      within(screen.getByRole('listbox', { name: 'Trimestre publicado' }))
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['4.º trimestre', '2.º trimestre', '1.º trimestre']);
    choosePublished('Trimestre publicado', '2025T1');
    expect(router.state.location.search).toBe('?period=2025T1&campaign=shared');
    await act(() => router.navigate(-1));
    expect(select).toHaveValue('4.º trimestre');
    await act(() => router.navigate(1));
    expect(select).toHaveValue('1.º trimestre');
  });

  it('scrubs only published quarters and keeps the manual selection in history', async () => {
    const { router } = await renderHome(
      '/?period=2025T4&marketer=R2-001&map_layer=market&campaign=shared',
    );
    await openMarketData('shares');
    await screen.findByRole('list', { name: 'Cuotas autonómicas · 2025T4' });
    const timeline = screen.getByRole('group', { name: 'Línea temporal del mapa' });
    const slider = within(timeline).getByRole('slider', {
      name: 'Trimestre del mapa',
    });
    expect(slider).toHaveAttribute('max', '2');
    fireEvent.change(slider, { target: { value: '1' } });
    expect(router.state.location.search).toContain('period=2025T2');
    expect(router.state.location.search).toContain('campaign=shared');
    await screen.findByRole('list', { name: 'Cuotas autonómicas · 2025T2' });
    fireEvent.click(
      within(timeline).getByRole('button', {
        name: 'Trimestre publicado anterior',
      }),
    );
    expect(router.state.location.search).toContain('period=2025T1');
    await act(() => router.navigate(-1));
    expect(slider).toHaveAttribute('aria-valuetext', '2.º trimestre de 2025');
  });

  it('toggles company details from its source link and closes on outside click or Escape', async () => {
    await renderHome('/?period=2025T4&marketer=R2-001');
    await openMarketData('shares');
    expect(screen.getByRole('region', { name: 'Datos de la comercializadora' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Cerrar datos' })).not.toBeInTheDocument();
    fireEvent.pointerDown(screen.getByRole('heading', { name: 'Explorar zonas eléctricas' }));
    expect(screen.queryByRole('region', { name: 'Datos de la comercializadora' })).not.toBeInTheDocument();
    await openMarketData('shares');
    fireEvent.keyDown(screen.getByRole('region', { name: 'Datos de la comercializadora' }), { key: 'Escape' });
    const trigger = screen.getByRole('button', { name: 'Cuotas y fuente' });
    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(trigger);
    fireEvent.click(trigger);
    expect(screen.queryByRole('region', { name: 'Datos de la comercializadora' })).not.toBeInTheDocument();
  });

  it('plays loaded map quarters and preserves the starting period for Back', async () => {
    const { router } = await renderHome(
      '/?period=2025T1&marketer=R2-001&map_layer=market',
    );
    await openMarketData('shares');
    await screen.findByRole('list', { name: 'Cuotas autonómicas · 2025T1' });
    await openMarketData('supplies');
    await screen.findByRole('listbox', { name: 'Comercializadora · código R2' });
    choosePublished('Velocidad', '2×');
    expect(screen.getByRole('combobox', { name: 'Velocidad' })).toHaveValue('2×');
    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByRole('button', { name: 'Reproducir trimestres' }));
      await act(async () => vi.advanceTimersByTimeAsync(900));
    } finally {
      vi.useRealTimers();
    }
    expect(router.state.location.search).toContain('period=2025T2');
    fireEvent.click(screen.getByRole('button', { name: 'Pausar reproducción' }));
    await act(() => router.navigate(-1));
    expect(router.state.location.search).toContain('period=2025T1');
    expect(screen.getByRole('button', { name: 'Reproducir trimestres' })).toBeVisible();
  });

  it('splits published years and quarters without selecting unavailable combinations', async () => {
    network.mockImplementation(async (config) => ({
      data: JSON.stringify(
        config.url?.endsWith('/quarters')
          ? {
              sector: 'electricity',
              quarters: [
                ...marketQuarters,
                ...['2024T2', '2024T1'].map((period) => ({
                  ...marketQuarters[0],
                  period,
                })),
              ],
            }
          : config.url?.includes('/v1/market/')
            ? marketResponse(config.url, config.params)
            : territoryLabels,
      ),
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }));
    const { router } = await renderHome('/?period=2025T4&campaign=shared');
    const year = screen.getByRole('combobox', { name: 'Año publicado' });
    const quarter = screen.getByRole('combobox', {
      name: 'Trimestre publicado',
    });
    await waitFor(() => expect(year).toBeEnabled());
    fireEvent.focus(year);
    expect(
      within(screen.getByRole('listbox', { name: 'Año publicado' }))
        .getAllByRole('option')
        .map((item) => item.textContent),
    ).toEqual(['2025', '2024']);
    choosePublished('Año publicado', '2024');
    expect(quarter).toHaveValue('2.º trimestre');
    fireEvent.focus(quarter);
    expect(
      within(screen.getByRole('listbox', { name: 'Trimestre publicado' }))
        .getAllByRole('option')
        .map((item) => item.textContent),
    ).toEqual(['2.º trimestre', '1.º trimestre']);
    choosePublished('Trimestre publicado', '2024T1');
    choosePublished('Año publicado', '2025');
    expect(quarter).toHaveValue('1.º trimestre');
    expect(
      new URLSearchParams(router.state.location.search).get('campaign'),
    ).toBe('shared');
    await act(() => router.navigate(-1));
    expect(year).toHaveValue('2024');
    expect(quarter).toHaveValue('1.º trimestre');
  });

  it('maps only community shares, distinguishes null from zero, and shares marketer selection', async () => {
    const { router } = await renderHome('/?period=2025T4&campaign=shared');
    const picker = screen.getByRole('combobox', {
      name: 'Comercializadora · código R2',
    });
    await waitFor(() => expect(picker).toBeEnabled());
    fireEvent.focus(picker);
    fireEvent.change(picker, { target: { value: 'R2-001' } });
    fireEvent.keyDown(picker, { key: 'Enter' });
    fireEvent.click(screen.getByRole('button', { name: 'Cuota comercializadora' }));
    await openMarketData('shares');
    const table = await screen.findByRole('list', {
      name: 'Cuotas autonómicas · 2025T4',
    });
    expect(table).toHaveTextContent('0 %');
    expect(table).toHaveTextContent('Sin denominador');
    const summary = within(
      screen.getByRole('region', { name: 'Cuotas autonómicas' }),
    );
    expect(summary.getByRole('link', { name: 'CC-BY-SA-4.0' })).toBeVisible();
    expect(summary.getByText('16 sept 2026')).toHaveAttribute(
      'datetime',
      '2026-09-16T09:54:27.287603',
    );
    expect(
      new URLSearchParams(router.state.location.search).get('marketer'),
    ).toBe('R2-001');
    expect(
      new URLSearchParams(router.state.location.search).get('campaign'),
    ).toBe('shared');
    const main = MapBoundary.instances.find(
      (map) => map.options.cooperativeGestures,
    )!;
    expect(main.layers.get('market-fill')).toMatchObject({
      'source-layer': 'ccaa',
    });
    expect(main.setPaintProperty).toHaveBeenLastCalledWith(
      'market-fill',
      'fill-color',
      [
        'match',
        ['get', 'ccaa_ine'],
        '13',
        '#eef4fb',
        '05',
        '#b6bcc4',
        '#e8e7e1',
      ],
    );
    const inset = MapBoundary.instances.find(
      (map) => !map.options.cooperativeGestures,
    )!;
    expect(inset.setPaintProperty).toHaveBeenLastCalledWith(
      'islas',
      'fill-color',
      expect.arrayContaining(['05', '#b6bcc4']),
    );
    await act(() =>
      router.navigate(
        '/?period=2025T4&marketer=R2-001&municipality=28079&map_layer=market',
      ),
    );
    expect(
      screen.getByRole('list', { name: 'Cuotas autonómicas · 2025T4' }),
    ).toHaveTextContent('Comunidad de Madrid');
    expect(
      network.mock.calls
        .filter(([config]) => config.url?.includes('/communities/'))
        .every(
          ([config]) =>
            !config.params.province &&
            !config.params.municipality &&
            !config.params.community_code,
        ),
    ).toBe(true);
    fireEvent.click(screen.getByRole('link', { name: 'Gas Próximamente' }));
    expect(main.setLayoutProperty).toHaveBeenLastCalledWith(
      'market-fill',
      'visibility',
      'none',
    );
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    await act(() => router.navigate(-1));
    await openMarketData('shares');
    expect(
      screen.getByRole('list', { name: 'Cuotas autonómicas · 2025T4' }),
    ).toBeVisible();
  });

  it('searches, sorts and expands community cards and synchronizes selection with the map and URL', async () => {
    network.mockImplementation(async (config) => {
      const response = config.url?.includes('/v1/market/')
        ? marketResponse(config.url, config.params)
        : territoryLabels;
      return {
        data: JSON.stringify(
          config.url?.includes('/communities/')
            ? {
                ...response,
                items: Array.from({ length: 19 }, (_, index) => ({
                  community_code: String(index + 1).padStart(2, '0'),
                  supplies: index <= 1 ? 0 : index,
                  marketer_supplies: index === 0 ? 0 : 100,
                  direct_consumer_supplies: 0,
                  unavailable_supplies: 0,
                  share: index === 0 ? null : index === 1 ? 0 : index / 100,
                })),
              }
            : response,
        ),
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      };
    });
    const { router } = await renderHome(
      '/?period=2025T4&marketer=R2-001&campaign=shared',
    );
    await openMarketData('shares');
    const list = await screen.findByRole('list', {
      name: 'Cuotas autonómicas · 2025T4',
    });
    expect(within(list).getAllByRole('listitem')).toHaveLength(5);
    expect(within(list).getAllByRole('listitem')[0]).toHaveTextContent('18 %');
    fireEvent.click(
      screen.getByRole('button', { name: 'Mostrar más comunidades (14)' }),
    );
    expect(within(list).getAllByRole('listitem')).toHaveLength(15);
    fireEvent.click(
      screen.getByRole('button', { name: 'Mostrar más comunidades (4)' }),
    );
    expect(within(list).getAllByRole('listitem')).toHaveLength(19);
    expect(list).toHaveTextContent('Sin denominador');
    expect(list).toHaveTextContent('0 %');
    choosePublished('Ordenar comunidades', 'name');
    expect(within(list).getAllByRole('listitem')[0]).toHaveTextContent(
      'Canarias',
    );
    fireEvent.change(
      screen.getByRole('searchbox', { name: 'Buscar comunidad' }),
      { target: { value: 'madrid' } },
    );
    expect(within(list).getAllByRole('listitem')).toHaveLength(1);
    fireEvent.click(within(list).getByRole('button'));
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get('autonomous_community')).toBe('13');
    expect(params.get('marketer')).toBe('R2-001');
    expect(params.get('period')).toBe('2025T4');
    expect(params.get('campaign')).toBe('shared');
    expect(within(list).getByRole('button')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    const main = MapBoundary.instances.find(
      (map) => map.options.cooperativeGestures,
    )!;
    expect(main.setFeatureState).toHaveBeenLastCalledWith(
      { source: 'territorio', sourceLayer: 'ccaa', id: '13' },
      { selected: true },
    );
    await act(() => router.navigate(-1));
    expect(within(list).getByRole('button')).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('shows supply counts in company search and selects without losing shared context', async () => {
    const companies = Array.from({ length: 8 }, (_, index) => ({
      marketer_code: `R2-${101 + index}`,
      observed_name: `Comercializadora ${String.fromCharCode(72 - index)}`,
      supplies: 100 - index,
    }));
    network.mockImplementation(async (config) => {
      const response = config.url?.includes('/v1/market/')
        ? marketResponse(config.url, config.params)
        : territoryLabels;
      return {
        data: JSON.stringify(
          config.url?.endsWith('/shares')
            ? {
                ...response,
                items: config.params.offset === 0 ? companies : [],
              }
            : response,
        ),
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      };
    });
    const { router } = await renderHome(
      '/?period=2025T1&autonomous_community=13&campaign=shared',
    );
    await openMarketData();
    const list = await screen.findByRole('listbox', {
      name: 'Comercializadora · código R2',
    });
    expect(within(list).getAllByRole('option')).toHaveLength(8);
    expect(within(list).getAllByRole('option')[0]).toHaveTextContent(
      'Comercializadora H',
    );
    expect(within(list).getAllByRole('option')[0]).toHaveTextContent('100 suministros');
    const search = screen.getByRole('combobox', { name: 'Comercializadora · código R2' });
    fireEvent.change(
      search,
      { target: { value: 'r2-108' } },
    );
    expect(within(list).getAllByRole('option')).toHaveLength(1);
    fireEvent.keyDown(search, { key: 'Enter' });
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get('marketer')).toBe('R2-108');
    expect(params.get('period')).toBe('2025T1');
    expect(params.get('autonomous_community')).toBe('13');
    expect(params.get('campaign')).toBe('shared');
    expect(params.get('map_layer')).toBe('market');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(screen.getByText('93 suministros')).toBeVisible();
    fireEvent.focus(search);
    fireEvent.change(
      search,
      { target: { value: 'no match' } },
    );
    expect(
      screen.getByText(
        'No hay coincidencias',
      ),
    ).toBeVisible();
  });

  it('keeps geographic companies as the default and scopes the marketer list to the parent community', async () => {
    const { router } = await renderHome('/?period=2025T1&municipality=28079');
    const main = MapBoundary.instances.find(
      (map) => map.options.cooperativeGestures,
    )!;
    expect(
      screen.getByRole('button', { name: 'Explorar zonas' }),
    ).toHaveAttribute('aria-pressed', 'true');
    expect(main.setLayoutProperty).toHaveBeenLastCalledWith(
      'market-fill',
      'visibility',
      'none',
    );
    await openMarketData();
    const table = await screen.findByRole('listbox', {
      name: 'Comercializadora · código R2',
    });
    expect(table).toHaveTextContent('R2-001');
    expect(network).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/v1/market/shares',
        params: {
          sector: 'electricity',
          period: '2025T1',
          community_code: '13',
          limit: 100,
          offset: 0,
        },
      }),
    );
    fireEvent.click(
      within(table).getByRole('option', { name: /^Comercializadora de prueba/ }),
    );
    expect(
      new URLSearchParams(router.state.location.search).get('marketer'),
    ).toBe('R2-001');
    fireEvent.click(screen.getByRole('button', { name: 'Cuota comercializadora' }));
    await waitFor(() =>
      expect(main.setLayoutProperty).toHaveBeenLastCalledWith(
        'market-fill',
        'visibility',
        'visible',
      ),
    );
    await act(() => router.navigate(-1));
    expect(main.setLayoutProperty).toHaveBeenLastCalledWith(
      'market-fill',
      'visibility',
      'none',
    );
    expect(
      screen.getByText('Mercado: ámbito nacional o autonómico.'),
    ).toBeVisible();
  });
});
