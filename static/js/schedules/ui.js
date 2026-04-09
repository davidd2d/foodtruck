const scheduleStore = new Map();
const TOTAL_DAYS = 7;

function formatTime(value) {
    if (!value) {
        return '';
    }
    return value.substring(0, 5);
}

function createWindowElement(schedule) {
    const wrapper = document.createElement('div');
    wrapper.className = 'schedule-window d-flex justify-content-between align-items-start mb-3';
    wrapper.dataset.scheduleId = schedule.id;
    wrapper.dataset.dayIndex = schedule.day_of_week;

    const left = document.createElement('div');
    const range = document.createElement('strong');
    range.className = 'd-block mb-1';
    let rangeText = `${formatTime(schedule.start_time)} → ${formatTime(schedule.end_time)}`;
    if (schedule.location_label) {
        rangeText += ` ${schedule.location_label}`;
    }
    range.textContent = rangeText;
    const capacity = document.createElement('small');
    capacity.className = 'text-muted d-block';
    capacity.textContent = `${schedule.capacity_per_slot} orders / ${schedule.slot_duration_minutes ?? 10} min`; // fallback
    left.appendChild(range);
    left.appendChild(capacity);

    const actions = document.createElement('div');
    actions.className = 'd-flex gap-2';

    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'btn btn-sm btn-outline-secondary edit-window-btn';
    edit.textContent = 'Edit';
    edit.dataset.schedule = schedule.id;

    const del = document.createElement('button');
    del.type = 'button';
    del.className = 'btn btn-sm btn-outline-danger delete-window-btn';
    del.textContent = 'Delete';
    del.dataset.schedule = schedule.id;

    actions.appendChild(edit);
    actions.appendChild(del);

    wrapper.appendChild(left);
    wrapper.appendChild(actions);
    return wrapper;
}

export function renderSchedules(schedules) {
    scheduleStore.clear();
    const grouped = new Map();

    schedules.forEach((schedule) => {
        scheduleStore.set(String(schedule.id), schedule);
        if (!grouped.has(schedule.day_of_week)) {
            grouped.set(schedule.day_of_week, []);
        }
        grouped.get(schedule.day_of_week).push(schedule);
    });

    for (let day = 0; day < TOTAL_DAYS; day++) {
        const listBox = document.getElementById(`schedule-windows-${day}`);
        const emptyState = document.getElementById(`empty-state-${day}`);
        const summary = document.getElementById(`day-summary-${day}`);
        if (!listBox || !summary) {
            continue;
        }
        const windows = grouped.get(day) ?? [];
        listBox.innerHTML = '';
        if (windows.length === 0) {
            emptyState?.classList.remove('d-none');
            summary.textContent = 'No windows defined';
        } else {
            emptyState?.classList.add('d-none');
            windows.sort((a, b) => a.start_time.localeCompare(b.start_time));
            windows.forEach((window) => {
                listBox.appendChild(createWindowElement(window));
            });
            summary.textContent = `${windows.length} window(s)`;
        }
    }
}

export function getScheduleById(scheduleId) {
    return scheduleStore.get(String(scheduleId));
}

export function showToast(message, variant = 'success') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) return;

    const toastElement = document.createElement('div');
    toastElement.className = `toast align-items-center text-bg-${variant} border-0 show`;
    toastElement.setAttribute('role', 'alert');
    toastElement.setAttribute('aria-live', 'assertive');
    toastElement.setAttribute('aria-atomic', 'true');
    toastElement.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    toastContainer.appendChild(toastElement);
    setTimeout(() => {
        toastElement.remove();
    }, 4000);
}

export function clearFormErrors() {
    const alert = document.getElementById('schedule-form-errors');
    if (alert) {
        alert.classList.add('d-none');
        alert.textContent = '';
    }
}

export function showFormErrors(messages) {
    const alert = document.getElementById('schedule-form-errors');
    if (!alert) return;
    alert.classList.remove('d-none');
    const text = Array.isArray(messages)
        ? messages.join(', ')
        : typeof messages === 'string'
            ? messages
            : JSON.stringify(messages);
    alert.textContent = text;
}

export function populateForm(schedule, dayIndex, overrides = {}) {
    const modalTitle = document.getElementById('scheduleModalLabel');
    const scheduleIdField = document.getElementById('schedule-id-field');
    const dayField = document.getElementById('schedule-day-field');
    const startTime = document.getElementById('start-time');
    const endTime = document.getElementById('end-time');
    const capacity = document.getElementById('capacity');
    const locationField = document.getElementById('location');

    if (schedule) {
        modalTitle.textContent = 'Edit time window';
        scheduleIdField.value = schedule.id;
        dayField.value = schedule.day_of_week;
        startTime.value = schedule.start_time;
        endTime.value = schedule.end_time;
        capacity.value = schedule.capacity_per_slot;
        if (locationField) {
            locationField.value = schedule.location ?? '';
        }
    } else {
        modalTitle.textContent = 'Add time window';
        scheduleIdField.value = '';
        dayField.value = dayIndex;
        startTime.value = '';
        endTime.value = '';
        capacity.value = '';
        if (locationField) {
            locationField.value = locationField.options[0]?.value || '';
        }
    }

    if (overrides.start_time) startTime.value = overrides.start_time;
    if (overrides.end_time) endTime.value = overrides.end_time;
    if (overrides.capacity_per_slot) capacity.value = overrides.capacity_per_slot;

    if (overrides.day !== undefined) {
        dayField.value = overrides.day;
    }
}

export function setFormProcessing(isProcessing) {
    const submit = document.getElementById('schedule-submit-btn');
    if (submit) {
        submit.disabled = isProcessing;
        submit.textContent = isProcessing ? 'Saving…' : 'Save';
    }
}
