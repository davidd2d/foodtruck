export function buildOptionControl(group, itemIndex) {
    const inputName = `group-${group.id}-${itemIndex}`;
    const isRadio = group.max_choices === 1 && group.min_choices <= 1;

    return group.options.map((option) => {
        const inputType = isRadio ? 'radio' : 'checkbox';
        return `
            <div class="form-check mb-2">
                <input
                    class="form-check-input menu-option"
                    type="${inputType}"
                    name="${inputName}"
                    id="option-${option.id}"
                    data-option-id="${option.id}"
                    value="${option.id}"
                />
                <label class="form-check-label" for="option-${option.id}">
                    ${option.name} <span class="text-muted">(+€${parseFloat(option.price_modifier).toFixed(2)})</span>
                </label>
            </div>
        `;
    }).join('');
}

export function renderComboItem(combo, orderingEnabled = true) {
    const comboItems = (combo.combo_items || []).map((comboItem) => {
        const quantity = comboItem.quantity > 1 ? `${comboItem.quantity}x ` : '';
        return `<li>${quantity}${comboItem.display_name}</li>`;
    }).join('');

    const effectivePrice = combo.combo_price ?? combo.effective_price;
    const canOrder = orderingEnabled && effectivePrice !== null && effectivePrice !== undefined;
    const priceMarkup = effectivePrice !== null && effectivePrice !== undefined
        ? `€${parseFloat(effectivePrice).toFixed(2)}`
        : 'Price to confirm';
    const orderingMarkup = canOrder ? `
        <div class="d-flex align-items-center gap-2 mt-3 js-orderable-entry">
            <input type="number" min="1" value="1" class="form-control form-control-sm menu-item-quantity" style="width: 84px;">
            <button type="button" class="btn btn-sm btn-warning add-to-cart" data-combo-id="${combo.id}" data-default-label="Add combo">
                Add combo
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
                            <span class="badge text-bg-warning">Combo</span>
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

export function renderMenuItem(item, itemIndex, orderingEnabled = true) {
    const optionGroupsMarkup = item.option_groups.map((group) => {
        return `
            <div class="mb-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <strong>${group.name}</strong>
                    <small class="text-muted">
                        ${group.required ? 'Required' : 'Optional'}
                        ${group.min_choices ? `• min ${group.min_choices}` : ''}
                        ${group.max_choices ? `• max ${group.max_choices}` : ''}
                    </small>
                </div>
                ${buildOptionControl(group, itemIndex)}
            </div>
        `;
    }).join('');

    return `
        <div class="card mb-3 menu-item" data-item-id="${item.id}">
            <div class="card-body">
                <div class="row g-3 align-items-start">
                    <div class="col-md-8">
                        <h4 class="h6 mb-1">${item.name}</h4>
                        <p class="text-muted mb-2">${item.description || ''}</p>
                        <div class="mb-3">
                            <strong>Price:</strong> €${parseFloat(item.base_price).toFixed(2)}
                        </div>
                        <div class="menu-item-options">
                            ${optionGroupsMarkup}
                        </div>
                    </div>
                    <div class="col-md-4 text-md-end">
                        ${orderingEnabled ? `
                        <div class="mb-3">
                            <label class="form-label small mb-1" for="quantity-${item.id}">Quantity</label>
                            <input type="number" class="form-control form-control-sm menu-item-quantity" id="quantity-${item.id}" value="1" min="1" />
                        </div>
                        <button type="button" class="btn btn-primary btn-sm add-to-cart" data-item-id="${item.id}">
                            Ajouter
                        </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
}

export function renderCategory(category, itemIndexStart = 0, orderingEnabled = true) {
    const items = category.items || [];
    const combos = category.combos || [];
    const itemsMarkup = items
        .map((item, index) => renderMenuItem(item, itemIndexStart + index, orderingEnabled))
        .join('');
    const combosMarkup = combos
        .map((combo) => renderComboItem(combo, orderingEnabled))
        .join('');
    const totalEntries = items.length + combos.length;

    return `
        <section class="mb-4" id="category-${category.id}">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h3 class="h6 mb-0">${category.name}</h3>
                <span class="badge bg-secondary">${totalEntries} items</span>
            </div>
            ${itemsMarkup}
            ${combosMarkup}
        </section>
    `;
}
