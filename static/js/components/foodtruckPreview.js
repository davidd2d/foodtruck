const defaultTranslations = {
    detailsTitle: 'Foodtruck Details',
    nameLabel: 'Name',
    descriptionLabel: 'Description',
    menuPreviewTitle: 'Menu Preview',
    noMenuItemsMessage: 'No menu items generated.',
    removeItemTitle: 'Remove item',
    addItemLabel: 'Add Item',
    newItemName: 'New Item',
};

/**
 * Render foodtruck preview
 * @param {Object} foodtruck - Foodtruck data
 * @param {string} foodtruck.name
 * @param {string} foodtruck.description
 * @param {Array} foodtruck.menu - Menu categories
 * @returns {string} HTML markup
 */
export function renderFoodtruckPreview(foodtruck, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };
    return `
        <div class="foodtruck-preview mb-4">
            <div class="row">
                <div class="col-md-6">
                    <h3 class="h4 mb-3">${labels.detailsTitle}</h3>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">${labels.nameLabel}</label>
                        <input type="text" class="form-control" id="foodtruck-name" value="${foodtruck.name}" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">${labels.descriptionLabel}</label>
                        <textarea class="form-control" id="foodtruck-description" rows="3" required>${foodtruck.description}</textarea>
                    </div>
                </div>
                <div class="col-md-6">
                    <h3 class="h4 mb-3">${labels.menuPreviewTitle}</h3>
                    <div id="menu-preview">
                        ${renderMenuPreview(foodtruck.menu, labels)}
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Render menu preview
 * @param {Array} menu - Menu categories
 * @returns {string} HTML markup
 */
function renderMenuPreview(menu, translations) {
    if (!menu || menu.length === 0) {
        return `<p class="text-muted">${translations.noMenuItemsMessage}</p>`;
    }

    return menu.map((category, categoryIndex) => `
        <div class="menu-category mb-4" data-category-index="${categoryIndex}">
            <h4 class="h5 mb-3">${category.category}</h4>
            <div class="menu-items">
                ${category.items.map((item, itemIndex) => `
                    <div class="menu-item card mb-2" data-item-index="${itemIndex}">
                        <div class="card-body py-2">
                            <div class="row align-items-center">
                                <div class="col">
                                    <input type="text" class="form-control form-control-sm" value="${item.name}" data-field="name" required>
                                </div>
                                <div class="col-auto">
                                    <div class="input-group input-group-sm">
                                        <span class="input-group-text">€</span>
                                        <input type="number" class="form-control" value="${item.price}" step="0.01" min="0.01" data-field="price" required>
                                    </div>
                                </div>
                                <div class="col-auto">
                                    <button type="button" class="btn btn-outline-danger btn-sm remove-item" title="${translations.removeItemTitle}">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
            <button type="button" class="btn btn-outline-primary btn-sm add-item" data-category-index="${categoryIndex}">
                <i class="bi bi-plus"></i> ${translations.addItemLabel}
            </button>
        </div>
    `).join('');
}

/**
 * Get edited foodtruck data from form
 * @returns {Object} Foodtruck data
 */
export function getEditedFoodtruckData() {
    const name = document.getElementById('foodtruck-name').value.trim();
    const description = document.getElementById('foodtruck-description').value.trim();

    const menu = Array.from(document.querySelectorAll('.menu-category')).map(categoryEl => {
        const categoryIndex = categoryEl.dataset.categoryIndex;
        const categoryName = categoryEl.querySelector('h4').textContent.trim();

        const items = Array.from(categoryEl.querySelectorAll('.menu-item')).map(itemEl => {
            const nameInput = itemEl.querySelector('[data-field="name"]');
            const priceInput = itemEl.querySelector('[data-field="price"]');

            return {
                name: nameInput.value.trim(),
                price: parseFloat(priceInput.value)
            };
        });

        return {
            category: categoryName,
            items: items
        };
    });

    return {
        name,
        description,
        menu
    };
}

/**
 * Add event listeners for menu editing
 * @param {Function} onDataChange - Callback when data changes
 */
export function setupMenuEditing(onDataChange, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };
    // Remove item
    document.addEventListener('click', (e) => {
        if (e.target.closest('.remove-item')) {
            const itemEl = e.target.closest('.menu-item');
            itemEl.remove();
            onDataChange();
        }
    });

    // Add item
    document.addEventListener('click', (e) => {
        if (e.target.closest('.add-item')) {
            const button = e.target.closest('.add-item');
            const categoryIndex = button.dataset.categoryIndex;
            const categoryEl = document.querySelector(`[data-category-index="${categoryIndex}"]`);
            const itemsContainer = categoryEl.querySelector('.menu-items');

            const newItemHtml = `
                <div class="menu-item card mb-2">
                    <div class="card-body py-2">
                        <div class="row align-items-center">
                            <div class="col">
                                <input type="text" class="form-control form-control-sm" value="${labels.newItemName}" data-field="name" required>
                            </div>
                            <div class="col-auto">
                                <div class="input-group input-group-sm">
                                    <span class="input-group-text">€</span>
                                    <input type="number" class="form-control" value="5.00" step="0.01" min="0.01" data-field="price" required>
                                </div>
                            </div>
                            <div class="col-auto">
                                <button type="button" class="btn btn-outline-danger btn-sm remove-item" title="${labels.removeItemTitle}">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            itemsContainer.insertAdjacentHTML('beforeend', newItemHtml);
            onDataChange();
        }
    });

    // Data change on input
    document.addEventListener('input', (e) => {
        if (e.target.matches('[data-field]')) {
            onDataChange();
        }
    });
}