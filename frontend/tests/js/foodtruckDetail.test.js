import { fireEvent, waitFor } from '@testing-library/dom';
import { vi } from 'vitest';

const mocked = vi.hoisted(() => ({
  fetchFoodtruckMenu: vi.fn(),
  fetchCart: vi.fn(),
  addCartItem: vi.fn(),
  removeCartItem: vi.fn(),
  fetchPickupSlots: vi.fn(),
  createCheckoutHandler: vi.fn(() => vi.fn()),
}));

vi.mock('../../../static/js/api/menu.js', () => ({
  fetchFoodtruckMenu: mocked.fetchFoodtruckMenu,
}));

vi.mock('../../../static/js/api/cart.js', () => ({
  fetchCart: mocked.fetchCart,
  addCartItem: mocked.addCartItem,
  removeCartItem: mocked.removeCartItem,
}));

vi.mock('../../../static/js/api/slots.js', () => ({
  fetchPickupSlots: mocked.fetchPickupSlots,
}));

vi.mock('../../../static/js/pages/checkout.js', () => ({
  createCheckoutHandler: mocked.createCheckoutHandler,
}));

const sampleMenu = {
  categories: [
    {
      id: 1,
      name: 'Pasta Box',
      items: [
        {
          id: 10,
          name: 'Sauce Pesto Roquette',
          description: 'Roquette - parmesan - amande - ail',
          base_price: '7.90',
          option_groups: [
            {
              id: 201,
              name: 'AI Free Customizations',
              required: true,
              min_choices: 1,
              max_choices: 2,
              options: [
                { id: 301, name: 'Chili flakes', price_modifier: '0.00' },
                { id: 302, name: 'Extra parmesan sprinkle', price_modifier: '0.00' },
              ],
            },
          ],
        },
      ],
      combos: [],
    },
  ],
};

function buildPageHtml({ authenticated }) {
  return `
    <div
      data-foodtruck-slug="cucina-di-pastaz"
      data-user-authenticated="${authenticated ? 'true' : 'false'}"
      data-ordering-enabled="true"
      data-login-url="/accounts/login/"
      data-register-url="/accounts/register/"
      data-loading-menu-message="Loading menu..."
      data-empty-menu-message="No menu items are available right now."
      data-empty-menu-hint="Please check back later."
      data-cart-count-label="Cart ({count})"
      data-login-checkout-message="Log in to submit your order."
      data-cart-checkout-message="Add items to your cart to checkout."
      data-cart-continue-message="Add items to your cart to continue."
      data-no-slots-message="No pickup slots are currently available."
      data-select-slot-message="Select a pickup slot before checkout."
      data-load-slots-error-message="Unable to load pickup slots."
      data-load-cart-error-message="Unable to load cart."
      data-missing-foodtruck-message="Could not identify foodtruck."
      data-load-menu-error-message="Unable to load menu."
      data-add-to-cart-label="Add to cart"
      data-adding-label="Adding..."
      data-add-to-cart-error-message="Unable to add item to cart."
      data-combo-label="Combo"
      data-option-label-prefix="Option"
      data-no-extras-selected="No extras selected"
      data-quantity-short-label="Qty"
      data-each-label="each"
      data-remove-label="Remove"
      data-cart-empty-message="Your cart is empty."
      data-price-to-confirm-label="Price to confirm"
      data-add-combo-label="Add combo"
      data-combo-badge-label="Combo"
      data-required-label="Required"
      data-optional-label="Optional"
      data-min-label="min"
      data-max-label="max"
      data-price-label="Price"
      data-quantity-label="Quantity"
      data-items-count-label="{count} items"
      data-recommended-pickup-message="Recommended pickup time selected automatically."
      data-pickup-now-message="Recommended pickup: right now"
      data-next-pickup-message="Next available slot: {time}"
      data-choose-pickup-slot-label="Choose a pickup slot"
      data-unavailable-suffix="unavailable"
      data-loading-slots-label="Loading available slots..."
      data-no-slots-option-label="No pickup slots available."
      data-load-slots-error-label="Unable to load pickup slots."
      data-customize-item-title="Customize {item}"
      data-add-item-to-cart-label="Add item to cart"
      data-no-customization-options-message="No customization options for this item."
      data-select-at-least-options-message="Please choose at least {count} option(s) for {group}."
      data-select-at-most-options-message="You can select up to {count} option(s) for {group}.">
      <div id="category-shortcuts"></div>
      <div id="menu-container"></div>
      <a id="nav-cart-count"></a>
      <div id="cart-loading"></div>
      <div id="cart-empty" class="d-none"></div>
      <div id="cart-content" class="d-none"></div>
      <div id="cart-items"></div>
      <div id="cart-total"></div>
      <button id="checkout-button">Checkout</button>
      <div id="checkout-help" class="d-none"></div>
      <select id="pickup-slot-select"></select>
      <div id="pickup-slot-help"></div>
    </div>
    <div class="modal" id="itemOrderModal">
      <form id="item-order-form">
        <h5 id="itemOrderModalLabel"></h5>
        <div id="item-order-error" class="d-none"></div>
        <p id="item-order-description" class="d-none"></p>
        <div id="item-order-options"></div>
        <input id="item-order-quantity" type="number" value="1" min="1">
        <button id="item-order-submit" type="submit">Add item to cart</button>
      </form>
    </div>
    <div class="modal" id="authRequiredModal">
      <a id="auth-required-login" href="/accounts/login/">Log in</a>
      <a id="auth-required-register" href="/accounts/register/">Create account</a>
    </div>
  `;
}

