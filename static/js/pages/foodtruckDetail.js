import { fetchFoodtruckMenu } from '../api/menu.js';
import { fetchCart, addCartItem, removeCartItem, updateCartItemQuantity } from '../api/cart.js';
import { fetchPickupSlots } from '../api/slots.js';
import { renderCategory } from '../components/menuItem.js';
import { renderCart } from '../components/cart.js';
import { getSelectedOptionIds, renderItemOrderModalBody, validateItemSelection } from '../components/itemOrderModal.js';
import { SlotSelector } from '../components/slotSelector.js';
import { createCheckoutHandler } from '../pages/checkout.js';
import { getDatasetTranslations, interpolate } from '../i18n.js';

const pageContainer = document.querySelector('[data-foodtruck-slug]');
const foodtruckSlug = pageContainer?.dataset.foodtruckSlug;
const userAuthenticated = pageContainer?.dataset.userAuthenticated === 'true';
const orderingEnabled = pageContainer?.dataset.orderingEnabled === 'true';
const paymentCheckoutUrlTemplate = pageContainer?.dataset.paymentCheckoutUrlTemplate || '';

const menuContainer = document.getElementById('menu-container');
const categoryShortcuts = document.getElementById('category-shortcuts');
const cartItemsContainer = orderingEnabled ? document.getElementById('cart-items') : null;
const cartTotalElement = orderingEnabled ? document.getElementById('cart-total') : null;
const cartContent = orderingEnabled ? document.getElementById('cart-content') : null;
const cartEmpty = orderingEnabled ? document.getElementById('cart-empty') : null;
const cartLoading = orderingEnabled ? document.getElementById('cart-loading') : null;
const navCartCount = orderingEnabled ? document.getElementById('nav-cart-count') : null;
const checkoutButton = orderingEnabled ? document.getElementById('checkout-button') : null;
const payOnSiteButton = orderingEnabled ? document.getElementById('checkout-on-site-button') : null;
const checkoutHelp = orderingEnabled ? document.getElementById('checkout-help') : null;
const pickupSlotSelect = orderingEnabled ? document.getElementById('pickup-slot-select') : null;
const pickupSlotHelp = orderingEnabled ? document.getElementById('pickup-slot-help') : null;
const itemOrderModalElement = orderingEnabled ? document.getElementById('itemOrderModal') : null;
const itemOrderForm = orderingEnabled ? document.getElementById('item-order-form') : null;
const itemOrderTitle = orderingEnabled ? document.getElementById('itemOrderModalLabel') : null;
const itemOrderDescription = orderingEnabled ? document.getElementById('item-order-description') : null;
const itemOrderOptions = orderingEnabled ? document.getElementById('item-order-options') : null;
const itemOrderError = orderingEnabled ? document.getElementById('item-order-error') : null;
const itemOrderQuantity = orderingEnabled ? document.getElementById('item-order-quantity') : null;
const itemOrderSubmit = orderingEnabled ? document.getElementById('item-order-submit') : null;
const comboOrderModalElement = orderingEnabled ? document.getElementById('comboOrderModal') : null;
const comboOrderForm = orderingEnabled ? document.getElementById('combo-order-form') : null;
const comboOrderTitle = orderingEnabled ? document.getElementById('comboOrderModalLabel') : null;
const comboOrderDescription = orderingEnabled ? document.getElementById('combo-order-description') : null;
const comboOrderComponents = orderingEnabled ? document.getElementById('combo-order-components') : null;
const comboOrderError = orderingEnabled ? document.getElementById('combo-order-error') : null;
const comboOrderPrice = orderingEnabled ? document.getElementById('combo-order-price') : null;
const comboOrderQuantity = orderingEnabled ? document.getElementById('combo-order-quantity') : null;
const comboOrderSubmit = orderingEnabled ? document.getElementById('combo-order-submit') : null;
const authRequiredModalElement = orderingEnabled ? document.getElementById('authRequiredModal') : null;
const authRequiredLoginLink = orderingEnabled ? document.getElementById('auth-required-login') : null;
const authRequiredRegisterLink = orderingEnabled ? document.getElementById('auth-required-register') : null;
let slotSelector = null;
let menuLoaded = false;
let menuLoadTimeout = null;
const MENU_LOAD_TIMEOUT_MS = 6000;
let activeItemId = null;
let activeComboId = null;
let itemOrderModal = null;
let comboOrderModal = null;
let authRequiredModal = null;
const menuItemsById = new Map();
const menuCombosById = new Map();
const menuCategoriesById = new Map();
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
    decreaseQuantityLabel: 'Decrease quantity',
    increaseQuantityLabel: 'Increase quantity',
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
    customizeItemTitle: 'Customize {item}',
    composeComboTitle: 'Compose {combo}',
    addItemToCartLabel: 'Add item to cart',
    addComboToCartLabel: 'Add combo to cart',
    composeComboLabel: 'Compose combo',
    noCustomizationOptionsMessage: 'No customization options for this item.',
    selectItemForComponentMessage: 'Choose an item for {component}.',
    estimatedComboPriceLabel: 'Estimated combo price',
    customerChoosesFromLabel: 'Customer chooses from {category}',
    selectAtLeastOptionsMessage: 'Please choose at least {count} option(s) for {group}.',
    selectAtMostOptionsMessage: 'You can select up to {count} option(s) for {group}.',
    redirectingToPaymentMessage: 'Order submitted. Redirecting to payment...',
    payOnlineLabel: 'Pay online',
    payOnSiteLabel: 'Pay at the food truck',
    payOnSiteSubmittedMessage: 'Order submitted. Pay at the food truck on pickup.',
});
const loginUrl = pageContainer?.dataset.loginUrl || '';
const registerUrl = pageContainer?.dataset.registerUrl || '';

