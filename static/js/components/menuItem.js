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

export function renderMenuItem(item, itemIndex) {
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
                        <div class="mb-3">
                            <label class="form-label small mb-1" for="quantity-${item.id}">Quantity</label>
                            <input type="number" class="form-control form-control-sm menu-item-quantity" id="quantity-${item.id}" value="1" min="1" />
                        </div>
                        <button type="button" class="btn btn-primary btn-sm add-to-cart" data-item-id="${item.id}">
                            Add to cart
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

export function renderCategory(category, itemIndexStart = 0) {
    const itemsMarkup = category.items.map((item, index) => renderMenuItem(item, itemIndexStart + index)).join('');

    return `
        <section class="mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="h6 mb-0">${category.name}</h4>
                <span class="badge bg-secondary">${category.items.length} items</span>
            </div>
            ${itemsMarkup}
        </section>
    `;
}