describe('foodtruckDetail ordering flow', () => {
  let modalInstances;

  beforeEach(() => {
    vi.resetModules();
    modalInstances = new Map();
    mocked.fetchFoodtruckMenu.mockReset();
    mocked.fetchCart.mockReset();
    mocked.addCartItem.mockReset();
    mocked.removeCartItem.mockReset();
    mocked.fetchPickupSlots.mockReset();
    mocked.createCheckoutHandler.mockReset();
    globalThis.bootstrap = {
      Modal: class {
        constructor(element) {
          this.element = element;
          this.show = vi.fn();
          this.hide = vi.fn();
          modalInstances.set(element.id, this);
        }
      },
    };

    mocked.fetchFoodtruckMenu.mockResolvedValue(sampleMenu);
    mocked.fetchCart.mockResolvedValue({ items: [], total_price: '0.00', item_count: 0 });
    mocked.fetchPickupSlots.mockResolvedValue([]);
    mocked.addCartItem.mockResolvedValue({ items: [], total_price: '0.00', item_count: 1 });
    mocked.removeCartItem.mockResolvedValue({ items: [], total_price: '0.00', item_count: 0 });
    mocked.createCheckoutHandler.mockReturnValue(vi.fn());
  });

  it('cache les options dans la carte et ouvre le modal de connexion pour un invité', async () => {
    document.body.innerHTML = buildPageHtml({ authenticated: false });

    await import('../../../static/js/pages/foodtruckDetail.js');

    await waitFor(() => expect(document.querySelector('.menu-item .add-to-cart')).not.toBeNull());
    await waitFor(() => expect(modalInstances.has('authRequiredModal')).toBe(true));
    const itemCard = document.querySelector('.menu-item');
    expect(itemCard.querySelector('.menu-option')).toBeNull();

    fireEvent.click(itemCard.querySelector('.add-to-cart'));

    expect(modalInstances.get('authRequiredModal').show).toHaveBeenCalledTimes(1);
    expect(mocked.addCartItem).not.toHaveBeenCalled();
    expect(document.getElementById('auth-required-login').getAttribute('href')).toContain('next=%2F');
  });

  it('ouvre le modal d’options puis ajoute l’item avec quantité et options sélectionnées', async () => {
    document.body.innerHTML = buildPageHtml({ authenticated: true });

    await import('../../../static/js/pages/foodtruckDetail.js');

    await waitFor(() => expect(document.querySelector('.menu-item .add-to-cart')).not.toBeNull());
    await waitFor(() => expect(modalInstances.has('itemOrderModal')).toBe(true));
    fireEvent.click(document.querySelector('.menu-item .add-to-cart'));

    expect(modalInstances.get('itemOrderModal').show).toHaveBeenCalledTimes(1);
    expect(document.getElementById('item-order-options').textContent).toContain('AI Free Customizations');

    const firstOption = document.querySelector('#item-order-options .menu-option');
    fireEvent.click(firstOption);
    fireEvent.change(document.getElementById('item-order-quantity'), { target: { value: '2' } });
    fireEvent.submit(document.getElementById('item-order-form'));

    await waitFor(() => expect(mocked.addCartItem).toHaveBeenCalledTimes(1));
    expect(mocked.addCartItem).toHaveBeenCalledWith({
      foodtruck_slug: 'cucina-di-pastaz',
      item_id: 10,
      quantity: 2,
      selected_options: [301],
    });
    await waitFor(() => expect(modalInstances.get('itemOrderModal').hide).toHaveBeenCalledTimes(1));
  });

  it('bloque la soumission du modal si une option requise manque', async () => {
    document.body.innerHTML = buildPageHtml({ authenticated: true });

    await import('../../../static/js/pages/foodtruckDetail.js');

    await waitFor(() => expect(document.querySelector('.menu-item .add-to-cart')).not.toBeNull());
    await waitFor(() => expect(modalInstances.has('itemOrderModal')).toBe(true));
    fireEvent.click(document.querySelector('.menu-item .add-to-cart'));
    fireEvent.submit(document.getElementById('item-order-form'));

    expect(mocked.addCartItem).not.toHaveBeenCalled();
    expect(document.getElementById('item-order-error').textContent).toContain('Please choose at least 1 option(s) for AI Free Customizations.');
  });
});