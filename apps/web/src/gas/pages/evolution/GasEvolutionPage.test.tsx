import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { appRoutes } from '../../../app.router';
import { choosePublished, network, renderRoute, seedQueryCache } from '../../../test/exploration-route-fixture';
import { gasRetailAudit, gasRetailContext, gasRetailResponse, gasRetailRevision, gasRetailSource, gasRetailValue } from '../../../test/fixtures/gas-retail';
import type { GasSeries } from '../../interfaces/retail';

async function open(search = '') {
  const router = createMemoryRouter(appRoutes, { initialEntries: [`/evolution?sector=gas${search}`] });
  renderRoute(router);
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Comercializadora observada' })).toBeEnabled());
  return router;
}
describe('gas evolution', () => {
  it('explains selected company identities without changing API labels, IDs or histories', async () => {
    const companies = [
      ['gas-eni-plenitude', 'Eni Plenitude Iberia'],
      ['gas-company-8b97b3e0f7b732176cf4', 'Eni España'],
      ['gas-cepsa-gas', 'Cepsa Gas / Moeve'],
      ['gas-cepsa-commercial', 'Cepsa Comercial Petróleo'],
      ['gas-test-unrelated', 'Plenitude sin correspondencia'],
    ];
    network.mockImplementation(async (config) => {
      const body = gasRetailResponse(config.url!, config.params);
      const response = config.url?.endsWith('/marketers') ? { ...body, total: companies.length, items: companies.map(([code, name]) => ({ marketer_id: code, company_name: name, observed_name: name, source: gasRetailSource, mapping_review_note: 'Correspondencia sintética para probar el selector.' })) } : body;
      return { data: JSON.stringify(response), status: 200, statusText: 'OK', headers: {}, config };
    });
    const router = await open();
    const selector = screen.getByRole('combobox', { name: 'Comercializadora observada' });
    fireEvent.focus(selector);
    const plenitude = screen.getByRole('option', { name: /Eni Plenitude Iberia/ });
    expect(plenitude).toHaveTextContent('Plenitude · hogares y empresas');
    expect(screen.getByRole('option', { name: /Eni España Comercializadora/ })).toHaveTextContent('industria, pymes y mayoristas');
    expect(screen.getByRole('option', { name: /Cepsa Gas \/ Moeve/ })).toHaveTextContent('no es el grupo completo');
    expect(screen.getByRole('option', { name: /actualmente Moeve Commercial/ })).toHaveTextContent('Cepsa Comercial Petróleo');
    expect(screen.getByRole('option', { name: 'Plenitude sin correspondencia' }).querySelector('.selector-option-detail')).toBeNull();
    fireEvent.click(plenitude);
    expect(selector).toHaveValue('Eni Plenitude Iberia');
    expect(new URLSearchParams(router.state.location.search).get('marketer')).toBe('gas-eni-plenitude');
    const comparison = screen.getByRole('combobox', { name: 'Añadir comercializadora a la comparación' });
    for (const name of [/Eni España Comercializadora/, /Cepsa Gas \/ Moeve/, /actualmente Moeve Commercial/]) {
      fireEvent.focus(comparison);
      fireEvent.click(screen.getByRole('option', { name }));
    }
    expect(new URLSearchParams(router.state.location.search).get('compare')).toBe('gas-company-8b97b3e0f7b732176cf4,gas-cepsa-gas,gas-cepsa-commercial');
    expect(comparison).toBeDisabled();
    fireEvent.click(screen.getByText(/Contexto actual de las empresas seleccionadas/));
    expect(screen.getByText(/no describe los segmentos de clientes de toda la serie histórica/)).toBeVisible();
    expect(screen.getByText(/Un cambio de marca no demuestra una fusión legal/)).toBeVisible();
    expect(screen.getByText('29/10/2026')).toHaveAttribute('datetime', '2026-10-29');
    expect(screen.getByRole('link', { name: 'Eni · Plenitude' })).toHaveAttribute('href', 'https://www.eni.com/es-ES/operaciones/plenitude.html');
    expect(screen.getByRole('link', { name: 'Eni · Eni España' })).toHaveAttribute('href', 'https://www.eni.com/es-ES/operaciones/eni-espana.html');
    expect(screen.getByRole('link', { name: 'Moeve · Gas natural' })).toHaveAttribute('href', 'https://www.moeve.es/es/utilidades/catalogo/natural-gas');
    expect(screen.getByRole('link', { name: 'BOE · denominación anterior y actual' })).toHaveAttribute('href', 'https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-4522');
    await waitFor(() => expect(network.mock.calls.filter(([c]) => c.url?.includes('/series/')).map(([c]) => c.url?.split('/').at(-1))).toEqual(expect.arrayContaining(companies.slice(0, 4).map(([code]) => code))));
    fireEvent.click(screen.getByRole('button', { name: 'Borrar comercializadora observada' }));
    expect(screen.queryByText(/Contexto actual de las empresas seleccionadas/)).not.toBeInTheDocument();
  });
  it('does not reuse a cached document catalogue from the previous frontend contract', async () => {
    seedQueryCache(['gas', 'retail', 'revision', ''], gasRetailRevision);
    seedQueryCache(['gas', 'retail', 'marketers', gasRetailRevision.load_id, { metric: 'clients', scope: 'whole_market' }], {
      ...gasRetailContext, total: 1, limit: 100, offset: 0,
      items: [{ marketer_id: 'gas-cnmc-066-0a1b6098c155', company_name: 'Antigua opción documental', observed_name: 'Antigua opción documental', source: gasRetailSource }],
    });
    await open();
    fireEvent.focus(screen.getByRole('combobox', { name: 'Comercializadora observada' }));
    expect(screen.queryByRole('option', { name: /Antigua opción/ })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Empresa sintética 0' })).toBeVisible();
    expect(network.mock.calls.some(([config]) => config.url?.endsWith('/marketers'))).toBe(true);
  });
  it('drops retired document selections while preserving revision pins and URL navigation', async () => {
    network.mockImplementation(async (config) => {
      const body = gasRetailResponse(config.url!, config.params);
      const load = config.params.load_id || gasRetailRevision.load_id;
      const response = config.url?.endsWith('/revisions') ? { ...body, items: [{ ...gasRetailRevision, load_id: load }] }
        : { ...body, revision: { ...gasRetailRevision, load_id: load } };
      return { data: JSON.stringify(response), status: 200, statusText: 'OK', headers: {}, config };
    });
    const router = await open(`&load_id=${'b'.repeat(64)}&marketer=gas-cnmc-066-0a1b6098c155&compare=gas-cnmc-068-0a1b6098c155`);
    expect(router.state.location.search).not.toContain('marketer=');
    expect(router.state.location.search).not.toContain('compare=');
    expect(screen.getByText(/La selección anterior usaba identificadores/)).toBeVisible();
    expect(await screen.findByText(/Revisión fijada en este enlace/)).toBeVisible();
    await act(() => router.navigate('/evolution?sector=gas'));
    await waitFor(() => expect(router.state.location.search).not.toContain('load_id='));
    expect(screen.queryByText(/Revisión fijada en este enlace/)).not.toBeInTheDocument();
    await waitFor(() => expect(network.mock.calls.some(([c]) => c.url?.endsWith('/revisions') && !c.params.load_id)).toBe(true));
  });
  it('keeps the chart height fixed while scrolling changes its position and a point gains focus', async () => {
    let top = 400;
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(() => new DOMRect(0, top, 900, 600));
    await open('&marketer=gas-test-0');
    const chart = await screen.findByRole('img', { name: /Evolución de clientes/ });
    const point = within(chart).getAllByRole('button')[0];
    const height = chart.style.height;
    top = 20;
    fireEvent.focus(point);
    expect(screen.getByRole('tooltip')).toHaveTextContent('100 clientes');
    expect(chart.style.height).toBe(height);
    fireEvent.mouseEnter(point);
    expect(chart.style.height).toBe(height);
  });
  it('defaults to whole-market clients and uses only gas endpoints without geographical filters', async () => {
    await open('&province=28&marketer=R2-001');
    expect(screen.getByRole('button', { name: 'Clientes' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('combobox', { name: 'Ámbito histórico del mercado' })).toHaveValue('whole_market');
    expect(screen.queryByRole('combobox', { name: 'Ámbito territorial' })).not.toBeInTheDocument();
    expect(screen.getByText(/Geografía definida por cada fuente/)).toBeVisible();
    expect(network.mock.calls.every(([c]) => c.url?.startsWith('/v1/gas/'))).toBe(true);
    expect(network.mock.calls.every(([c]) => !c.params.province && !c.params.community)).toBe(true);
  });
  it('anchors details beside the active point and keeps them inside the chart edges', async () => {
    vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(180);
    vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(60);
    await open('&marketer=gas-test-0');
    const chart = await screen.findByRole('img', { name: /Evolución de clientes/ });
    const points = within(chart).getAllByRole('button');
    expect(chart.querySelector('title')).toBeNull();
    expect(chart.querySelector('desc')).toHaveTextContent('los huecos');
    expect(chart.querySelector('[title]')).toBeNull();
    fireEvent.mouseEnter(points[0]);
    const tooltip = screen.getByRole('tooltip');
    const firstLeft = Number.parseFloat(tooltip.style.left);
    const firstTop = Number.parseFloat(tooltip.style.top);
    expect(firstLeft).toBe(8);
    expect(firstTop).toBe(Number(points[0].getAttribute('cy')) + 12);
    fireEvent.mouseLeave(points[0]);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    fireEvent.focus(points[1]);
    const lastTooltip = screen.getByRole('tooltip');
    const width = Number(chart.getAttribute('viewBox')!.split(' ')[2]);
    expect(Number.parseFloat(lastTooltip.style.left)).toBe(width - 180 - 8);
    expect(Number.parseFloat(lastTooltip.style.top)).toBe(Number(points[1].getAttribute('cy')) - 60 - 12);
    expect(lastTooltip).toHaveTextContent('0 clientes');
  });
  it('switches metrics and scopes, clears incompatible identities, and restores filters through history', async () => {
    const router = await open('&marketer=gas-test-0&compare=gas-test-1&display=table');
    expect(await screen.findAllByRole('cell', { name: '100 clientes' })).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Ventas (MWh)' }));
    expect(router.state.location.search).toContain('metric=sales');
    expect(router.state.location.search).not.toContain('marketer=');
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Comercializadora observada' })).toBeEnabled());
    choosePublished('Comercializadora observada', 'Empresa sintética 0');
    expect(await screen.findByRole('cell', { name: '1000 MWh' })).toBeVisible();
    fireEvent.change(screen.getByRole('combobox', { name: 'Ámbito histórico del mercado' }), { target: { value: 'liberalised' } });
    expect(router.state.location.search).toContain('scope=liberalised');
    expect(router.state.location.search).not.toContain('marketer=');
    await act(() => router.navigate(-1));
    expect(screen.getByRole('combobox', { name: 'Ámbito histórico del mercado' })).toHaveValue('whole_market');
    expect(await screen.findByRole('cell', { name: '1000 MWh' })).toBeVisible();
    await act(() => router.navigate(1));
    expect(screen.getByRole('combobox', { name: 'Ámbito histórico del mercado' })).toHaveValue('liberalised');
  });
  it('uses the shared searchable dropdown for the full catalogue and limits comparison to four companies', async () => {
    const router = await open('&marketer=gas-test-0&compare=gas-test-1,gas-test-2,gas-test-3,gas-test-4,gas-test-0');
    expect(new URLSearchParams(router.state.location.search).get('compare')).toBe('gas-test-1,gas-test-2,gas-test-3');
    expect(screen.getByRole('combobox', { name: 'Añadir comercializadora a la comparación' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Siguiente' })).not.toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(new URLSearchParams(router.state.location.search).get('marketer')).toBe('gas-test-0');
    fireEvent.click(screen.getByRole('button', { name: 'Limpiar comparación' }));
    choosePublished('Añadir comercializadora a la comparación', 'Empresa sintética 24');
    expect(new URLSearchParams(router.state.location.search).get('compare')).toBe('gas-test-24');
    expect(network.mock.calls.filter(([c]) => c.url?.endsWith('/marketers'))).toHaveLength(1);
  });
  it('shows bounded and missing values in tables, uses no invented chart points, and exposes provenance', async () => {
    const router = await open('&marketer=gas-test-0');
    const chart = await screen.findByRole('img', { name: /Evolución de clientes/ });
    await waitFor(() => expect(within(chart).getAllByRole('button')).toHaveLength(2));
    expect(chart.querySelectorAll('polyline')).toHaveLength(2);
    expect(screen.queryByText(/límite exclusivo, sin punto/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Los huecos no equivalen a cero/)).not.toBeInTheDocument();
    expect(screen.queryByText('Cómo leer las series y sus identidades')).not.toBeInTheDocument();
    expect(screen.queryByText('Cobertura, problemas de las fuentes y revisión')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Actualizar datos|Usar revisión más reciente/ })).not.toBeInTheDocument();
    expect(screen.getByText('Valores, notas y fuentes por trimestre')).toBeVisible();
    for (const name of ['Gráfico', 'Tabla']) {
      const toggle = screen.getByRole('button', { name });
      expect(toggle.textContent).toBe('');
      expect(toggle.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    }
    expect(screen.getByRole('button', { name: 'Gráfico' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.focus(within(chart).getAllByRole('button')[0]);
    expect(screen.getByRole('tooltip')).toHaveTextContent('100 clientes');
    fireEvent.keyDown(within(chart).getAllByRole('button')[0], { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Tabla' }));
    expect(screen.getByRole('button', { name: 'Tabla' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('cell', { name: '<50 clientes' })).toBeVisible();
    expect(screen.getByRole('cell', { name: 'Revisión parcial' })).toBeVisible();
    expect(screen.getByRole('cell', { name: '0 clientes' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Cuota' }));
    expect(screen.getByRole('cell', { name: '1 %' })).toBeVisible();
    expect(screen.getByRole('cell', { name: /Sin cuota/ })).toBeVisible();
    fireEvent.change(screen.getByRole('combobox', { name: 'Desde el trimestre' }), { target: { value: '2025T3' } });
    await waitFor(() => expect(screen.queryByRole('rowheader', { name: 'T1 2025' })).not.toBeInTheDocument());
    expect(router.state.location.search).toContain('start_period=2025T3');
    expect(screen.getAllByRole('link', { hidden: true }).some((link) => link.getAttribute('href') === 'https://example.org/gas.pdf#page=3')).toBe(true);
  });
  it('starts page navigation at defaults and clears identifiers when changing sectors', async () => {
    const router = await open('&marketer=gas-test-0&metric=sales&scope=liberalised&search=test&page=2');
    fireEvent.click(screen.getByRole('link', { name: 'Tarifa regulada' }));
    expect(router.state.location).toMatchObject({ pathname: '/regulated-tariff', search: '?sector=gas' });
    expect(await screen.findByRole('heading', { name: 'Catálogo con evidencia fechada' })).toBeVisible();
    fireEvent.click(screen.getByRole('link', { name: 'Electricidad' }));
    expect(router.state.location).toMatchObject({ pathname: '/regulated-tariff', search: '' });
    await act(() => router.navigate(-2));
    expect(router.state.location.search).toContain('marketer=gas-test-0');
    fireEvent.click(screen.getByRole('link', { name: 'Evolución' }));
    expect(router.state.location.search).toBe('?sector=gas');
  });
  it('offers retry after a revision failure and preserves empty coverage without zeros', async () => {
    network.mockRejectedValueOnce(new Error('offline'));
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/evolution?sector=gas'] });
    renderRoute(router);
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar la revisión');
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar revisión' }));
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Comercializadora observada' })).toBeEnabled());
    network.mockImplementation(async (config) => ({ data: JSON.stringify({ ...gasRetailResponse(config.url!, config.params), total: 0, items: [] }), status: 200, statusText: 'OK', headers: {}, config }));
    fireEvent.click(screen.getByRole('button', { name: 'Ventas (MWh)' }));
    expect(await screen.findByText(/No hay comercializadoras revisadas/)).toBeVisible();
    expect(screen.getByText('No hay periodos de auditoría para estos filtros.')).toBeVisible();
  });
  it('connects consecutive reviewed quarters for one canonical company across documents, but breaks at unreviewed quarters', async () => {
    network.mockImplementation(async (config) => {
      let body: unknown = gasRetailResponse(config.url!, config.params);
      if (config.url?.includes('/series/')) {
        const series = body as GasSeries;
        series.items = ['2025T1', '2025T2', '2025T3', '2025T4'].map((period, i) => {
          const source = { ...gasRetailSource, source_id: `report-${i}`, url: `https://example.org/report-${i}.pdf` };
          const base = gasRetailValue('gas-test-0', period);
          const record = { ...base, status: 'exact' as const, value: String(100 + i), upper_bound: null, source, observations: base.observations.map((o) => ({ ...o, observed_name: `Nombre histórico ${i}` })), denominator: base.denominator ? { ...base.denominator, source } : null };
          return { audit: { ...gasRetailAudit(period), status: i === 2 ? 'partial' : 'reviewed', sources: [source] }, availability: i === 2 ? 'unreviewed' : 'reviewed', records: i === 2 ? [] : [record] };
        });
        body = series;
      }
      return { data: JSON.stringify(body), status: 200, statusText: 'OK', headers: {}, config };
    });
    await open('&marketer=gas-test-0');
    const chart = screen.getByRole('img', { name: /Evolución de clientes/ });
    await waitFor(() => expect(within(chart).getAllByRole('button')).toHaveLength(3));
    const segments = [...chart.querySelectorAll('polyline')].map((p) => p.getAttribute('points')!.split(' ').length);
    expect(segments).toEqual([2, 1]);
    fireEvent.click(screen.getByRole('button', { name: 'Tabla' }));
    expect(screen.getByRole('cell', { name: 'Revisión parcial' })).toBeVisible();
    expect(screen.getAllByRole('link', { hidden: true }).some((a) => a.getAttribute('href') === 'https://example.org/report-1.pdf#page=3')).toBe(true);
  });
  it('keeps one canonical option without document titles and retains its label while searching comparisons', async () => {
    network.mockImplementation(async (config) => {
      let body = gasRetailResponse(config.url!, config.params);
      if (config.url?.endsWith('/marketers')) {
        const items = Array.from({ length: 25 }, (_, i) => ({ marketer_id: `gas-test-${i}`, company_name: i === 0 ? 'Empresa canónica' : `Otra empresa ${i}`, observed_name: i === 0 ? 'Nombre histórico' : `Otra empresa ${i}`, source: gasRetailSource, mapping_review_note: 'Correspondencia revisada.' }));
        const offset = Number(config.params.offset), limit = Number(config.params.limit);
        body = { ...gasRetailContext, metric: 'clients', scope: 'whole_market', total: 25, offset, limit, items: items.slice(offset, offset + limit) } as typeof body;
      }
      if (config.url?.includes('/series/gas-test-0')) body = { ...body, company_name: 'Empresa canónica' };
      return { data: JSON.stringify(body), status: 200, statusText: 'OK', headers: {}, config };
    });
    await open();
    fireEvent.focus(screen.getByRole('combobox', { name: 'Comercializadora observada' }));
    expect(screen.getAllByRole('option', { name: 'Empresa canónica' })).toHaveLength(1);
    expect(screen.queryByRole('option', { name: /Informe sintético/ })).not.toBeInTheDocument();
    choosePublished('Comercializadora observada', 'Empresa canónica');
    choosePublished('Añadir comercializadora a la comparación', 'Otra empresa 24');
    expect(screen.getByRole('combobox', { name: 'Comercializadora observada' })).toHaveValue('Empresa canónica');
    expect(within(screen.getByLabelText('Series del gráfico')).getByText('Empresa canónica')).toBeVisible();
  });
  it('removes retired pagination and external search parameters without losing the selection', async () => {
    const router = await open('&page=99&limit=20&search=old&marketer=gas-test-0');
    expect(new URLSearchParams(router.state.location.search).has('page')).toBe(false);
    expect(new URLSearchParams(router.state.location.search).has('limit')).toBe(false);
    expect(new URLSearchParams(router.state.location.search).has('search')).toBe(false);
    expect(new URLSearchParams(router.state.location.search).get('marketer')).toBe('gas-test-0');
    expect(router.state.historyAction).toBe('REPLACE');
  });
  it('does not merge distinct API company identities by their display label', async () => {
    network.mockImplementation(async (config) => {
      let body: Record<string, unknown> = gasRetailResponse(config.url!, config.params);
      if (config.url?.endsWith('/marketers')) body = { ...gasRetailContext, metric: 'clients', scope: 'whole_market', total: 2, offset: 0, limit: 100, items: [0, 1].map((i) => ({ marketer_id: `gas-test-${i}`, company_name: 'Mismo nombre', observed_name: 'Mismo nombre', identity_status: 'reviewed_identity', identity_review_note: 'Empresa identificada de prueba.', source: { ...gasRetailSource, source_id: `document-${i}`, title: `Informe de prueba ${i}` }, mapping_review_note: '' })) } as typeof body;
      if (config.url?.includes('/series/')) body = { ...body, company_name: 'Mismo nombre', identity_status: 'reviewed_identity' } as typeof body;
      return { data: JSON.stringify(body), status: 200, statusText: 'OK', headers: {}, config };
    });
    const router = await open();
    fireEvent.focus(screen.getByRole('combobox', { name: 'Comercializadora observada' }));
    expect(screen.getAllByRole('option', { name: /Mismo nombre/ })).toHaveLength(2);
    choosePublished('Comercializadora observada', 'Mismo nombre · gas-test-1');
    expect(router.state.location.search).toContain('marketer=gas-test-1');
    expect(screen.getByRole('combobox', { name: 'Comercializadora observada' })).toHaveValue('Mismo nombre · gas-test-1');
  });
});
