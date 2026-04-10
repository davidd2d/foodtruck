import { fetchFoodtruckMenu } from '../api/menu.js';
import { fetchCart, addCartItem, removeCartItem } from '../api/cart.js';
import { fetchPickupSlots } from '../api/slots.js';
import { renderCategory } from '../components/menuItem.js';
import { renderCart } from '../components/cart.js';
import { SlotSelector } from '../components/slotSelector.js';
import { createCheckoutHandler } from '../pages/checkout.js';
import { getDatasetTranslations, interpolate } from '../i18n.js';

const pageContainer = document.querySelector('[data-foodtruck-slug]');
const foodtruckSlug = pageContainer?.dataset.foodtruckSlug;
const userAuthenticated = pageContainer?.dataset.userAuthenticated === 'true';
const orderingEnabled = pageContainer?.dataset.orderingEnabled === 'true';

const menuContainer = document.getElementById('menu-container');
const categoryShortcuts = document.getElementById('category-shortcuts');
const cartItemsContainer = orderingEnabled ? document.getElementById('cart-items') : null;
const cartTotalElement = orderingEnabled ? document.getElementById('cart-total') : null;
const cartContent = orderingEnabled ? document.getElementById('cart-content') : null;
const cartEmpty = orderingEnabled ? document.getElementById('cart-empty') : null;
const cartLoading = orderingEnabled ? document.getElementById('cart-loading') : null;
const navCartCount = orderingEnabled ? document.getElementById('nav-cart-count') : null;
const checkoutButton = orderingEnabled ? document.getElementById('checkout-button') : null;
const checkoutHelp = orderingEnabled ? document.getElementById('checkout-help') : null;
const pickupSlotSelect = orderingEnabled ? document.getElementById('pickup-slot-select') : null;
const pickupSlotHelp = orderingEnabled ? document.getElementById('pickup-slot-help') : null;
let slotSelector = null;
let menuLoaded = false;
let menuLoadTimeout = null;
const MENU_LOAD_TIMEOUT_MS = 6000;
const translations = getDatasetTranslations(pageContainer, {
    loadingMenuMessage: 'Loading menu...',
    emptyMenuMessage: 'No menu items are available right now.',
    emptyMenuHint: 'Please check back later.',
    cartCountLabel: 'Cart ({count})',
    loginCheckoutMessage: 'Log in to submit your order.',
    cartCheckoutMessage: 'Add items to your cart to checkout.',
    cartContinueMessage: 'Add items to your cart to continue.',
    noSlotsMessage: 'No pickup slots are currently available.',
    selectSlotMessage: 'Select a pickup slot before checkout.',
    loadSlotsErrorMessage: 'Unable to load pickup slots.',
    loadCartErrorMessage: 'Unable to load cart.',
    missingFoodtruckMessage: 'Could not identify foodtruck.',
    loadMenuErrorMessage: 'Unable to load menu.',
    addToCartLabel: 'Add to cart',
    addingLabel: 'Adding...',
    addToCartErrorMessage: 'Unable to add item to cart.',
    comboLabel: 'Combo',
    optionLabelPrefix: 'Option',
    noExtrasSelected: 'No extras selected',
    quantityShortLabel: 'Qty',
    eachLabel: 'each',
    removeLabel: 'Remove',
    cartEmptyMessage: 'Your cart is empty.',
    priceToConfirmLabel: 'Price to confirm',
    addComboLabel: 'Add combo',
    comboBadgeLabel: 'Combo',
    requiredLabel: 'Required',
    optionalLabel: 'Optional',
    minLabel: 'min',
    maxLabel: 'max',
    priceLabel: 'Price',
    quantityLabel: 'Quantity',
    itemsCountLabel: '{count} items',
    recommendedPickupMessage: 'Recommended pickup time selected automatically.',
    pickupNowMessage: 'Recommended pickup: right now',
    nextPickupMessage: 'Next available slot: {time}',
    choosePickupSlotLabel: 'Choose a pickup slot',
    unavailableSuffix: 'unavailable',
    loadingSlotsLabel: 'Loading available slots...',
    noSlotsOptionLabel: 'No pickup slots available.',
    loadSlotsErrorLabel: 'Unable to load pickup slots.',
});

function createLoadingState() {
    menuContainer.innerHTML = `
        <div class="text-center text-muted py-5">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-3 mb-0">${translations.loadingMenuMessage}</p>
        </div>
    `;
}

function renderCategoryShortcuts(categories) {
    if (!categoryShortcuts) {
        return;
    }

    if (!categories || !categories.length) {
        categoryShortcuts.innerHTML = '';
        return;
    }

    categoryShortcuts.innerHTML = categories
        .map((category) => `
            <a href="#category-${category.id}" class="btn btn-outline-primary btn-sm flex-shrink-0">
                ${category.name}
            </a>
        `)
        .join('');
}

