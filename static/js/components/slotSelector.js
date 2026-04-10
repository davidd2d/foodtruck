import { interpolate } from '../i18n.js';

const defaultTranslations = {
    recommendedPickupMessage: 'Recommended pickup time selected automatically.',
    pickupNowMessage: 'Recommended pickup: right now',
    nextPickupMessage: 'Next available slot: {time}',
    choosePickupSlotLabel: 'Choose a pickup slot',
    unavailableSuffix: 'unavailable',
    loadingSlotsLabel: 'Loading available slots...',
    noSlotsOptionLabel: 'No pickup slots available.',
    noSlotsMessage: 'No pickup slots are currently available.',
    loadSlotsErrorLabel: 'Unable to load pickup slots.',
    selectSlotMessage: 'Select a pickup slot before checkout.',
};

function formatSlotLabel(slot, translations) {
    const start = new Date(slot.start_time);
    const end = new Date(slot.end_time);

    return `${start.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    })} – ${end.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
    })}${slot.is_available ? '' : ` (${translations.unavailableSuffix})`}`;
}

function formatSlotTime(slot) {
    const start = new Date(slot.start_time);
    return start.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
    });
}

export function buildRecommendedMessage(slot, customTranslations = {}) {
    const translations = { ...defaultTranslations, ...customTranslations };

    if (!slot) {
        return translations.recommendedPickupMessage;
    }

    const now = new Date();
    const start = new Date(slot.start_time);
    const end = new Date(slot.end_time);

    if (start <= now && end > now) {
        return translations.pickupNowMessage;
    }

    return interpolate(translations.nextPickupMessage, { time: formatSlotTime(slot) });
}

export class SlotSelector {
    constructor({ selectElement, helpElement, onSelectionChange, translations = {} } = {}) {
        this.selectElement = selectElement;
        this.helpElement = helpElement;
        this.onSelectionChange = onSelectionChange;
        this.translations = { ...defaultTranslations, ...translations };
        this.defaultSlotId = selectElement?.dataset?.defaultSlot ? parseInt(selectElement.dataset.defaultSlot, 10) : null;

        this.selectElement?.addEventListener('change', () => {
            if (typeof this.onSelectionChange === 'function') {
                this.onSelectionChange(this.getSelectedSlotId());
            }
        });
    }

    async loadSlots(fetcher, foodtruckSlug) {
        if (!this.selectElement || !foodtruckSlug) {
            return [];
        }

        this.setLoadingState();

        try {
            const slots = await fetcher(foodtruckSlug);
            if (!slots.length) {
                this.setEmptyState();
                return [];
            }
            this.populateOptions(slots);
            return slots;
        } catch (error) {
            this.setErrorState();
            throw error;
        }
    }

    populateOptions(slots) {
        if (!this.selectElement) {
            return;
        }

        const defaultSlot = slots.find((slot) => slot.is_available && this.defaultSlotId === slot.id)
            || slots.find((slot) => slot.is_available)
            || null;

        this.selectElement.innerHTML = `
            <option value="">${this.translations.choosePickupSlotLabel}</option>
            ${slots
                .map((slot) => `
                    <option value="${slot.id}" ${slot.is_available ? '' : 'disabled'} ${defaultSlot && defaultSlot.id === slot.id ? 'selected' : ''}>
                        ${formatSlotLabel(slot, this.translations)}
                    </option>
                `)
                .join('')}
        `;
        this.selectElement.disabled = false;

        if (defaultSlot && typeof this.onSelectionChange === 'function') {
            this.onSelectionChange(defaultSlot.id);
        }

        if (this.helpElement) {
            this.helpElement.classList.remove('text-danger');
            this.helpElement.textContent = defaultSlot
                ? buildRecommendedMessage(defaultSlot, this.translations)
                : this.translations.noSlotsMessage;
        }
    }

    setLoadingState() {
        if (!this.selectElement) {
            return;
        }
        this.selectElement.disabled = true;
        this.selectElement.innerHTML = `<option value="">${this.translations.loadingSlotsLabel}</option>`;
        if (this.helpElement) {
            this.helpElement.classList.remove('text-danger');
            this.helpElement.textContent = this.translations.loadingSlotsLabel;
        }
    }

    setEmptyState() {
        if (!this.selectElement) {
            return;
        }
        this.selectElement.disabled = true;
        this.selectElement.innerHTML = `<option value="">${this.translations.noSlotsOptionLabel}</option>`;
        if (this.helpElement) {
            this.helpElement.textContent = this.translations.noSlotsMessage;
        }
    }

    setErrorState() {
        if (!this.selectElement) {
            return;
        }

        this.selectElement.disabled = true;
        this.selectElement.innerHTML = `<option value="">${this.translations.loadSlotsErrorLabel}</option>`;
        if (this.helpElement) {
            this.helpElement.classList.add('text-danger');
            this.helpElement.textContent = this.translations.loadSlotsErrorLabel;
        }
    }

    reset(message = this.translations.selectSlotMessage) {
        if (!this.selectElement) {
            return;
        }

        this.selectElement.innerHTML = `<option value="">${this.translations.choosePickupSlotLabel}</option>`;
        this.selectElement.disabled = true;
        if (this.helpElement) {
            this.helpElement.textContent = message;
            this.helpElement.classList.remove('text-danger');
        }
    }

    getSelectedSlotId() {
        if (!this.selectElement) {
            return null;
        }

        const value = this.selectElement.value;
        return value ? Number(value) : null;
    }
}
