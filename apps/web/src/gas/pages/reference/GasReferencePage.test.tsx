import { fireEvent, screen, within } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { appRoutes } from '../../../app.router';
import { network, renderRoute } from '../../../test/exploration-route-fixture';
import { gasRetailResponse } from '../../../test/fixtures/gas-retail';

function open() { const router = createMemoryRouter(appRoutes, { initialEntries: ['/regulated-tariff?sector=gas&marketer=R2-001&province=28'] }); renderRoute(router); return router; }
describe('gas CUR catalogue', () => {
  it('shows four independent entities, dated variants and source links without electricity codes or prices', async () => {
    const router = open();
    expect(await screen.findByRole('heading', { name: 'Catálogo con evidencia fechada' })).toBeVisible();
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    expect(screen.getByText(/Esta página no publica precios/)).toBeVisible();
    const details = screen.getAllByText('Denominaciones observadas, fechas y fuentes')[0];
    fireEvent.click(details);
    expect(screen.getByRole('heading', { name: 'CUR sintética 0' })).toBeVisible();
    expect(screen.getAllByText('2022-11-14')[0]).toBeVisible();
    expect(screen.getAllByText('Sin fecha de publicación declarada.', { exact: false })[0]).toBeVisible();
    expect(router.state.location.search).toBe('?sector=gas');
    expect(network.mock.calls.every(([c]) => c.url?.endsWith('/v1/gas/reference-marketers'))).toBe(true);
  });
  it('shows a loading state followed by retryable failure', async () => {
    let reject: (error: Error) => void = () => {};
    network.mockImplementationOnce(() => new Promise((_, fail) => { reject = fail; }));
    open();
    expect(screen.getByText('Cargando catálogo de último recurso…')).toBeVisible();
    reject(new Error('offline'));
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar el catálogo de gas');
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByRole('heading', { name: 'Catálogo con evidencia fechada' })).toBeVisible();
  });
  it('opens company and source disclosures independently and restores their collapsed states', async () => {
    open();
    await screen.findByRole('heading', { name: 'Catálogo con evidencia fechada' });
    const entries = screen.getAllByRole('listitem');
    const first = entries[0].querySelector('details')!;
    const second = entries[1].querySelector('details')!;
    fireEvent.click(within(entries[0]).getByText('Denominaciones observadas, fechas y fuentes'));
    expect(first).toHaveAttribute('open');
    expect(second).not.toHaveAttribute('open');
    const source = within(entries[0]).getAllByText('Identificación de la fuente')[0];
    fireEvent.click(source);
    expect(source.closest('details')).toHaveAttribute('open');
    expect(within(entries[0]).getAllByText(/SHA-256/)[0]).toBeVisible();
    fireEvent.click(within(entries[1]).getByText('Denominaciones observadas, fechas y fuentes'));
    expect(second).toHaveAttribute('open');
    expect(first).toHaveAttribute('open');
    fireEvent.click(source);
    expect(source.closest('details')).not.toHaveAttribute('open');
    expect(first).toHaveAttribute('open');
    fireEvent.click(within(entries[0]).getByText('Denominaciones observadas, fechas y fuentes'));
    expect(first).not.toHaveAttribute('open');
    expect(second).toHaveAttribute('open');
  });
  it('shows an empty catalogue without inventing the four expected entries', async () => {
    network.mockImplementation(async (config) => ({ data: JSON.stringify({ ...gasRetailResponse(config.url!, config.params), total: 0, items: [] }), status: 200, statusText: 'OK', headers: {}, config }));
    open();
    expect(await screen.findByRole('heading', { name: 'Sin entradas publicadas' })).toBeVisible();
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
  });
});