function getNavbarOffset() {
    const navbar = document.querySelector('.foodtruck-order-navbar');
    if (!navbar) {
        return 148;
    }
    return Math.ceil(navbar.getBoundingClientRect().height);
}

function syncNavbarMetrics() {
    const offset = getNavbarOffset();
    document.documentElement.style.setProperty('--foodtruck-navbar-height', `${offset}px`);
}

function scrollToAnchorTarget(target, updateHash = true) {
    if (!target) {
        return;
    }

    const top = target.getBoundingClientRect().top + window.scrollY - getNavbarOffset() - 12;
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });

    if (updateHash && target.id) {
        history.replaceState(null, '', `#${target.id}`);
    }
}

function wireOffsetAnchors() {
    const anchorLinks = document.querySelectorAll('a.js-foodtruck-anchor[href^="#"], #nav-cart-link[href^="#"]');
    anchorLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
            const href = link.getAttribute('href') || '';
            const targetId = href.slice(1);
            if (!targetId) {
                return;
            }

            const target = document.getElementById(targetId);
            if (!target) {
                return;
            }

            event.preventDefault();
            scrollToAnchorTarget(target, true);
        });
    });

    if (window.location.hash) {
        const target = document.getElementById(window.location.hash.replace('#', ''));
        if (target) {
            window.requestAnimationFrame(() => {
                scrollToAnchorTarget(target, false);
            });
        }
    }
}

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

    menuItemsById.clear();
    menuCombosById.clear();
    menuCategoriesById.clear();
    menu.categories.forEach((category) => {
        menuCategoriesById.set(String(category.id), category);
        (category.items || []).forEach((item) => {
            menuItemsById.set(String(item.id), item);
        });
        (category.combos || []).forEach((combo) => {
            menuCombosById.set(String(combo.id), combo);
        });
    });

    categoryShortcuts?.classList.remove('d-none');
    renderCategoryShortcuts(menu.categories);
    menuContainer.innerHTML = menu.categories
        .map((category, index) => renderCategory(category, index * 10, orderingEnabled, {
            priceToConfirmLabel: translations.priceToConfirmLabel,
            addComboLabel: translations.addComboLabel,
            composeComboLabel: translations.composeComboLabel,
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
            navCartCount.textContent = '0';
        }
        return;
    }

    const rendered = renderCart(cart, {
        comboLabel: translations.comboLabel,
        optionLabelPrefix: translations.optionLabelPrefix,
        noExtrasSelected: translations.noExtrasSelected,
        quantityLabel: translations.quantityShortLabel,
        decreaseQuantityLabel: translations.decreaseQuantityLabel,
        increaseQuantityLabel: translations.increaseQuantityLabel,
        eachLabel: translations.eachLabel,
        removeLabel: translations.removeLabel,
        cartEmptyMessage: translations.cartEmptyMessage,
    });
    cartContent.classList.remove('d-none');
    cartEmpty.classList.add('d-none');
    cartItemsContainer.innerHTML = rendered.markup;
    cartTotalElement.textContent = `€${rendered.total}`;

    if (navCartCount) {
        navCartCount.textContent = String(rendered.itemCount);
    }
}

