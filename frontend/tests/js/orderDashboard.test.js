import { fireEvent, waitFor } from '@testing-library/dom';
import { vi } from 'vitest';

function buildDashboardHtml() {
  return `
    <div
      id="order-dashboard"
      data-dashboard-url="/orders/api/dashboard/"
      data-status-url-template="/orders/api/0/status/"
      data-empty-message="No orders for this section."
      data-loading-message="Refreshing orders..."
      data-error-message="Unable to load orders right now."
      data-update-error-message="Unable to update this order."
      data-refresh-label="Refresh"
      data-confirm-label="Confirm order"
      data-cancel-label="Cancel order"
      data-start-preparing-label="Start preparing"
      data-mark-ready-label="Mark as ready"
      data-complete-label="Complete"
      data-urgent-label="Urgent pickup"
      data-order-label="Order">
      <select id="dashboard-status-filter">
        <option value="">All statuses</option>
        <option value="pending">Pending</option>
        <option value="confirmed">Confirmed</option>
      </select>
      <button id="dashboard-refresh-button" type="button">Refresh</button>
      <div id="dashboard-feedback" class="d-none"></div>
      <div id="dashboard-loading" class="d-none"></div>
      <div data-dashboard-section="pending">
        <span data-section-count>0</span>
        <div data-section-body></div>
      </div>
      <div data-dashboard-section="confirmed">
        <span data-section-count>0</span>
        <div data-section-body></div>
      </div>
      <div data-dashboard-section="preparing">
        <span data-section-count>0</span>
        <div data-section-body></div>
      </div>
      <div data-dashboard-section="ready">
        <span data-section-count>0</span>
        <div data-section-body></div>
      </div>
      <div data-dashboard-section="completed">
        <span data-section-count>0</span>
        <div data-section-body></div>
      </div>
    </div>
  `;
}

function createResponse(payload, ok = true) {
  return Promise.resolve({
    ok,
    json: async () => payload,
  });
}

describe('order dashboard module', () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = buildDashboardHtml();
    globalThis.fetch.mockReset();
  });

  it('charge les commandes au démarrage et les rend dans la bonne colonne', async () => {
    globalThis.fetch.mockImplementation(() => createResponse([
      {
        id: 12,
        status: 'pending',
        pickup_time: '2026-04-11T10:00:00.000Z',
        total_price: '25.00',
        items: [{ item_name: 'Burger', quantity: 2, total_price: '25.00', selected_options: [{ name: 'Cheddar' }, { name: 'Pickles' }] }],
      },
    ]));

    await import('../../../static/orders/js/dashboard.js');

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(document.querySelector('[data-order-id="12"]')).not.toBeNull());
    expect(document.querySelector('[data-dashboard-section="pending"] [data-section-count]').textContent).toBe('1');
    expect(document.body.textContent).toContain('Burger');
    expect(document.body.textContent).toContain('x2');
    expect(document.body.textContent).toContain('Cheddar');
    expect(document.body.textContent).toContain('Pickles');
  });

  it('envoie la transition de statut puis rafraîchit le dashboard', async () => {
    globalThis.fetch
      .mockImplementationOnce(() => createResponse([
        {
          id: 12,
          status: 'pending',
          pickup_time: '2026-04-11T10:00:00.000Z',
          total_price: '25.00',
          items: [{ item_name: 'Burger', quantity: 2, total_price: '25.00', selected_options: [{ name: 'Cheddar' }] }],
        },
      ]))
      .mockImplementationOnce(() => createResponse({
        id: 12,
        status: 'confirmed',
        pickup_time: '2026-04-11T10:00:00.000Z',
        total_price: '25.00',
        items: [{ item_name: 'Burger', quantity: 2, total_price: '25.00', selected_options: [{ name: 'Cheddar' }] }],
      }))
      .mockImplementationOnce(() => createResponse([
        {
          id: 12,
          status: 'confirmed',
          pickup_time: '2026-04-11T10:00:00.000Z',
          total_price: '25.00',
          items: [{ item_name: 'Burger', quantity: 2, total_price: '25.00', selected_options: [{ name: 'Cheddar' }] }],
        },
      ]));

    await import('../../../static/orders/js/dashboard.js');

    await waitFor(() => expect(document.querySelector('.js-order-status')).not.toBeNull());
    fireEvent.click(document.querySelector('.js-order-status'));

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(3));
    const updateCall = globalThis.fetch.mock.calls[1];
    expect(updateCall[0]).toContain('/orders/api/12/status/');
    expect(updateCall[1].method).toBe('POST');
    expect(updateCall[1].body).toBe(JSON.stringify({ status: 'confirmed' }));
    await waitFor(() => expect(document.querySelector('[data-dashboard-section="confirmed"] [data-section-count]').textContent).toBe('1'));
  });

  it('applique le filtre de statut aux requêtes de rafraîchissement', async () => {
    globalThis.fetch
      .mockImplementationOnce(() => createResponse([]))
      .mockImplementationOnce(() => createResponse([]));

    await import('../../../static/orders/js/dashboard.js');

    const filter = document.getElementById('dashboard-status-filter');
    fireEvent.change(filter, { target: { value: 'confirmed' } });

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(2));
    expect(globalThis.fetch.mock.calls[1][0]).toContain('status=confirmed');
  });
});