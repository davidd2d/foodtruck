export function renderCartItem(item) {
    const optionSummary = item.line_type === 'combo'
        ? (item.component_summary || 'Combo')
        : item.selected_options && item.selected_options.length
            ? item.selected_options.map((option) => option.name || `Option ${option.option_id}`).join(', ')
            : 'No extras selected';

    return `
        <li class="list-group-item d-flex justify-content-between align-items-start">
            <div>
                <div class="fw-semibold">${item.item_name}</div>
                <div class="small text-muted">${optionSummary}</div>
                <div class="small text-muted">Qty ${item.quantity} • €${parseFloat(item.unit_price).toFixed(2)} each</div>
            </div>
            <div class="text-end">
                <div class="fw-semibold">€${parseFloat(item.total_price).toFixed(2)}</div>
                <button type="button" class="btn btn-link btn-sm text-danger cart-remove" data-line-key="${item.line_key}">
                    Remove
                </button>
            </div>
        </li>
    `;
}

export function renderCart(cart) {
    if (!cart || cart.items.length === 0) {
        return {
            empty: true,
            markup: '<li class="list-group-item text-center text-muted">Your cart is empty.</li>',
        };
    }

    const itemsMarkup = cart.items.map(renderCartItem).join('');
    return {
        empty: false,
        markup: itemsMarkup,
        total: parseFloat(cart.total_price).toFixed(2),
        itemCount: cart.item_count,
    };
}
