import { fetchFoodtruckMenu } from '../api/menu.js';
import { fetchCart, addCartItem, removeCartItem } from '../api/cart.js';
import { fetchPickupSlots } from '../api/slots.js';
import { renderCategory } from '../components/menuItem.js';
import { renderCart } from '../components/cart.js';
import { SlotSelector } from '../components/slotSelector.js';
import { createCheckoutHandler } from '../pages/checkout.js';
import { getDatasetTranslations } from '../i18n.js';

console.log('[FoodtruckDetail] Script starting...');

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
const translations = getDatasetTranslations(pageContainer, {
    loadingMenuMessage: 'Loading menu...',
    emptyMenuMessage: 'No menu items are available right now.',
    emptyMenuHint: 'Please check back later.',
    missingFoodtruckMessage: 'Could not identify foodtruck.',
    loadMenuErrorMessage: 'Unable to load menu.',
});

console.log('[FoodtruckDetail] DOM elements loaded');
console.log('[FoodtruckDetail] foodtruckSlug:', foodtruckSlug);
console.log('[FoodtruckDetail] userAuthenticated:', userAuthenticated);

let slotSelector = null;

function createLoadingState() {
    if (!menuContainer) {
        console.warn('[FoodtruckDetail] menuContainer not found');
        return;
    }
    menuContainer.innerHTML = `
        <div class="text-center text-muted py-5">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-3 mb-0">${translations.loadingMenuMessage}</p>
        </div>
    `;
}

function renderMenu(menu) {
    console.log('[FoodtruckDetail] renderMenu called with:', menu);
    if (!menu || !menu.categories || !menu.categories.length) {
        if (menuContainer) {
            menuContainer.innerHTML = `
                <div class="text-center text-muted py-5">
                    <p class="mb-2">${translations.emptyMenuMessage}</p>
                    <p class="small">${translations.emptyMenuHint}</p>
                </div>
            `;
        }
        return;
    }

    if (menuContainer) {
        menuContainer.innerHTML = menu.categories
            .map((category, index) => renderCategory(category, index * 10))
            .join('');
    }
}

function renderError(message) {
    console.error('[FoodtruckDetail] Error:', message);
    if (menuContainer) {
        menuContainer.innerHTML = `
            <div class="alert alert-danger" role="alert">
                ${message}
            </div>
        `;
    }
}

async function initializeMenu() {
    console.log('[FoodtruckDetail] initializeMenu() called');
    
    if (!foodtruckSlug) {
        renderError(translations.missingFoodtruckMessage);
        return;
    }

    createLoadingState();

    try {
        console.log('[FoodtruckDetail] Fetching menu for slug:', foodtruckSlug);
        const menu = await fetchFoodtruckMenu(foodtruckSlug);
        console.log('[FoodtruckDetail] Menu fetched successfully:', menu);
        renderMenu(menu);
    } catch (error) {
        console.error('[FoodtruckDetail] Error loading menu:', error);
        renderError(error.message || translations.loadMenuErrorMessage);
    }
}

console.log('[FoodtruckDetail] About to call initializeMenu()');
initializeMenu().then(() => {
    console.log('[FoodtruckDetail] Menu initialization complete');
}).catch(err => {
    console.error('[FoodtruckDetail] Menu initialization failed:', err);
});
