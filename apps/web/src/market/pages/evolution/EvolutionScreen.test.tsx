import { AxiosError } from 'axios';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { territoryLabels } from '../../../test/fixtures/territory-labels';
import { MapBoundary } from '../../../test/maplibre-boundary';
import { marketResponse } from '../../../test/fixtures/market';
import { choosePublished, network, renderExplorer as renderHome } from '../../../test/exploration-route-fixture';

vi.mock('maplibre-gl', async () => {
  const { MapBoundary } = await import('../../../test/maplibre-boundary');
  return {
    Map: MapBoundary,
    NavigationControl: class {},
    AttributionControl: class {},
    addProtocol: vi.fn(),
  };
});

describe('evolution route', () => {
  it.each(['/', '/evolution'])(
    'provides a focusable content destination on %s',
    async (entry) => {
      await renderHome(entry);
      const content = screen.getByRole('main');
      expect(content).toHaveAttribute('id', 'exploration-content');
      expect(content).toHaveAttribute('tabindex', '-1');
      expect(screen.getByRole('link', { name: 'Saltar al contenido' })).toHaveAttribute(
        'href',
        '#exploration-content',
      );
      expect(within(content).getAllByRole('heading', { level: 1 })).toHaveLength(1);
      expect(within(content).queryByRole('navigation', { name: 'Navegación principal' })).toBeNull();
    },
  );

  it('takes the empty evolution view to company search without changing the URL', async () => {
    const { router } = await renderHome('/evolution?campaign=shared');
    const search = screen.getByRole('combobox', { name: 'Comercializadora · código R2' });
    await waitFor(() => expect(search).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Buscar comercializadora' }));
    expect(search).toHaveFocus();
    expect(screen.getByRole('listbox')).toBeVisible();
    expect(router.state.location.pathname).toBe('/evolution');
    expect(router.state.location.search).toBe('?campaign=shared');
    expect(MapBoundary.instances).toHaveLength(0);
  });

  it('shows supplies with missing observations and the confirmed share-series contract', async () => {
    const { router } = await renderHome(
      '/evolution?period=2025T4&marketer=R2-001&municipality=28079',
    );
    await screen.findByRole('img', { name: /Evolución de suministros/ });
    const results = document.querySelector('.evolution-results') as HTMLElement;
    expect(results).toContainElement(screen.getByRole('group', { name: 'Dato de evolución' }));
    expect(results).toContainElement(screen.getByRole('group', { name: 'Presentación de la evolución' }));
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Tabla' }));
    const table = await screen.findByRole('table', {
      name: 'Suministros de Comercializadora de prueba · R2-001 · Comunidad de Madrid',
    });
    expect(table).toHaveTextContent('Sin observación');
    expect(
      screen.queryByRole('button', { name: 'Plegar información de zona' }),
    ).not.toBeInTheDocument();
    expect(MapBoundary.instances).toHaveLength(0);
    const toolbar = table
      .closest('.evolution-content')!
      .querySelector('.evolution-toolbar')! as HTMLElement;
    expect(within(toolbar).getAllByRole('combobox')).toHaveLength(2);
    expect(
      within(toolbar).getByRole('combobox', {
        name: 'Comercializadora · código R2',
      }),
    ).toHaveAccessibleName('Comercializadora · código R2');
    expect(
      screen.getByRole('group', { name: 'Filtros de suministros' }),
    ).toContainElement(
      screen.getByRole('combobox', { name: 'Ámbito territorial' }),
    );
    expect(table).toHaveTextContent('4.º trimestre de 2025');
    expect(table).toHaveTextContent('16 sept 2026');
    fireEvent.click(screen.getByRole('button', { name: 'Gráfico' }));
    const point = screen.getByRole('button', {
      name: '1.º trimestre de 2025: 25 suministros',
    });
    fireEvent.mouseEnter(point);
    expect(screen.getByRole('tooltip')).toHaveTextContent(
      '1.º trimestre de 2025',
    );
    expect(screen.getByRole('tooltip')).toHaveTextContent('25 suministros');
    fireEvent.mouseLeave(point);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    fireEvent.focus(point);
    expect(screen.getByRole('tooltip')).toBeVisible();
    fireEvent.keyDown(point, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', {
        name: '4.º trimestre de 2025: 0 suministros',
      }),
    );
    expect(screen.getByRole('tooltip')).toHaveTextContent('0 suministros');
    fireEvent.click(screen.getByRole('button', { name: 'Tabla' }));
    const currentTable = screen.getByRole('table', {
      name: 'Suministros de Comercializadora de prueba · R2-001 · Comunidad de Madrid',
    });
    fireEvent.click(
      within(currentTable).getByRole('button', { name: /Suministros/ }),
    );
    expect(
      within(currentTable).getByRole('columnheader', { name: /Suministros/ }),
    ).toHaveAttribute('aria-sort', 'ascending');
    let rows = within(currentTable).getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('4.º trimestre');
    expect(rows.at(-1)).toHaveTextContent('Sin observación');
    fireEvent.click(
      within(currentTable).getByRole('button', { name: /Suministros/ }),
    );
    rows = within(currentTable).getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('1.º trimestre');
    expect(rows.at(-1)).toHaveTextContent('Sin observación');
    choosePublished('Observaciones', 'zero');
    expect(within(currentTable).getAllByRole('row')).toHaveLength(2);
    expect(currentTable).not.toHaveTextContent('Sin observación');
    choosePublished('Trimestre', '1');
    expect(
      screen.getByText(/No hay trimestres con estos filtros/),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole('button', { name: 'Restablecer filtros' }),
    );
    expect(within(currentTable).getAllByRole('row')).toHaveLength(4);
    fireEvent.change(
      screen.getByRole('spinbutton', { name: 'Suministros mínimos' }),
      { target: { value: '1' } },
    );
    expect(within(currentTable).getAllByRole('row')).toHaveLength(2);
    expect(currentTable).toHaveTextContent('1.º trimestre');
    fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    expect(
      screen.queryByRole('img', { name: /Evolución de suministros/ }),
    ).not.toBeInTheDocument();
    expect(network).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/v1/market/series/R2-001',
        params: { sector: 'electricity', community_code: '13' },
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Cuota' }));
    const shares = await screen.findByRole('table', {
      name: 'Cuota de Comercializadora de prueba · R2-001 · Comunidad de Madrid',
    });
    expect(shares).toHaveTextContent('Sin denominador');
    expect(shares).toHaveTextContent('0 %');
    expect(
      screen.queryByRole('img', { name: /Evolución de cuota/ }),
    ).not.toBeInTheDocument();
    expect(
      new URLSearchParams(router.state.location.search).get('metric'),
    ).toBe('share');
    expect(network).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/v1/market/share-series/R2-001',
        params: { sector: 'electricity', community_code: '13', limit: 120 },
      }),
    );
    await act(() => router.navigate(-1));
    expect(
      screen.getByRole('table', {
        name: 'Suministros de Comercializadora de prueba · R2-001 · Comunidad de Madrid',
      }),
    ).toBeVisible();
  });

  it('filters the chart and table together, keeps the latest revision visible and restores display through history', async () => {
    const { router } = await renderHome(
      '/evolution?period=2025T4&marketer=R2-001',
    );
    const chart = await screen.findByRole('img', {
      name: /Evolución de suministros/,
    });
    const filters = screen.getByRole('group', {
      name: 'Filtros de suministros',
    });
    expect(
      filters.compareDocumentPosition(chart) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    choosePublished('Trimestre', '4');
    expect(chart.querySelectorAll('.chart-point-target')).toHaveLength(1);
    expect(
      within(chart).getByRole('button', { name: /0 suministros/ }),
    ).toBeVisible();
    const updated = screen.getByText(/Último trimestre publicado:/);
    expect(updated).toHaveTextContent('4.º trimestre de 2025');
    expect(updated).toHaveTextContent('16 sept 2026');
    fireEvent.click(screen.getByRole('button', { name: 'Tabla' }));
    expect(
      screen.queryByRole('img', { name: /Evolución de suministros/ }),
    ).not.toBeInTheDocument();
    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(table).toHaveTextContent('4.º trimestre de 2025');
    expect(
      new URLSearchParams(router.state.location.search).get('display'),
    ).toBe('table');
    await act(() => router.navigate(-1));
    expect(screen.getByRole('button', { name: 'Gráfico' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('combobox', { name: 'Trimestre' })).toHaveValue(
      '4.º trimestre',
    );
    choosePublished('Trimestre', '1');
    expect(
      screen.getByRole('button', { name: /25 suministros/ }),
    ).toBeVisible();
    expect(updated).toHaveTextContent('4.º trimestre de 2025');
    fireEvent.click(screen.getByRole('button', { name: 'Cuota' }));
    const shares = await screen.findByRole('img', {
      name: /Evolución de cuota/,
    });
    expect(within(shares).getAllByRole('button')).toHaveLength(1);
    expect(within(shares).getByText('30 %')).toBeInTheDocument();
    expect(
      screen.queryByRole('spinbutton', { name: 'Suministros mínimos' }),
    ).not.toBeInTheDocument();
  });

  it('compares registered codes with independent series, common filters, share curves and URL history', async () => {
    const { router } = await renderHome(
      '/evolution?period=2025T4&marketer=R2-001&autonomous_community=13',
    );
    await screen.findByRole('img', { name: /Evolución de suministros/ });
    const picker = screen.getByRole('combobox', {
      name: 'Añadir comercializadora a la comparación',
    });
    await waitFor(() => expect(picker).toBeEnabled());
    fireEvent.focus(picker);
    fireEvent.change(picker, { target: { value: 'R2-002' } });
    fireEvent.keyDown(picker, { key: 'Enter' });
    const chart = await screen.findByRole('img', {
      name: 'Comparación de suministros en Comunidad de Madrid',
    });
    await screen.findByRole('button', {
      name: 'Otra comercializadora de prueba · R2-002: 1.º trimestre de 2025, 75 suministros',
    });
    expect(chart.querySelectorAll('.chart-point-target')).toHaveLength(4);
    expect(
      new URLSearchParams(router.state.location.search).get('compare'),
    ).toBe('R2-002');
    expect(network).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/v1/market/series/R2-002',
        params: { sector: 'electricity', community_code: '13' },
      }),
    );
    const point = within(chart).getByRole('button', {
      name: /R2-002: 1.º trimestre/,
    });
    fireEvent.focus(point);
    expect(screen.getByRole('tooltip')).toHaveTextContent('75 suministros');
    expect(screen.getByRole('tooltip')).toHaveTextContent('Otra comercializadora de prueba · R2-002');
    choosePublished('Trimestre', '1');
    expect(chart.querySelectorAll('.chart-point-target')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Tabla' }));
    const table = screen.getByRole('table', {
      name: 'Comparación de suministros · Comunidad de Madrid',
    });
    expect(table).toHaveTextContent('75');
    expect(table).toHaveTextContent('25');
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    fireEvent.click(within(table).getByRole('button', { name: 'Otra comercializadora de prueba · R2-002' }));
    expect(
      within(table).getByRole('columnheader', { name: 'Otra comercializadora de prueba · R2-002' }),
    ).toHaveAttribute('aria-sort', 'ascending');
    fireEvent.click(screen.getByRole('button', { name: 'Cuota' }));
    const shares = await screen.findByRole('table', {
      name: 'Comparación de cuotas · Comunidad de Madrid',
    });
    await waitFor(() => expect(shares).toHaveTextContent('75 %'));
    expect(shares).toHaveTextContent('25 %');
    choosePublished('Trimestre', '2');
    expect(within(shares).getAllByText('Sin denominador')).toHaveLength(2);
    fireEvent.click(
      screen.getByRole('button', { name: 'Quitar Otra comercializadora de prueba · R2-002 de la comparación' }),
    );
    expect(
      new URLSearchParams(router.state.location.search).has('compare'),
    ).toBe(false);
    await act(() => router.navigate(-1));
    expect(
      screen.getByRole('button', { name: 'Quitar Otra comercializadora de prueba · R2-002 de la comparación' }),
    ).toBeVisible();
    expect(MapBoundary.instances).toHaveLength(0);
  });

  it('keeps the primary chart visible at the same viewport while another series loads', async () => {
    let finishLoading = () => {};
    const pending = new Promise<void>((resolve) => { finishLoading = resolve; });
    network.mockImplementation(async (config) => {
      if (config.url?.endsWith('/v1/market/series/R2-002')) await pending;
      return {
        data: JSON.stringify(config.url?.includes('/v1/market/')
          ? marketResponse(config.url, config.params)
          : territoryLabels),
        status: 200, statusText: 'OK', headers: {}, config,
      };
    });
    await renderHome('/evolution?period=2025T4&marketer=R2-001');
    const original = await screen.findByRole('img', { name: /Evolución de suministros/ });
    act(() => {
      vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(360);
      window.dispatchEvent(new Event('resize'));
    });
    expect(original.getAttribute('viewBox')).toMatch(/^0 0 360 /);
    const picker = screen.getByRole('combobox', {
      name: 'Añadir comercializadora a la comparación',
    });
    fireEvent.focus(picker);
    fireEvent.change(picker, { target: { value: 'R2-002' } });
    fireEvent.keyDown(picker, { key: 'Enter' });
    const comparison = await screen.findByRole('img', {
      name: 'Comparación de suministros en España',
    });
    expect(comparison).toBe(original);
    expect(comparison).toHaveClass('supplies-chart');
    expect(comparison).toHaveAttribute('viewBox', original.getAttribute('viewBox'));
    expect(within(comparison).getByRole('button', {
      name: /Comercializadora de prueba · R2-001: 1.º trimestre/,
    })).toBeInTheDocument();
    expect(screen.getByText('Cargando Otra comercializadora de prueba · R2-002…')).toBeInTheDocument();
    expect(screen.getByLabelText('Series del gráfico')).toHaveTextContent('Otra comercializadora de prueba · R2-002 · Cargando…');
    finishLoading();
    expect(await within(comparison).findByRole('button', {
      name: /Otra comercializadora de prueba · R2-002: 1.º trimestre/,
    })).toBeInTheDocument();
  });

  it('clears all comparison codes while preserving the primary code, scope, filters and history', async () => {
    const { router } = await renderHome(
      '/evolution?period=2025T4&marketer=R2-001&compare=R2-002,R2-003&autonomous_community=13',
    );
    await screen.findByRole('img', {
      name: 'Comparación de suministros en Comunidad de Madrid',
    });
    choosePublished('Trimestre', '1');
    fireEvent.click(
      screen.getByRole('button', { name: 'Limpiar comparación' }),
    );
    const params = new URLSearchParams(router.state.location.search);
    expect(params.has('compare')).toBe(false);
    expect(params.get('marketer')).toBe('R2-001');
    expect(params.get('autonomous_community')).toBe('13');
    expect(params.get('period')).toBe('2025T4');
    expect(screen.getByRole('combobox', { name: 'Trimestre' })).toHaveValue(
      '1.º trimestre',
    );
    expect(
      screen.queryByRole('button', { name: 'Limpiar comparación' }),
    ).not.toBeInTheDocument();
    const chart = await screen.findByRole('img', {
      name: /Evolución de suministros/,
    });
    expect(chart).toHaveTextContent('CUPS (suministros)');
    expect(chart).toHaveTextContent('Trimestre y año');
    await act(() => router.navigate(-1));
    expect(
      screen.getByRole('button', { name: 'Quitar Otra comercializadora de prueba · R2-002 de la comparación' }),
    ).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Quitar Nombre no disponible · R2-003 de la comparación' }),
    ).toBeVisible();
  });

  it('keeps a successful comparison visible after a second series fails and retries only that code', async () => {
    let unavailable = true;
    network.mockImplementation(async (config) => {
      if (unavailable && config.url?.endsWith('/series/R2-002'))
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
      return {
        data: JSON.stringify(
          config.url?.includes('/v1/market/')
            ? marketResponse(config.url, config.params)
            : territoryLabels,
        ),
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      };
    });
    await renderHome(
      '/evolution?period=2025T4&marketer=R2-001&compare=R2-002,R2-000,R2-002,invalid',
    );
    await screen.findByRole('button', { name: 'Reintentar Otra comercializadora de prueba · R2-002' });
    const chart = screen.getByRole('img', {
      name: 'Comparación de suministros en España',
    });
    expect(chart.querySelectorAll('.chart-point-target')).toHaveLength(2);
    expect(
      screen.queryByRole('button', { name: /R2-002:.*suministros/ }),
    ).not.toBeInTheDocument();
    expect(
      network.mock.calls.some(([config]) =>
        config.url?.includes('/series/R2-000'),
      ),
    ).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Tabla' }));
    expect(screen.getByRole('table')).toHaveTextContent('Error de carga');
    expect(screen.getByRole('table')).toHaveTextContent('25');
    const primaryCalls = network.mock.calls.filter(([config]) =>
      config.url?.endsWith('/series/R2-001'),
    ).length;
    unavailable = false;
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar Otra comercializadora de prueba · R2-002' }));
    await waitFor(() =>
      expect(screen.getByRole('table')).toHaveTextContent('75'),
    );
    expect(screen.getByRole('table')).not.toHaveTextContent('Error de carga');
    expect(
      network.mock.calls.filter(([config]) =>
        config.url?.endsWith('/series/R2-001'),
      ),
    ).toHaveLength(primaryCalls);
  });

  it('changes the evolution area inline and restores it through history without mounting maps', async () => {
    const { router } = await renderHome(
      '/evolution?period=2025T4&marketer=R2-001&municipality=28079&campaign=shared&display=table',
    );
    await screen.findByRole('table', {
      name: 'Suministros de Comercializadora de prueba · R2-001 · Comunidad de Madrid',
    });
    choosePublished('Ámbito territorial', '');
    await screen.findByRole('table', {
      name: 'Suministros de Comercializadora de prueba · R2-001 · España',
    });
    const params = new URLSearchParams(router.state.location.search);
    expect(params.has('municipality')).toBe(false);
    expect(params.get('campaign')).toBe('shared');
    expect(params.get('marketer')).toBe('R2-001');
    expect(params.get('period')).toBe('2025T4');
    await act(() => router.navigate(-1));
    expect(
      screen.getByRole('combobox', { name: 'Ámbito territorial' }),
    ).toHaveValue('Comunidad de Madrid');
    expect(MapBoundary.instances).toHaveLength(0);
    expect(
      screen.queryByRole('combobox', { name: 'Municipio' }),
    ).not.toBeInTheDocument();
  });
});