function renderError(message) {
    menuContainer.innerHTML = `
        <div class="alert alert-danger" role="alert">
            ${message}
        </div>
    `;
}

function buildAuthUrl(baseUrl) {
    if (!baseUrl) {
        return '#';
    }

    const nextPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    const separator = baseUrl.includes('?') ? '&' : '?';
    return `${baseUrl}${separator}next=${encodeURIComponent(nextPath)}`;
}

function configureAuthLinks() {
    if (authRequiredLoginLink) {
        authRequiredLoginLink.href = buildAuthUrl(loginUrl);
    }

    if (authRequiredRegisterLink) {
        authRequiredRegisterLink.href = buildAuthUrl(registerUrl);
    }
}

function setItemOrderError(message = '') {
    if (!itemOrderError) {
        return;
    }

    if (!message) {
        itemOrderError.classList.add('d-none');
        itemOrderError.textContent = '';
        return;
    }

    itemOrderError.classList.remove('d-none');
    itemOrderError.textContent = message;
}

function setComboOrderError(message = '') {
    if (!comboOrderError) {
        return;
    }

    if (!message) {
        comboOrderError.classList.add('d-none');
        comboOrderError.textContent = '';
        return;
    }

    comboOrderError.classList.remove('d-none');
    comboOrderError.textContent = message;
}

function resetItemOrderModal() {
    activeItemId = null;
    setItemOrderError();

    if (itemOrderTitle) {
        itemOrderTitle.textContent = '';
    }

    if (itemOrderDescription) {
        itemOrderDescription.textContent = '';
        itemOrderDescription.classList.add('d-none');
    }

    if (itemOrderOptions) {
        itemOrderOptions.innerHTML = '';
    }

    if (itemOrderQuantity) {
        itemOrderQuantity.value = '1';
    }

    if (itemOrderSubmit) {
        itemOrderSubmit.disabled = false;
        itemOrderSubmit.textContent = translations.addItemToCartLabel;
    }
}

function resetComboOrderModal() {
    activeComboId = null;
    setComboOrderError();

    if (comboOrderTitle) {
        comboOrderTitle.textContent = '';
    }

    if (comboOrderDescription) {
        comboOrderDescription.textContent = '';
        comboOrderDescription.classList.add('d-none');
    }

    if (comboOrderComponents) {
        comboOrderComponents.innerHTML = '';
    }

    if (comboOrderPrice) {
        comboOrderPrice.textContent = '€0.00';
    }

    if (comboOrderQuantity) {
        comboOrderQuantity.value = '1';
    }

    if (comboOrderSubmit) {
        comboOrderSubmit.disabled = false;
        comboOrderSubmit.textContent = translations.addComboToCartLabel;
    }
}

function showAuthRequiredModal() {
    if (authRequiredModal) {
        authRequiredModal.show();
        return;
    }

    if (loginUrl) {
        window.location.assign(buildAuthUrl(loginUrl));
    }
}

function showItemOrderModal(item) {
    if (!item || !itemOrderModal) {
        return;
    }

    activeItemId = String(item.id);
    setItemOrderError();
    itemOrderTitle.textContent = interpolate(translations.customizeItemTitle, { item: item.name });

    if (item.description) {
        itemOrderDescription.textContent = item.description;
        itemOrderDescription.classList.remove('d-none');
    } else {
        itemOrderDescription.textContent = '';
        itemOrderDescription.classList.add('d-none');
    }

    itemOrderOptions.innerHTML = renderItemOrderModalBody(item, {
        requiredLabel: translations.requiredLabel,
        optionalLabel: translations.optionalLabel,
        minLabel: translations.minLabel,
        maxLabel: translations.maxLabel,
        noCustomizationOptionsMessage: translations.noCustomizationOptionsMessage,
    });
    itemOrderQuantity.value = '1';
    itemOrderSubmit.textContent = translations.addItemToCartLabel;
    itemOrderModal.show();
}

