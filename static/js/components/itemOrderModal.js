import { interpolate } from '../i18n.js';

const defaultTranslations = {
    requiredLabel: 'Required',
    optionalLabel: 'Optional',
    minLabel: 'min',
    maxLabel: 'max',
    quantityLabel: 'Quantity',
    noCustomizationOptionsMessage: 'No customization options for this item.',
    selectAtLeastOptionsMessage: 'Please choose at least {count} option(s) for {group}.',
    selectAtMostOptionsMessage: 'You can select up to {count} option(s) for {group}.',
};

function buildOptionControl(group, itemId) {
    const inputName = `group-${group.id}-${itemId}`;
    const isRadio = Number(group.max_choices || 0) === 1 && Number(group.min_choices || 0) <= 1;

    return (group.options || []).map((option) => {
        const inputType = isRadio ? 'radio' : 'checkbox';
        const optionId = `item-${itemId}-option-${option.id}`;
        const priceModifier = Number(option.price_modifier || 0);
        const itemTaxRate = Number(group.item_tax_rate || 0);
        const displayModifier = group.prices_include_tax ? priceModifier * (1 + itemTaxRate) : priceModifier;
        return `
            <div class="form-check mb-2">
                <input
                    class="form-check-input menu-option"
                    type="${inputType}"
                    name="${inputName}"
                    id="${optionId}"
                    data-option-id="${option.id}"
                    value="${option.id}"
                />
                <label class="form-check-label" for="${optionId}">
                    ${option.name} <span class="text-muted">(+€${displayModifier.toFixed(2)})</span>
                </label>
            </div>
        `;
    }).join('');
}

export function renderItemOrderModalBody(item, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };
    const optionGroups = item.option_groups || [];

    if (!optionGroups.length) {
        return `
            <p class="text-muted mb-0">${labels.noCustomizationOptionsMessage}</p>
        `;
    }

    return optionGroups.map((group) => `
        <section class="border rounded p-3 mb-3">
            <div class="d-flex justify-content-between align-items-center gap-3 mb-2">
                <strong>${group.name}</strong>
                <small class="text-muted text-end">
                    ${group.required ? labels.requiredLabel : labels.optionalLabel}
                    ${group.min_choices ? `• ${labels.minLabel} ${group.min_choices}` : ''}
                    ${group.max_choices ? `• ${labels.maxLabel} ${group.max_choices}` : ''}
                </small>
            </div>
            ${buildOptionControl({ ...group, item_tax_rate: item.tax_rate, prices_include_tax: item.prices_include_tax }, item.id)}
        </section>
    `).join('');
}

export function getSelectedOptionIds(container) {
    if (!container) {
        return [];
    }

    return Array.from(container.querySelectorAll('.menu-option:checked')).map((input) => Number(input.dataset.optionId));
}

export function validateItemSelection(item, selectedOptionIds, translations = {}) {
    const labels = { ...defaultTranslations, ...translations };
    const optionGroups = item.option_groups || [];
    const selectedIds = new Set((selectedOptionIds || []).map((optionId) => Number(optionId)));

    for (const group of optionGroups) {
        const groupOptionIds = new Set((group.options || []).map((option) => Number(option.id)));
        const selectedCount = Array.from(selectedIds).filter((optionId) => groupOptionIds.has(optionId)).length;
        const minChoices = Number(group.min_choices || (group.required ? 1 : 0));
        const maxChoices = Number(group.max_choices || 0);

        if (minChoices && selectedCount < minChoices) {
            return {
                valid: false,
                message: interpolate(labels.selectAtLeastOptionsMessage, {
                    count: minChoices,
                    group: group.name,
                }),
            };
        }

        if (maxChoices && selectedCount > maxChoices) {
            return {
                valid: false,
                message: interpolate(labels.selectAtMostOptionsMessage, {
                    count: maxChoices,
                    group: group.name,
                }),
            };
        }
    }

    return { valid: true, message: '' };
}