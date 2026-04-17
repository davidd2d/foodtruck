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
});