function getComboCandidates(comboItem) {
    if (comboItem.source_category_id) {
        return (menuCategoriesById.get(String(comboItem.source_category_id))?.items || []).filter((item) => item.is_available !== false);
    }

    if (Array.isArray(comboItem.fixed_items) && comboItem.fixed_items.length) {
        return comboItem.fixed_items
            .map((fixedItem) => menuItemsById.get(String(fixedItem.id)) || fixedItem)
            .filter((item) => item && item.is_available !== false);
    }

    if (Array.isArray(comboItem.fixed_item_ids) && comboItem.fixed_item_ids.length) {
        return comboItem.fixed_item_ids
            .map((fixedItemId) => menuItemsById.get(String(fixedItemId)))
            .filter((item) => item && item.is_available !== false);
    }

    if (comboItem.item_id) {
        const fixedItem = menuItemsById.get(String(comboItem.item_id));
        return fixedItem ? [fixedItem] : [];
    }

    return [];
}

function buildComboComponentMarkup(comboItem) {
    const candidates = getComboCandidates(comboItem);
    const selectedItemId = comboItem.item_id || (candidates.length ? candidates[0].id : '');
    const requiresChoice = Boolean(comboItem.source_category_id);
    const allowsMultipleFixed = !requiresChoice && candidates.length > 1;
    const sourceHint = comboItem.source_category_name
        ? interpolate(translations.customerChoosesFromLabel, { category: comboItem.source_category_name })
        : '';

    const selectorMarkup = requiresChoice ? `
        <select class="form-select combo-component-item-select" data-combo-item-id="${comboItem.id}">
            <option value="">${interpolate(translations.selectItemForComponentMessage, { component: comboItem.display_name })}</option>
            ${candidates.map((item) => `<option value="${item.id}" ${Number(selectedItemId) === Number(item.id) ? 'selected' : ''}>${item.name}</option>`).join('')}
        </select>
    ` : allowsMultipleFixed ? `
        ${candidates.map((item) => `
            <input type="hidden" class="combo-component-item-select" data-combo-item-id="${comboItem.id}" value="${item.id}">
            <div class="fw-medium">${item.name}</div>
        `).join('')}
    ` : `
        <input type="hidden" class="combo-component-item-select" data-combo-item-id="${comboItem.id}" value="${selectedItemId}">
        <div class="fw-medium">${candidates[0]?.name || comboItem.display_name}</div>
    `;

    return `
        <section class="border rounded p-3 mb-3" data-combo-item-id="${comboItem.id}">
            <div class="d-flex justify-content-between align-items-start gap-3 mb-2">
                <div>
                    <strong>${comboItem.display_name}</strong>
                    ${sourceHint ? `<div class="small text-muted">${sourceHint}</div>` : ''}
                </div>
                <span class="badge text-bg-light">x${comboItem.quantity}</span>
            </div>
            ${selectorMarkup}
            <div class="combo-component-options mt-3"></div>
        </section>
    `;
}

function renderComboComponentOptions(section) {
    const itemSelectElements = Array.from(section.querySelectorAll('.combo-component-item-select'));
    const optionsContainer = section.querySelector('.combo-component-options');

    if (!optionsContainer) {
        return;
    }

    const selectedItemIds = itemSelectElements
        .map((itemSelect) => itemSelect?.value)
        .filter((itemId) => Boolean(itemId));

    if (!selectedItemIds.length) {
        optionsContainer.innerHTML = '';
        return;
    }

    optionsContainer.innerHTML = selectedItemIds.map((selectedItemId) => {
        const selectedItem = menuItemsById.get(String(selectedItemId));
        if (!selectedItem) {
            return '';
        }

        const optionsMarkup = renderItemOrderModalBody(selectedItem, {
            requiredLabel: translations.requiredLabel,
            optionalLabel: translations.optionalLabel,
            minLabel: translations.minLabel,
            maxLabel: translations.maxLabel,
            noCustomizationOptionsMessage: translations.noCustomizationOptionsMessage,
        });

        const itemTitle = selectedItemIds.length > 1
            ? `<div class="fw-medium small mb-2">${selectedItem.name}</div>`
            : '';

        return `
            <div class="combo-component-options-item mb-3" data-item-id="${selectedItem.id}">
                ${itemTitle}
                ${optionsMarkup}
            </div>
        `;
    }).join('');
}

