import { interpolate } from '../i18n.js';

const defaultTranslations = {
    priceToConfirmLabel: 'Price to confirm',
    addComboLabel: 'Add combo',
    comboBadgeLabel: 'Combo',
    requiredLabel: 'Required',
    optionalLabel: 'Optional',
    minLabel: 'min',
    maxLabel: 'max',
    priceLabel: 'Price',
    quantityLabel: 'Quantity',
    addToCartLabel: 'Add to cart',
    itemsCountLabel: '{count} items',
};

export function renderComboItem(combo, orderingEnabled = true, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };
    const comboItems = (combo.combo_items || []).map((comboItem) => {
        const quantity = comboItem.quantity > 1 ? `${comboItem.quantity}x ` : '';
        return `<li>${quantity}${comboItem.display_name}</li>`;
    }).join('');

    const effectivePrice = combo.combo_price ?? combo.effective_price;
    const canOrder = orderingEnabled && effectivePrice !== null && effectivePrice !== undefined;
    const priceMarkup = effectivePrice !== null && effectivePrice !== undefined
        ? `€${parseFloat(effectivePrice).toFixed(2)}`
        : labels.priceToConfirmLabel;
    const orderingMarkup = canOrder ? `
        <div class="d-flex flex-wrap align-items-center gap-2 mt-3 js-orderable-entry">
            <label class="form-label small mb-0" for="combo-quantity-${combo.id}">${labels.quantityLabel}</label>
            <input id="combo-quantity-${combo.id}" type="number" min="1" value="1" class="form-control form-control-sm menu-item-quantity" style="width: 84px;">
            <button type="button" class="btn btn-sm btn-warning add-to-cart" data-combo-id="${combo.id}" data-default-label="${labels.addComboLabel}">
                ${labels.addComboLabel}
            </button>
        </div>
    ` : '';

    return `
        <div class="card mb-3 border-warning-subtle bg-warning-subtle">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start gap-3">
                    <div>
                        <div class="d-flex align-items-center gap-2 mb-1">
                            <h4 class="h6 mb-0">${combo.name}</h4>
                            <span class="badge text-bg-warning">${labels.comboBadgeLabel}</span>
                        </div>
                        <p class="text-muted mb-2">${combo.description || ''}</p>
                        ${comboItems ? `<ul class="small text-muted ps-3 mb-0">${comboItems}</ul>` : ''}
                    </div>
                    <div class="text-end">
                        <strong>${priceMarkup}</strong>
                    </div>
                </div>
                ${orderingMarkup}
            </div>
        </div>
    `;
}

export function renderMenuItem(item, itemIndex, orderingEnabled = true, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };

    return `
        <div class="card mb-3 menu-item" data-item-id="${item.id}">
            <div class="card-body">
                <div class="row g-3 align-items-start">
                    <div class="col-md-8">
                        <h4 class="h6 mb-1">${item.name}</h4>
                        <p class="text-muted mb-2">${item.description || ''}</p>
                        <div class="mb-0">
                            <strong>${labels.priceLabel}:</strong> €${parseFloat(item.base_price).toFixed(2)}
                        </div>
                    </div>
                    <div class="col-md-4 d-flex justify-content-md-end">
                        ${orderingEnabled ? `
                        <div class="d-flex flex-wrap align-items-center justify-content-md-end gap-2 w-100">
                            <button type="button" class="btn btn-primary btn-sm add-to-cart" data-item-id="${item.id}" data-default-label="${labels.addToCartLabel}">
                                ${labels.addToCartLabel}
                            </button>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
}

export function renderCategory(category, itemIndexStart = 0, orderingEnabled = true, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };
    const items = category.items || [];
    const combos = category.combos || [];
    const itemsMarkup = items
        .map((item, index) => renderMenuItem(item, itemIndexStart + index, orderingEnabled, labels))
        .join('');
    const combosMarkup = combos
        .map((combo) => renderComboItem(combo, orderingEnabled, labels))
        .join('');
    const totalEntries = items.length + combos.length;

    return `
        <section class="mb-4" id="category-${category.id}">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h3 class="h6 mb-0">${category.name}</h3>
                <span class="badge bg-secondary">${interpolate(labels.itemsCountLabel, { count: totalEntries })}</span>
            </div>
            ${itemsMarkup}
            ${combosMarkup}
        </section>
    `;
}
