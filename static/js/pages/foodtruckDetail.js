import { fetchFoodtruckMenu } from '../api/menu.js';
import { fetchCart, addCartItem, removeCartItem } from '../api/cart.js';
import { fetchPickupSlots } from '../api/slots.js';
import { renderCategory } from '../components/menuItem.js';
import { renderCart } from '../components/cart.js';
import { SlotSelector } from '../components/slotSelector.js';
import { createCheckoutHandler } from '../pages/checkout.js';

const menuContainer = document.getElementById('menu-container');
const cartItemsContainer = document.getElementById('cart-items');
const cartTotalElement = document.getElementById('cart-total');
const cartContent = document.getElementById('cart-content');
const cartEmpty = document.getElementById('cart-empty');
const cartLoading = document.getElementById('cart-loading');
const navCartCount = document.getElementById('nav-cart-count');
const checkoutButton = document.getElementById('checkout-button');
const checkoutHelp = document.getElementById('checkout-help');
const pickupSlotSelect = document.getElementById('pickup-slot-select');
const pickupSlotHelp = document.getElementById('pickup-slot-help');
const pageContainer = document.querySelector('[data-foodtruck-slug]');
const foodtruckSlug = pageContainer?.dataset.foodtruckSlug;
const userAuthenticated = pageContainer?.dataset.userAuthenticated === 'true';
let slotSelector = null;

function createLoadingState() {
    menuContainer.innerHTML = `
        <div class="text-center text-muted py-5">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-3 mb-0">Loading menu...</p>
        </div>
    `;
}

function renderMenu(menu) {
    if (!menu.categories.length) {
        menuContainer.innerHTML = `
            <div class="text-center text-muted py-5">
                <p class="mb-2">No menu items are available right now.</p>
                <p class="small">Please check back later.</p>
            </div>
        `;
        return;
    }

    menuContainer.innerHTML = menu.categories
        .map((category, index) => renderCategory(category, index * 10))
        .join('');
}

function updateCartUI(cart) {
    cartLoading.classList.add('d-none');

    if (!cart || cart.items.length === 0) {
        cartContent.classList.add('d-none');
        cartEmpty.classList.remove('d-none');
        if (navCartCount) {
            navCartCount.textContent = 'Cart (0)';
        }
        return;
    }

    const rendered = renderCart(cart);
    cartContent.classList.remove('d-none');
    cartEmpty.classList.add('d-none');
    cartItemsContainer.innerHTML = rendered.markup;
    cartTotalElement.textContent = `€${rendered.total}`;

    if (navCartCount) {
        navCartCount.textContent = `Cart (${rendered.itemCount})`;
    }
}

function renderError(message) {
    menuContainer.innerHTML = `
        <div class="alert alert-danger" role="alert">
            ${message}
        </div>
    `;
}

function setCheckoutState(enabled, message = null) {
    if (!checkoutButton) {
        return;
    }

    checkoutButton.disabled = !enabled || !userAuthenticated;

    if (!userAuthenticated) {
        checkoutHelp.classList.remove('d-none');
        checkoutHelp.textContent = 'Log in to submit your order.';
        return;
    }

    if (!enabled) {
        checkoutHelp.classList.remove('d-none');
        checkoutHelp.textContent = message || 'Add items to your cart to checkout.';
        return;
    }

    checkoutHelp.classList.add('d-none');
}

async function handleCartUpdate(cart) {
    updateCartUI(cart);
    await updateSlotSelector(cart);
}

async function updateSlotSelector(cart) {
    if (!slotSelector) {
        return;
    }

    if (!cart || cart.items.length === 0) {
        slotSelector.reset('Add items to your cart to continue.');
        setCheckoutState(false, 'Add items to your cart to continue.');
        return;
    }

    try {
        const slots = await slotSelector.loadSlots(fetchPickupSlots, foodtruckSlug);
        if (!slots.length) {
            setCheckoutState(false, 'No pickup slots are currently available.');
            return;
        }
        setCheckoutState(false, 'Select a pickup slot before checkout.');
    } catch (error) {
        setCheckoutState(false, 'Unable to load pickup slots.');
        console.error(error);
    }
}

function handleSlotSelection(slotId) {
    if (!slotId) {
        setCheckoutState(false, 'Select a pickup slot before checkout.');
        return;
    }

    setCheckoutState(true);
    checkoutHelp?.classList.add('d-none');
}

function initializeSlotSelector() {
    if (!pickupSlotSelect) {
        return;
    }

    slotSelector = new SlotSelector({
        selectElement: pickupSlotSelect,
        helpElement: pickupSlotHelp,
        onSelectionChange: handleSlotSelection,
    });
}

function initializeCheckoutFlow() {
    if (!checkoutButton || !slotSelector) {
        return;
    }

    const handler = createCheckoutHandler({
        slotSelector,
        checkoutButton,
        checkoutHelp,
        refreshCart,
        setCheckoutState,
        userAuthenticated,
    });

    checkoutButton.addEventListener('click', handler);
}

async function refreshCart() {
    try {
        const cart = await fetchCart();
        await handleCartUpdate(cart);
    } catch (error) {
        cartLoading.classList.add('d-none');
        cartEmpty.classList.remove('d-none');
        cartEmpty.innerHTML = `<p class="text-danger">Unable to load cart.</p>`;
        console.error(error);
    }
}

async function initializeMenu() {
    if (!foodtruckSlug) {
        renderError('Could not identify foodtruck.');
        return;
    }

    createLoadingState();

    try {
        const menu = await fetchFoodtruckMenu(foodtruckSlug);
        renderMenu(menu);
    } catch (error) {
        renderError(error.message || 'Unable to load menu.');
    }
}

async function handleAddToCart(event) {
    const button = event.target.closest('.add-to-cart');
    if (!button) {
        return;
    }

    const itemCard = button.closest('.menu-item');
    const itemId = Number(button.dataset.itemId);
    const quantityField = itemCard.querySelector('.menu-item-quantity');
    const quantity = Math.max(1, Number(quantityField?.value || 1));
    const selectedOptions = Array.from(itemCard.querySelectorAll('.menu-option:checked')).map((input) => Number(input.dataset.optionId));

    button.disabled = true;
    button.textContent = 'Adding...';

    try {
        const cart = await addCartItem({
            foodtruck_slug: foodtruckSlug,
            item_id: itemId,
            quantity,
            selected_options: selectedOptions,
        });
        await handleCartUpdate(cart);
    } catch (error) {
        renderError(error.message || 'Unable to add item to cart.');
        console.error(error);
    } finally {
        button.disabled = false;
        button.textContent = 'Add to cart';
    }
}

async function handleRemoveFromCart(event) {
    const button = event.target.closest('.cart-remove');
    if (!button) {
        return;
    }

    const lineKey = button.dataset.lineKey;
    if (!lineKey) {
        return;
    }

    button.disabled = true;

    try {
        const cart = await removeCartItem(lineKey);
        await handleCartUpdate(cart);
    } catch (error) {
        console.error(error);
    } finally {
        button.disabled = false;
    }
}

function wireEvents() {
    menuContainer.addEventListener('click', handleAddToCart);
    cartItemsContainer.addEventListener('click', handleRemoveFromCart);
}

async function bootstrap() {
    initializeSlotSelector();
    initializeCheckoutFlow();
    wireEvents();
    await initializeMenu();
    await refreshCart();
}

bootstrap();
