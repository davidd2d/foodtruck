function formatSlotLabel(slot) {
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
    })}`;
}

function formatSlotTime(slot) {
    const start = new Date(slot.start_time);
    return start.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
    });
}

export function buildRecommendedMessage(slot) {
    if (!slot) {
        return 'Recommended pickup time selected automatically.';
    }

    const now = new Date();
    const start = new Date(slot.start_time);
    const end = new Date(slot.end_time);

    if (start <= now && end > now) {
        return 'Retrait conseillé : dès maintenant';
    }

    return `Prochain créneau disponible : ${formatSlotTime(slot)}`;
}

export class SlotSelector {
    constructor({ selectElement, helpElement, onSelectionChange } = {}) {
        this.selectElement = selectElement;
        this.helpElement = helpElement;
        this.onSelectionChange = onSelectionChange;
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

        const defaultSlot = slots.find((slot) => slot.is_available && this.defaultSlotId === slot.id);

        this.selectElement.innerHTML = `
            <option value="">Choose a pickup slot</option>
            ${slots
                .map((slot) => `
                    <option value="${slot.id}" ${slot.is_available ? '' : 'disabled'} ${defaultSlot && defaultSlot.id === slot.id ? 'selected' : ''}>
                        ${formatSlotLabel(slot)}${slot.is_available ? '' : ' (unavailable)'}
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
            this.helpElement.textContent = buildRecommendedMessage(defaultSlot);
        }
    }

    setLoadingState() {
        if (!this.selectElement) {
            return;
        }
        this.selectElement.disabled = true;
        this.selectElement.innerHTML = '<option value="">Loading available slots…</option>';
        if (this.helpElement) {
            this.helpElement.classList.remove('text-danger');
            this.helpElement.textContent = 'Loading available slots…';
        }
    }

    setEmptyState() {
        if (!this.selectElement) {
            return;
        }
        this.selectElement.disabled = true;
        this.selectElement.innerHTML = '<option value="">No pickup slots available.</option>';
        if (this.helpElement) {
            this.helpElement.textContent = 'No pickup slots are currently available.';
        }
    }

    setErrorState() {
        if (!this.selectElement) {
            return;
        }

        this.selectElement.disabled = true;
        this.selectElement.innerHTML = '<option value="">Unable to load pickup slots.</option>';
        if (this.helpElement) {
            this.helpElement.classList.add('text-danger');
            this.helpElement.textContent = 'Unable to load pickup slots.';
        }
    }

    reset(message = 'Select a pickup slot before checkout.') {
        if (!this.selectElement) {
            return;
        }

        this.selectElement.innerHTML = '<option value="">Choose a pickup slot</option>';
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