function updateComboOrderPricePreview(combo) {
    if (!comboOrderPrice || !combo) {
        return;
    }

    const basePrice = parseFloat(combo.display_price || 0);
    let optionsExtra = 0;

    const taxRate = parseFloat(combo.tax_rate || 0);
    const taxMultiplier = combo.prices_include_tax ? (1 + taxRate) : 1;

    combo.combo_items.forEach((comboItem) => {
        const section = comboOrderComponents?.querySelector(`[data-combo-item-id="${comboItem.id}"]`);
        const itemSelectElements = Array.from(section?.querySelectorAll('.combo-component-item-select') || []);
        const selectedItemIds = itemSelectElements
            .map((itemSelect) => itemSelect?.value)
            .filter((itemId) => Boolean(itemId));

        selectedItemIds.forEach((selectedItemId) => {
            const selectedItem = menuItemsById.get(String(selectedItemId));
            if (!selectedItem) {
                return;
            }

            const scopedOptionsContainer = section.querySelector(`[data-item-id="${selectedItemId}"]`) || section.querySelector('.combo-component-options');
            const selectedOptions = getSelectedOptionIds(scopedOptionsContainer);
            selectedOptions.forEach((optionId) => {
                const option = (selectedItem.option_groups || []).flatMap((group) => group.options || []).find((entry) => Number(entry.id) === Number(optionId));
                if (option) {
                    optionsExtra += parseFloat(option.price_modifier || 0) * taxMultiplier * Number(comboItem.quantity || 1);
                }
            });
        });
    });

    const quantity = parseInt(comboOrderQuantity?.value || '1', 10);
    const total = (basePrice + optionsExtra) * Math.max(1, quantity);
    comboOrderPrice.textContent = `€${total.toFixed(2)}`;
}

function showComboOrderModal(combo) {
    if (!combo || !comboOrderModal) {
        return;
    }

    activeComboId = String(combo.id);
    setComboOrderError();
    comboOrderTitle.textContent = interpolate(translations.composeComboTitle, { combo: combo.name });

    if (combo.description) {
        comboOrderDescription.textContent = combo.description;
        comboOrderDescription.classList.remove('d-none');
    } else {
        comboOrderDescription.textContent = '';
        comboOrderDescription.classList.add('d-none');
    }

    comboOrderComponents.innerHTML = (combo.combo_items || []).map((comboItem) => buildComboComponentMarkup(comboItem)).join('');
    comboOrderComponents.querySelectorAll('[data-combo-item-id]').forEach((section) => {
        renderComboComponentOptions(section);
    });
    comboOrderQuantity.value = '1';
    comboOrderSubmit.textContent = translations.addComboToCartLabel;
    updateComboOrderPricePreview(combo);
    comboOrderModal.show();
}

function collectComboSelections(combo) {
    const selections = [];

    for (const comboItem of combo.combo_items || []) {
        const section = comboOrderComponents?.querySelector(`[data-combo-item-id="${comboItem.id}"]`);
        const itemSelectElements = Array.from(section?.querySelectorAll('.combo-component-item-select') || []);
        const selectedItemIds = itemSelectElements
            .map((itemSelect) => itemSelect?.value)
            .filter((itemId) => Boolean(itemId));
        const requiresChoice = Boolean(comboItem.source_category_id);

        if (requiresChoice && !selectedItemIds.length) {
            return {
                valid: false,
                message: interpolate(translations.selectItemForComponentMessage, { component: comboItem.display_name }),
            };
        }

        if (!requiresChoice && !selectedItemIds.length) {
            return {
                valid: false,
                message: interpolate(translations.selectItemForComponentMessage, { component: comboItem.display_name }),
            };
        }

        for (const selectedItemId of selectedItemIds) {
            const selectedItem = menuItemsById.get(String(selectedItemId));
            if (!selectedItem) {
                return {
                    valid: false,
                    message: interpolate(translations.selectItemForComponentMessage, { component: comboItem.display_name }),
                };
            }

            const scopedOptionsContainer = section.querySelector(`[data-item-id="${selectedItemId}"]`) || section.querySelector('.combo-component-options');
            const selectedOptions = getSelectedOptionIds(scopedOptionsContainer);
            const validation = validateItemSelection(selectedItem, selectedOptions, {
                selectAtLeastOptionsMessage: translations.selectAtLeastOptionsMessage,
                selectAtMostOptionsMessage: translations.selectAtMostOptionsMessage,
            });

            if (!validation.valid) {
                return validation;
            }

            selections.push({
                combo_item_id: comboItem.id,
                item_id: Number(selectedItemId),
                selected_options: selectedOptions,
            });
        }
    }

    return { valid: true, selections };
}

