class SlotManager {
    constructor(appSelector) {
        this.app = document.querySelector(appSelector);
        if (!this.app) {
            return;
        }

        this.foodtruckSlug = this.app.dataset.foodtruckSlug;
        this.foodtruckId = this.app.dataset.foodtruckId;
        this.emptyMessage = this.app.dataset.emptyMessage || 'No slots configured yet.';
        this.loadingMessage = this.app.dataset.loadingMessage || 'Loading slots...';
        this.editLabel = this.app.dataset.editLabel || 'Edit slot';
        this.createLabel = this.app.dataset.createLabel || 'Create pickup slot';

        this.tableBody = this.app.querySelector('#slot-table-body');
        this.modal = new bootstrap.Modal(document.querySelector('#slotModal'));
        this.form = document.querySelector('#slot-form');
        this.csrfToken = window.CSRF_TOKEN;

        this.bind();
        this.loadSlots();
    }

    bind() {
        this.form.addEventListener('submit', (event) => {
            event.preventDefault();
            this.saveSlot();
        });

        const createButton = this.app.querySelector('[data-action="create"]');
        if (createButton) {
            createButton.addEventListener('click', () => {
                this.resetForm();
                document.getElementById('slotModalLabel').textContent = this.createLabel;
            });
        }

        this.tableBody.addEventListener('click', (event) => {
            const button = event.target.closest('button[data-action]');
            if (!button) {
                return;
            }
            const action = button.dataset.action;
            const slotId = button.dataset.slotId;

            if (action === 'edit') {
                const slotData = JSON.parse(decodeURIComponent(button.dataset.slot));
                this.fillForm(slotData);
            } else if (action === 'delete') {
                this.deleteSlot(slotId);
            }
        });

        document.getElementById('slotModal').addEventListener('hidden.bs.modal', () => {
            this.resetForm();
        });
    }

    async loadSlots() {
        const placeholder = document.getElementById('slot-loading-placeholder');
        if (placeholder) {
            placeholder.innerHTML = `<div class="spinner-border spinner-border-sm me-2" role="status"><span class="visually-hidden">Loading</span></div>${this.loadingMessage}`;
        }

        try {
            const response = await fetch(`/api/pickup-slots/?foodtruck_slug=${this.foodtruckSlug}`, {
                headers: { 'Accept': 'application/json' },
                credentials: 'include',
            });
            if (!response.ok) {
                throw new Error('Unable to load slots');
            }
            const slots = await response.json();
            this.renderSlots(slots);
        } catch (error) {
            this.tableBody.innerHTML = `<tr><td colspan="7" class="text-danger text-center">${error.message}</td></tr>`;
        }
    }

    renderSlots(slots) {
        if (!slots.length) {
            this.tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">${this.emptyMessage}</td></tr>`;
            return;
        }

        this.tableBody.innerHTML = slots.map(slot => this.buildRow(slot)).join('');
    }

    buildRow(slot) {
        const status = slot.is_available ? 'Available' : 'Closed';
        const start = this.formatParis(slot.start_time);
        const end = this.formatParis(slot.end_time);
        const payload = encodeURIComponent(JSON.stringify(slot));

        return `
            <tr>
                <td>${start}</td>
                <td>${end}</td>
                <td>${slot.capacity}</td>
                <td>${slot.remaining_capacity}</td>
                <td>${slot.current_bookings}</td>
                <td>${status}</td>
                <td class="text-end actions">
                    <button type="button" class="btn btn-sm btn-outline-primary me-2" data-action="edit" data-slot-id="${slot.id}" data-slot="${payload}">
                        Edit
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger" data-action="delete" data-slot-id="${slot.id}">
                        Delete
                    </button>
                </td>
            </tr>
        `;
    }

    formatParis(value) {
        if (!value) {
            return '-';
        }
        const formatter = new Intl.DateTimeFormat('fr-FR', {
            timeZone: 'Europe/Paris',
            dateStyle: 'medium',
            timeStyle: 'short',
        });
        return formatter.format(new Date(value));
    }

    async saveSlot() {
        const slotId = document.getElementById('slot-id').value;
        const payload = {
            food_truck_id: this.foodtruckId,
            start_time: this.toISOString(document.getElementById('slot-start').value),
            end_time: this.toISOString(document.getElementById('slot-end').value),
            capacity: Number(document.getElementById('slot-capacity').value),
        };

        const url = slotId ? `/api/pickup-slots/${slotId}/` : '/api/pickup-slots/';
        const method = slotId ? 'PATCH' : 'POST';

        try {
            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || JSON.stringify(error));
            }

            this.modal.hide();
            this.loadSlots();
        } catch (error) {
            const errorContainer = document.getElementById('slot-form-error');
            errorContainer.textContent = error.message;
            errorContainer.classList.remove('d-none');
        }
    }

    toISOString(value) {
        if (!value) {
            return null;
        }
        const [date, time] = value.split('T');
        return `${date}T${time}:00+02:00`;
    }

    fillForm(slot) {
        document.getElementById('slot-id').value = slot.id;
        document.getElementById('slot-start').value = this.toParisInput(slot.start_time);
        document.getElementById('slot-end').value = this.toParisInput(slot.end_time);
        document.getElementById('slot-capacity').value = slot.capacity;
        document.getElementById('slotModalLabel').textContent = this.editLabel;
        this.modal.show();
    }

    toParisInput(value) {
        if (!value) {
            return '';
        }
        const dt = new Date(value);
        const formatter = new Intl.DateTimeFormat('sv-SE', {
            timeZone: 'Europe/Paris',
            hour12: false,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
        const parts = formatter.formatToParts(dt);
        const map = {};
        parts.forEach(part => {
            if (part.type !== 'literal') {
                map[part.type] = part.value;
            }
        });
        return `${map.year}-${map.month}-${map.day}T${map.hour}:${map.minute}`;
    }

    resetForm() {
        this.form.reset();
        this.form.querySelector('#slot-id').value = '';
        document.getElementById('slotModalLabel').textContent = this.createLabel;
        document.getElementById('slot-form-error').classList.add('d-none');
    }

    async deleteSlot(slotId) {
        if (!confirm('Are you sure you want to delete this slot?')) {
            return;
        }

        try {
            const response = await fetch(`/api/pickup-slots/${slotId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                },
            });

            if (!response.ok) {
                throw new Error('Unable to delete slot.');
            }

            this.loadSlots();
        } catch (error) {
            alert(error.message);
        }
    }
}


document.addEventListener('DOMContentLoaded', () => {
    new SlotManager('#slot-manager-app');
});