function renderMenu(menu) {
    if (!menu || !menu.categories || !menu.categories.length) {
        categoryShortcuts?.classList.add('d-none');
        menuContainer.innerHTML = `
            <div class="text-center text-muted py-5">
                <p class="mb-2">${translations.emptyMenuMessage}</p>
                <p class="small">${translations.emptyMenuHint}</p>
            </div>
        `;
        return;
    }

    categoryShortcuts?.classList.remove('d-none');
    renderCategoryShortcuts(menu.categories);
    menuContainer.innerHTML = menu.categories
        .map((category, index) => renderCategory(category, index * 10, orderingEnabled, {
            priceToConfirmLabel: translations.priceToConfirmLabel,
            addComboLabel: translations.addComboLabel,
            comboBadgeLabel: translations.comboBadgeLabel,
            requiredLabel: translations.requiredLabel,
            optionalLabel: translations.optionalLabel,
            minLabel: translations.minLabel,
            maxLabel: translations.maxLabel,
            priceLabel: translations.priceLabel,
            quantityLabel: translations.quantityLabel,
            addToCartLabel: translations.addToCartLabel,
            itemsCountLabel: translations.itemsCountLabel,
        }))
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

    const rendered = renderCart(cart, {
        comboLabel: translations.comboLabel,
        optionLabelPrefix: translations.optionLabelPrefix,
        noExtrasSelected: translations.noExtrasSelected,
        quantityLabel: translations.quantityShortLabel,
        eachLabel: translations.eachLabel,
        removeLabel: translations.removeLabel,
        cartEmptyMessage: translations.cartEmptyMessage,
    });
    cartContent.classList.remove('d-none');
    cartEmpty.classList.add('d-none');
    cartItemsContainer.innerHTML = rendered.markup;
    cartTotalElement.textContent = `€${rendered.total}`;

    if (navCartCount) {
        navCartCount.textContent = interpolate(translations.cartCountLabel, { count: rendered.itemCount });
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
        checkoutHelp.textContent = translations.loginCheckoutMessage;
        return;
    }

    if (!enabled) {
        checkoutHelp.classList.remove('d-none');
        checkoutHelp.textContent = message || translations.cartCheckoutMessage;
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
        slotSelector.reset(translations.cartContinueMessage);
        setCheckoutState(false, translations.cartContinueMessage);
        return;
    }

    try {
        const slots = await slotSelector.loadSlots(fetchPickupSlots, foodtruckSlug);
        if (!slots.length) {
            setCheckoutState(false, translations.noSlotsMessage);
            return;
        }
        setCheckoutState(false, translations.selectSlotMessage);
    } catch (error) {
        setCheckoutState(false, translations.loadSlotsErrorMessage);
        console.error(error);
    }
}

function handleSlotSelection(slotId) {
    if (!slotId) {
        setCheckoutState(false, translations.selectSlotMessage);
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
        translations: {
            recommendedPickupMessage: translations.recommendedPickupMessage,
            pickupNowMessage: translations.pickupNowMessage,
            nextPickupMessage: translations.nextPickupMessage,
            choosePickupSlotLabel: translations.choosePickupSlotLabel,
            unavailableSuffix: translations.unavailableSuffix,
            loadingSlotsLabel: translations.loadingSlotsLabel,
            noSlotsOptionLabel: translations.noSlotsOptionLabel,
            noSlotsMessage: translations.noSlotsMessage,
            loadSlotsErrorLabel: translations.loadSlotsErrorLabel,
            selectSlotMessage: translations.selectSlotMessage,
        },
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
        translations: {
            loginRequiredMessage: translations.loginCheckoutMessage,
            selectSlotMessage: translations.selectSlotMessage,
            cartContinueMessage: translations.cartContinueMessage,
            checkoutLabel: checkoutButton.textContent.trim(),
        },
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
        cartEmpty.innerHTML = `<p class="text-danger">${translations.loadCartErrorMessage}</p>`;
        console.error(error);
    }
}

async function initializeMenu() {
    if (!foodtruckSlug) {
        renderError(translations.missingFoodtruckMessage);
        return;
    }

    createLoadingState();

    try {
        const menu = await fetchFoodtruckMenu(foodtruckSlug);
        renderMenu(menu);
    } catch (error) {
        renderError(error.message || translations.loadMenuErrorMessage);
    }
}

async function handleAddToCart(event) {
    const button = event.target.closest('.add-to-cart');
    if (!button) {
        return;
    }

    const itemCard = button.closest('.menu-item, .js-orderable-entry, .card');
    const itemId = button.dataset.itemId ? Number(button.dataset.itemId) : null;
    const comboId = button.dataset.comboId ? Number(button.dataset.comboId) : null;
    const quantityField = itemCard?.querySelector('.menu-item-quantity');
    const quantity = Math.max(1, Number(quantityField?.value || 1));
    const selectedOptions = itemId
        ? Array.from(itemCard.querySelectorAll('.menu-option:checked')).map((input) => Number(input.dataset.optionId))
        : [];
    const defaultLabel = button.dataset.defaultLabel || translations.addToCartLabel;

    button.disabled = true;
    button.textContent = translations.addingLabel;

    try {
        const cart = await addCartItem({
            foodtruck_slug: foodtruckSlug,
            ...(itemId ? { item_id: itemId } : {}),
            ...(comboId ? { combo_id: comboId } : {}),
            quantity,
            selected_options: selectedOptions,
        });
        await handleCartUpdate(cart);
    } catch (error) {
        renderError(error.message || translations.addToCartErrorMessage);
        console.error(error);
    } finally {
        button.disabled = false;
        button.textContent = defaultLabel;
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
    if (!orderingEnabled) {
        return;
    }

    menuContainer?.addEventListener('click', handleAddToCart);
    cartItemsContainer?.addEventListener('click', handleRemoveFromCart);
}

async function bootstrap() {
    await initializeMenu();

    if (orderingEnabled) {
        initializeSlotSelector();
        initializeCheckoutFlow();
        wireEvents();
        await refreshCart();
    }
}

bootstrap();