async function submitItemOrder(event) {
    event.preventDefault();

    if (!activeItemId) {
        return;
    }

    const item = menuItemsById.get(activeItemId);
    if (!item) {
        setItemOrderError(translations.addToCartErrorMessage);
        return;
    }

    const quantity = Math.max(1, Number(itemOrderQuantity?.value || 1));
    const selectedOptions = getSelectedOptionIds(itemOrderOptions);
    const validation = validateItemSelection(item, selectedOptions, {
        selectAtLeastOptionsMessage: translations.selectAtLeastOptionsMessage,
        selectAtMostOptionsMessage: translations.selectAtMostOptionsMessage,
    });

    if (!validation.valid) {
        setItemOrderError(validation.message);
        return;
    }

    setItemOrderError();
    itemOrderSubmit.disabled = true;
    itemOrderSubmit.textContent = translations.addingLabel;

    try {
        const cart = await addCartItem({
            foodtruck_slug: foodtruckSlug,
            item_id: Number(activeItemId),
            quantity,
            selected_options: selectedOptions,
        });
        await handleCartUpdate(cart);
        itemOrderModal.hide();
    } catch (error) {
        setItemOrderError(error.message || translations.addToCartErrorMessage);
        console.error(error);
    } finally {
        itemOrderSubmit.disabled = false;
        itemOrderSubmit.textContent = translations.addItemToCartLabel;
    }
}

async function submitComboOrder(event) {
    event.preventDefault();

    if (!activeComboId) {
        return;
    }

    const combo = menuCombosById.get(activeComboId);
    if (!combo) {
        setComboOrderError(translations.addToCartErrorMessage);
        return;
    }

    const quantity = Math.max(1, Number(comboOrderQuantity?.value || 1));
    const collected = collectComboSelections(combo);

    if (!collected.valid) {
        setComboOrderError(collected.message);
        return;
    }

    setComboOrderError();
    comboOrderSubmit.disabled = true;
    comboOrderSubmit.textContent = translations.addingLabel;

    try {
        const cart = await addCartItem({
            foodtruck_slug: foodtruckSlug,
            combo_id: Number(activeComboId),
            quantity,
            combo_selections: collected.selections,
        });
        await handleCartUpdate(cart);
        comboOrderModal.hide();
    } catch (error) {
        setComboOrderError(error.message || translations.addToCartErrorMessage);
        console.error(error);
    } finally {
        comboOrderSubmit.disabled = false;
        comboOrderSubmit.textContent = translations.addComboToCartLabel;
    }
}

function handleComboOrderChange(event) {
    const section = event.target.closest('section[data-combo-item-id]');
    if (!section || !activeComboId) {
        return;
    }

    if (event.target.classList.contains('combo-component-item-select')) {
        renderComboComponentOptions(section);
    }

    const combo = menuCombosById.get(activeComboId);
    updateComboOrderPricePreview(combo);
}

function setCheckoutState(enabled, message = null) {
    if (!checkoutButton && !payOnSiteButton) {
        return;
    }

    [checkoutButton, payOnSiteButton].filter(Boolean).forEach((button) => {
        button.disabled = !enabled || !userAuthenticated;
    });

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
        paymentCheckoutUrlTemplate,
        payOnSiteButton,
        translations: {
            loginRequiredMessage: translations.loginCheckoutMessage,
            selectSlotMessage: translations.selectSlotMessage,
            cartContinueMessage: translations.cartContinueMessage,
            checkoutLabel: checkoutButton.textContent.trim(),
            payOnSiteLabel: payOnSiteButton?.textContent?.trim() || translations.payOnSiteLabel,
            redirectingToPaymentMessage: translations.redirectingToPaymentMessage,
            payOnSiteSubmittedMessage: translations.payOnSiteSubmittedMessage,
        },
    });

    checkoutButton.addEventListener('click', () => handler('online', checkoutButton));
    payOnSiteButton?.addEventListener('click', () => handler('on_site', payOnSiteButton));
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

    if (!userAuthenticated) {
        showAuthRequiredModal();
        return;
    }

    const itemCard = button.closest('.menu-item, .js-orderable-entry, .card');
    const itemId = button.dataset.itemId ? Number(button.dataset.itemId) : null;
    const comboId = button.dataset.comboId ? Number(button.dataset.comboId) : null;

    if (itemId) {
        showItemOrderModal(menuItemsById.get(String(itemId)));
        return;
    }

    if (comboId) {
        showComboOrderModal(menuCombosById.get(String(comboId)));
        return;
    }

    const quantityField = itemCard?.querySelector('.menu-item-quantity');
    const quantity = Math.max(1, Number(quantityField?.value || 1));
    const selectedOptions = [];
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

