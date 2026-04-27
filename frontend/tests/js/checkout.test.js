import { vi } from 'vitest';

const mocked = vi.hoisted(() => ({
  checkoutCart: vi.fn(),
  setPickupSlot: vi.fn(),
  submitOrder: vi.fn(),
}));

vi.mock('../../../static/js/api/order.js', () => ({
  checkoutCart: mocked.checkoutCart,
  setPickupSlot: mocked.setPickupSlot,
  submitOrder: mocked.submitOrder,
}));

describe('createCheckoutHandler', () => {
  beforeEach(() => {
    vi.resetModules();
    mocked.checkoutCart.mockReset();
    mocked.setPickupSlot.mockReset();
    mocked.submitOrder.mockReset();
  });

  it('redirige vers la page de paiement après soumission de commande', async () => {
    const { createCheckoutHandler } = await import('../../../static/js/pages/checkout.js');
    const checkoutButton = document.createElement('button');
    checkoutButton.textContent = 'Checkout';
    const payOnSiteButton = document.createElement('button');
    payOnSiteButton.textContent = 'Pay at truck';
    const checkoutHelp = document.createElement('div');
    const slotSelector = {
      getSelectedSlotId: () => '42',
    };
    const setCheckoutState = vi.fn();
    const assignSpy = vi.fn();
    const originalLocation = window.location;

    mocked.checkoutCart.mockResolvedValue({ order_id: 123 });
    mocked.setPickupSlot.mockResolvedValue({ status: 'ok' });
    mocked.submitOrder.mockResolvedValue({ status: 'ok' });

    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { assign: assignSpy },
    });

    try {
      const handler = createCheckoutHandler({
        slotSelector,
        checkoutButton,
        payOnSiteButton,
        checkoutHelp,
        refreshCart: vi.fn(),
        setCheckoutState,
        userAuthenticated: true,
        paymentCheckoutUrlTemplate: '/payments/checkout/0/',
        translations: {
          redirectingToPaymentMessage: 'Order submitted. Redirecting to payment...',
        },
      });

      await handler();

      expect(mocked.checkoutCart).toHaveBeenCalledTimes(1);
      expect(mocked.checkoutCart).toHaveBeenCalledWith(null, 'online');
      expect(mocked.setPickupSlot).toHaveBeenCalledWith(123, '42');
      expect(mocked.submitOrder).toHaveBeenCalledWith(123);
      expect(assignSpy).toHaveBeenCalledWith('/payments/checkout/123/');
      expect(checkoutHelp.textContent).toContain('Redirecting to payment');
      expect(setCheckoutState).not.toHaveBeenCalledWith(false, expect.any(String));
    } finally {
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: originalLocation,
      });
    }
  });

  it('soumet une commande avec paiement au foodtruck sans redirection', async () => {
    const { createCheckoutHandler } = await import('../../../static/js/pages/checkout.js');
    const checkoutButton = document.createElement('button');
    checkoutButton.textContent = 'Checkout';
    const payOnSiteButton = document.createElement('button');
    payOnSiteButton.textContent = 'Pay at truck';
    const checkoutHelp = document.createElement('div');
    const slotSelector = {
      getSelectedSlotId: () => '42',
    };
    const refreshCart = vi.fn().mockResolvedValue(undefined);

    mocked.checkoutCart.mockResolvedValue({ order_id: 321 });
    mocked.setPickupSlot.mockResolvedValue({ status: 'ok' });
    mocked.submitOrder.mockResolvedValue({ status: 'ok' });

    const handler = createCheckoutHandler({
      slotSelector,
      checkoutButton,
      payOnSiteButton,
      checkoutHelp,
      refreshCart,
      setCheckoutState: vi.fn(),
      userAuthenticated: true,
      paymentCheckoutUrlTemplate: '/payments/checkout/0/',
      translations: {
        payOnSiteSubmittedMessage: 'Order submitted. Pay at the food truck on pickup.',
      },
    });

    await handler('on_site', payOnSiteButton);

    expect(mocked.checkoutCart).toHaveBeenCalledWith(null, 'on_site');
    expect(mocked.setPickupSlot).toHaveBeenCalledWith(321, '42');
    expect(mocked.submitOrder).toHaveBeenCalledWith(321);
    expect(refreshCart).toHaveBeenCalledTimes(1);
    expect(checkoutHelp.textContent).toContain('Pay at the food truck on pickup');
  });
});