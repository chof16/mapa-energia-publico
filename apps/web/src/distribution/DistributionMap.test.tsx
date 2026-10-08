import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { territoryLabels } from '../test/fixtures/territory-labels';
import { MapBoundary } from '../test/maplibre-boundary';
import { marketResponse } from '../test/fixtures/market';
import { choosePublished, network, mockProvinceResponse, provinceResponse, provinceSummaryResponse, renderExplorer as renderHome } from '../test/exploration-route-fixture';

vi.mock('maplibre-gl', async () => {
  const { MapBoundary } = await import('../test/maplibre-boundary');
  return {
    Map: MapBoundary,
    NavigationControl: class {},
    AttributionControl: class {},
    addProtocol: vi.fn(),
  };
});

describe('documented distribution map route', () => {
  it('loads the map summary once without querying provincial detail for Spain or a community', async () => {
    mockProvinceResponse();
    const { router } = await renderHome();
    expect(screen.getByText(/El mapa marca provincias con presencias documentadas/)).toBeVisible();
    await waitFor(() => expect(network.mock.calls.some(([config]) => config.url?.endsWith('/v1/distribution/provinces'))).toBe(true));
    expect(network.mock.calls.some(([config]) => config.url?.includes('/v1/distribution/provinces/'))).toBe(false);
    await act(() => router.navigate('/?autonomous_community=13'));
    expect(screen.getByText(/No hay una cobertura completa para toda la comunidad/)).toBeVisible();
    expect(network.mock.calls.filter(([config]) => config.url?.endsWith('/v1/distribution/provinces'))).toHaveLength(1);
    expect(network.mock.calls.some(([config]) => config.url?.includes('/v1/distribution/provinces/'))).toBe(false);
  });

  it('paints only documented provincial presence and hides it for quotas and gas', async () => {
    mockProvinceResponse();
    const { router } = await renderHome('/?period=2025T4');
    const main = MapBoundary.instances.find((map) => map.options.cooperativeGestures)!;
    await waitFor(() => expect(main.setLayoutProperty).toHaveBeenCalledWith('distribution-fill', 'visibility', 'visible'));
    expect(main.layers.get('distribution-fill')).toMatchObject({
      'source-layer': 'provincias', minzoom: 0, maxzoom: 8.2,
    });
    expect(main.setPaintProperty).toHaveBeenCalledWith('distribution-fill', 'fill-color', [
      'case', ['boolean', ['feature-state', 'selected'], false], '#b9d5ef',
      ['match', ['get', 'cpro'], '24', '#4c9276', '28', '#4c9276', '46', '#a7d6c4', '#e5ebef'],
    ]);
    expect(screen.getByText('Sin evidencia (desconocido)')).toBeVisible();
    expect(screen.getByText(/no cobertura completa ni municipal/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Cuota comercializadora' }));
    expect(main.setLayoutProperty.mock.calls.filter(([id]) => id === 'distribution-fill').at(-1)).toEqual(['distribution-fill', 'visibility', 'none']);
    await act(() => router.navigate('/?sector=gas&map_layer=distribution'));
    expect(main.setLayoutProperty.mock.calls.filter(([id]) => id === 'distribution-fill').at(-1)).toEqual(['distribution-fill', 'visibility', 'none']);
    expect(network.mock.calls.filter(([config]) => config.url?.endsWith('/v1/distribution/provinces'))).toHaveLength(1);
  });

  it('requests presence after choosing a province, and only in the exploration layer', async () => {
    mockProvinceResponse();
    const { router } = await renderHome('/?map_layer=market&autonomous_community=13');
    expect(network.mock.calls.some(([config]) => config.url?.includes('/v1/distribution/'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Explorar zonas' }));
    choosePublished('Provincia', '28');
    expect(await screen.findByText('Presencia en una parte de Madrid.')).toBeVisible();
    expect(new URLSearchParams(router.state.location.search).get('province')).toBe('28');
    expect(network.mock.calls.filter(([config]) => config.url?.endsWith('/v1/distribution/provinces/28'))).toHaveLength(1);
  });

  it('shows sourced positive provincial evidence and keeps its limits when selecting a municipality or using history', async () => {
    mockProvinceResponse();
    const { router } = await renderHome('/?autonomous_community=13&province=28&campaign=shared');
    const panel = await screen.findByRole('complementary', { name: 'Evidencia de distribuidoras en Madrid' });
    expect(panel).toHaveTextContent('Distribuidora de prueba · R1-001');
    expect(panel).toHaveTextContent('Grupo empresarial: Grupo Iberdrola');
    expect(panel).toHaveTextContent('Iberdrola identifica a esta distribuidora como filial.');
    expect(within(panel).getByRole('link', { name: 'Fuente del grupo empresarial de Distribuidora de prueba' })).toHaveAttribute('href', 'https://www.iberdrola.com/gobierno-corporativo/estructura');
    expect(panel).toHaveTextContent('Presencia en una parte de Madrid.');
    expect(panel).toHaveTextContent('Documento oficial');
    expect(panel).toHaveTextContent('29 de enero de 2026');
    expect(panel).toHaveTextContent('3 de octubre de 2026');
    expect(within(panel).getByRole('link', { name: 'Fuente geográfica de prueba' })).toHaveAttribute('href', 'https://www.boe.es/zona');
    expect(within(panel).getByRole('link', { name: /Fuente del código/ })).toHaveAttribute('href', 'https://www.boe.es/registro');
    expect(panel).toHaveTextContent('Basado en datos de la Agencia Estatal Boletín Oficial del Estado');
    expect(panel).toHaveTextContent('Síntesis elaborada por este proyecto');
    expect(panel).toHaveTextContent(/no indica ausencia de otras distribuidoras, exclusividad ni cobertura de toda la provincia/);
    expect(panel).toHaveTextContent('El grupo empresarial no identifica una COR ni añade cobertura.');
    expect(network).toHaveBeenCalledWith(expect.objectContaining({ url: '/v1/distribution/provinces/28', params: { sector: 'electricity' } }));
    expect(router.state.location.search).toBe('?autonomous_community=13&province=28&campaign=shared');
    await act(() => router.navigate('/?autonomous_community=13&province=28&municipality=28079&campaign=shared'));
    expect(panel).toHaveTextContent('no prueba cobertura en ese municipio');
    await act(() => router.navigate(-1));
    expect(panel).not.toHaveTextContent('no prueba cobertura en ese municipio');
  });

  it('treats an empty incomplete provincial response as unknown', async () => {
    mockProvinceResponse({ ...provinceResponse, items: [] });
    await renderHome('/?province=28');
    expect(await screen.findByText(/Cobertura desconocida en esta provincia/)).toBeVisible();
    expect(screen.queryByText('No hay distribuidoras')).not.toBeInTheDocument();
  });

  it.each([
    ['Ceuta', '18', '51', '030'],
    ['Melilla', '19', '52', '027'],
  ])('renders all seven synthetic presences in %s, including a local operator without a group', async (city, community, province, localCode) => {
    // Synthetic names, geometry and co-presence: exercise the UI, not actual coverage.
    const labels = {
      ...territoryLabels,
      features: territoryLabels.features.slice(0, 3).map((feature, index) => ({
        ...feature,
        properties: {
          ...feature.properties, nombre: city, ccaa_ine: community,
          cpro: index === 0 ? null : province,
          ine_municipio: index === 2 ? `${province}001` : null,
        },
      })),
    };
    const items = [...['101', '102', '103', '104', '105', '106'], localCode].map((code) => ({
      ...provinceResponse.items[0], distributor_code: `R1-${code}`,
      distributor_name: `Distribuidora local de prueba con un nombre registral largo de ${city} ${code}`,
      corporate_group: null,
      evidence: { ...provinceResponse.items[0].evidence, geographic_claim: `Presencia parcial sintética en ${city}.` },
    }));
    network.mockImplementation(async (config) => ({
      data: JSON.stringify(config.url?.endsWith('/v1/distribution/provinces')
        ? { ...provinceSummaryResponse, items: [{ province_code: province, documented_distributor_count: 7 }] }
        : config.url?.includes('/v1/distribution/')
          ? { ...provinceResponse, province_code: province, items }
          : config.url?.includes('/v1/market/') ? marketResponse(config.url, config.params) : labels),
      status: 200, statusText: 'OK', headers: {}, config,
    }));
    const { router } = await renderHome(`/?province=${province}`);
    const panel = await screen.findByRole('complementary', { name: `Evidencia de distribuidoras en ${city}` });
    await waitFor(() => expect(within(panel).getAllByRole('listitem')).toHaveLength(7));
    expect(within(panel).getAllByRole('heading', { level: 3 }).at(-1)).toHaveTextContent(`· R1-${localCode}`);
    expect(within(panel).getAllByRole('link', { name: 'Fuente geográfica de prueba' })).toHaveLength(7);
    expect(panel).not.toHaveTextContent('Grupo empresarial:');
    expect(panel).toHaveTextContent('Lista incompleta: no indica ausencia de otras distribuidoras');
    const main = MapBoundary.instances.find((map) => map.options.cooperativeGestures)!;
    await waitFor(() => expect(main.setPaintProperty).toHaveBeenCalledWith('distribution-fill', 'fill-color', [
      'case', ['boolean', ['feature-state', 'selected'], false], '#b9d5ef',
      ['match', ['get', 'cpro'], province, '#4c9276', '#e5ebef'],
    ]));
    expect(screen.getByText('Sin evidencia (desconocido)')).toBeVisible();
    await act(() => router.navigate(`/?province=${province}&municipality=${province}001`));
    expect(panel).toHaveTextContent(`Has seleccionado ${city}. Esta evidencia es provincial y no prueba cobertura en ese municipio.`);
    expect(within(panel).getAllByRole('listitem')).toHaveLength(7);
  });

  it('keeps Endesa as the geographic source and attributes only the BOE registry data to BOE', async () => {
    mockProvinceResponse({
      ...provinceResponse,
      items: [{
        ...provinceResponse.items[0],
        evidence: {
          ...provinceResponse.items[0].evidence,
          source_title: 'Artículo de Endesa',
          source_url: 'https://www.endesa.com/es/articulo',
          confidence: 'other_operator_reported',
        },
      }],
    });
    await renderHome('/?province=28');
    const panel = await screen.findByRole('complementary', { name: 'Evidencia de distribuidoras en Madrid' });
    await waitFor(() => expect(within(panel).getByRole('link', { name: 'Artículo de Endesa' })).toBeVisible());
    expect(panel).toHaveTextContent('Código y nombre R1: Basado en datos de la Agencia Estatal Boletín Oficial del Estado');
    expect(panel).not.toHaveTextContent('Afirmación geográfica y datos registrales:');
  });

  it('offers a retry after invalid provincial data and recovers without leaving the selection', async () => {
    let invalid = true;
    network.mockImplementation(async (config) => ({
      data: JSON.stringify(config.url?.includes('/v1/distribution/')
        ? { ...provinceResponse, complete: invalid }
        : config.url?.includes('/v1/market/')
          ? marketResponse(config.url, config.params)
          : territoryLabels),
      status: 200, statusText: 'OK', headers: {}, config,
    }));
    const { router } = await renderHome('/?province=28');
    const retry = await screen.findByRole('button', { name: 'Reintentar evidencia' });
    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo cargar o validar');
    invalid = false;
    fireEvent.click(retry);
    expect(await screen.findByText('Presencia en una parte de Madrid.')).toBeVisible();
    expect(new URLSearchParams(router.state.location.search).get('province')).toBe('28');
  });

  it('keeps gas pending and does not request electrical presence there', async () => {
    mockProvinceResponse();
    await renderHome('/?sector=gas&province=28');
    expect(screen.queryByRole('complementary', { name: /Evidencia de distribuidoras/ })).not.toBeInTheDocument();
    expect(network.mock.calls.some(([config]) => config.url?.includes('/v1/distribution/'))).toBe(false);
  });
});
