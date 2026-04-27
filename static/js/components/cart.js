const defaultTranslations = {
    comboLabel: 'Combo',
    optionLabelPrefix: 'Option',
    noExtrasSelected: 'No extras selected',
    quantityLabel: 'Qty',
    decreaseQuantityLabel: 'Decrease quantity',
    increaseQuantityLabel: 'Increase quantity',
    eachLabel: 'each',
    removeLabel: 'Remove',
    cartEmptyMessage: 'Your cart is empty.',
};

export function renderCartItem(item, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };
    const optionSummary = item.line_type === 'combo'
        ? (item.component_summary || labels.comboLabel)
        : item.selected_options && item.selected_options.length
            ? item.selected_options.map((option) => option.name || `${labels.optionLabelPrefix} ${option.option_id}`).join(', ')
            : labels.noExtrasSelected;

    return `
        <li class="list-group-item d-flex justify-content-between align-items-start">
            <div>
                <div class="fw-semibold">${item.item_name}</div>
                <div class="small text-muted">${optionSummary}</div>
                <div class="small text-muted d-flex align-items-center gap-2 flex-wrap">
                    <span>${labels.quantityLabel}</span>
                    <div class="input-group input-group-sm" style="width: 112px;">
                        <button type="button" class="btn btn-outline-secondary cart-quantity-step" data-line-key="${item.line_key}" data-delta="-1" aria-label="${labels.decreaseQuantityLabel}">-</button>
                        <input type="number" min="1" class="form-control text-center cart-quantity-input" data-line-key="${item.line_key}" value="${item.quantity}" aria-label="${labels.quantityLabel}">
                        <button type="button" class="btn btn-outline-secondary cart-quantity-step" data-line-key="${item.line_key}" data-delta="1" aria-label="${labels.increaseQuantityLabel}">+</button>
                    </div>
                    <span>• €${parseFloat(item.display_unit_price ?? item.unit_price).toFixed(2)} ${labels.eachLabel}</span>
                </div>
            </div>
            <div class="text-end">
                <div class="fw-semibold">€${parseFloat(item.display_total_price ?? item.total_price).toFixed(2)}</div>
                <button type="button" class="btn btn-link btn-sm text-danger cart-remove" data-line-key="${item.line_key}">
                    ${labels.removeLabel}
                </button>
            </div>
        </li>
    `;
}

export function renderCart(cart, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };
    if (!cart || cart.items.length === 0) {
        return {
            empty: true,
            markup: `<li class="list-group-item text-center text-muted">${labels.cartEmptyMessage}</li>`,
        };
    }

    const itemsMarkup = cart.items.map((item) => renderCartItem(item, labels)).join('');
    return {
        empty: false,
        markup: itemsMarkup,
            total: parseFloat(cart.display_total_price ?? cart.total_price).toFixed(2),
        itemCount: cart.item_count,
    };
}
