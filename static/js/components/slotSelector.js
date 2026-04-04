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

export class SlotSelector {
    constructor({ selectElement, helpElement, onSelectionChange } = {}) {
        this.selectElement = selectElement;
        this.helpElement = helpElement;
        this.onSelectionChange = onSelectionChange;

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

        this.selectElement.innerHTML = `
            <option value="">Choose a pickup slot</option>
            ${slots
                .map((slot) => `
                    <option value="${slot.id}" ${slot.is_available ? '' : 'disabled'}>
                        ${formatSlotLabel(slot)}${slot.is_available ? '' : ' (unavailable)'}
                    </option>
                `)
                .join('')}
        `;
        this.selectElement.disabled = false;
        this.helpElement?.classList.remove('text-danger');
        this.helpElement?.textContent = 'Select a pickup slot before checkout.';
    }

    setLoadingState() {
        if (!this.selectElement) {
            return;
        }
        this.selectElement.disabled = true;
        this.selectElement.innerHTML = '<option value="">Loading available slots…</option>';
        this.helpElement?.classList.remove('text-danger');
        this.helpElement?.textContent = 'Loading available slots…';
    }

    setEmptyState() {
        if (!this.selectElement) {
            return;
        }
        this.selectElement.disabled = true;
        this.selectElement.innerHTML = '<option value="">No pickup slots available.</option>';
        this.helpElement?.textContent = 'No pickup slots are currently available.';
    }

    setErrorState() {
        if (!this.selectElement) {
            return;
        }

        this.selectElement.disabled = true;
        this.selectElement.innerHTML = '<option value="">Unable to load pickup slots.</option>';
        this.helpElement?.classList.add('text-danger');
        this.helpElement?.textContent = 'Unable to load pickup slots.';
    }

    reset(message = 'Select a pickup slot before checkout.') {
        if (!this.selectElement) {
            return;
        }

        this.selectElement.innerHTML = '<option value="">Choose a pickup slot</option>';
        this.selectElement.disabled = true;
        this.helpElement?.textContent = message;
        this.helpElement?.classList.remove('text-danger');
    }

    getSelectedSlotId() {
        if (!this.selectElement) {
            return null;
        }

        const value = this.selectElement.value;
        return value ? Number(value) : null;
    }
}