async function updateCartLineQuantity(lineKey, quantity, input = null) {
    if (!lineKey) {
        return;
    }

    const normalizedQuantity = Math.max(1, Number(quantity || 1));
    if (input) {
        input.value = String(normalizedQuantity);
        input.disabled = true;
    }

    try {
        const cart = await updateCartItemQuantity(lineKey, normalizedQuantity);
        await handleCartUpdate(cart);
    } catch (error) {
        console.error(error);
    } finally {
        if (input) {
            input.disabled = false;
        }
    }
}

async function handleCartClick(event) {
    const removeButton = event.target.closest('.cart-remove');
    if (removeButton) {
        const lineKey = removeButton.dataset.lineKey;
        if (!lineKey) {
            return;
        }

        removeButton.disabled = true;

        try {
            const cart = await removeCartItem(lineKey);
            await handleCartUpdate(cart);
        } catch (error) {
            console.error(error);
        } finally {
            removeButton.disabled = false;
        }
        return;
    }

    const quantityStepButton = event.target.closest('.cart-quantity-step');
    if (!quantityStepButton) {
        return;
    }

    const lineKey = quantityStepButton.dataset.lineKey;
    const delta = Number(quantityStepButton.dataset.delta || 0);
    const quantityInput = cartItemsContainer?.querySelector(`.cart-quantity-input[data-line-key="${lineKey}"]`);
    const nextQuantity = Math.max(1, Number(quantityInput?.value || 1) + delta);
    await updateCartLineQuantity(lineKey, nextQuantity, quantityInput);
}

async function handleCartQuantityChange(event) {
    const input = event.target.closest('.cart-quantity-input');
    if (!input) {
        return;
    }

    await updateCartLineQuantity(input.dataset.lineKey, input.value, input);
}

function wireEvents() {
    if (!orderingEnabled) {
        return;
    }

    menuContainer?.addEventListener('click', handleAddToCart);
    cartItemsContainer?.addEventListener('click', handleCartClick);
    cartItemsContainer?.addEventListener('change', handleCartQuantityChange);
    itemOrderForm?.addEventListener('submit', submitItemOrder);
    comboOrderForm?.addEventListener('submit', submitComboOrder);
    comboOrderComponents?.addEventListener('change', handleComboOrderChange);
    comboOrderQuantity?.addEventListener('input', () => {
        const combo = menuCombosById.get(activeComboId);
        updateComboOrderPricePreview(combo);
    });
}

function initializeModals() {
    if (!orderingEnabled) {
        return;
    }

    if (itemOrderModalElement) {
        itemOrderModal = new bootstrap.Modal(itemOrderModalElement);
        itemOrderModalElement.addEventListener('hidden.bs.modal', resetItemOrderModal);
    }

    if (comboOrderModalElement) {
        comboOrderModal = new bootstrap.Modal(comboOrderModalElement);
        comboOrderModalElement.addEventListener('hidden.bs.modal', resetComboOrderModal);
    }

    if (authRequiredModalElement) {
        authRequiredModal = new bootstrap.Modal(authRequiredModalElement);
    }

    configureAuthLinks();
}

async function initializePage() {
    syncNavbarMetrics();
    wireOffsetAnchors();
    window.addEventListener('resize', syncNavbarMetrics);
    await initializeMenu();

    if (orderingEnabled) {
        initializeModals();
        initializeSlotSelector();
        initializeCheckoutFlow();
        wireEvents();
        await refreshCart();
    }
}

initializePage();
