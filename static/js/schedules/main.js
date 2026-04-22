import * as api from './api.js';
import * as ui from './ui.js';
import { getPreset } from './presets.js';
import { getDatasetTranslations } from '../i18n.js';

let scheduleModal;
let schedulerBootstrapped = false;
let isLoadingSchedules = false;
const scheduleApp = document.getElementById('schedule-app');
const translations = getDatasetTranslations(scheduleApp, {
    editLabel: 'Modifier',
    deleteLabel: 'Supprimer',
    noWindowsDefinedLabel: 'Aucune plage définie',
    windowsCountLabel: '{count} plage(s)',
    editTimeWindowLabel: 'Modifier la plage horaire',
    addTimeWindowLabel: 'Ajouter une plage horaire',
    savingLabel: 'Enregistrement...',
    saveLabel: 'Enregistrer',
    ordersPerDurationLabel: '{count} commandes / {minutes} min',
    loadSchedulesErrorMessage: 'Impossible de charger les horaires.',
    deleteWindowConfirmation: 'Supprimer cette plage horaire ?',
    windowRemovedMessage: 'Plage horaire supprimée.',
    deleteScheduleErrorMessage: 'Impossible de supprimer cet horaire.',
    windowUpdatedMessage: 'Plage horaire mise à jour.',
    windowAddedMessage: 'Plage horaire ajoutée.',
    presetUnavailableMessage: 'Préréglage indisponible.',
});

function determineDefaultDay() {
    const today = new Date();
    const zeroBased = today.getDay(); // 0=Sunday
    return (zeroBased + 6) % 7; // convert so Monday=0, Sunday=6
}

function readPresetDay() {
    const select = document.getElementById('preset-day-select');
    if (!select) {
        return determineDefaultDay();
    }
    const parsed = parseInt(select.value, 10);
    return Number.isInteger(parsed) ? parsed : determineDefaultDay();
}

function setPresetDay(day) {
    const select = document.getElementById('preset-day-select');
    if (select) {
        select.value = day;
    }
}

async function loadSchedules() {
    if (isLoadingSchedules) {
        return;
    }
    isLoadingSchedules = true;
    try {
        const data = await api.fetchSchedules();
        const schedules = Array.isArray(data) ? data : data?.results ?? [];
        ui.renderSchedules(schedules);
    } catch (error) {
        ui.showToast(translations.loadSchedulesErrorMessage, 'danger');
    } finally {
        isLoadingSchedules = false;
    }
}

function attachCardHandlers() {
    document.getElementById('day-card-grid').addEventListener('click', (event) => {
        const target = event.target.closest('[data-day-index]');
        if (!target) return;
        const dayIndex = parseInt(target.dataset.dayIndex, 10);
        if (target.matches('.add-window-btn') || target.matches('.btn-link')) {
            setPresetDay(dayIndex);
            ui.populateForm(null, dayIndex);
            scheduleModal.show();
        }
    });

    document.getElementById('day-card-grid').addEventListener('click', (event) => {
        if (event.target.matches('.edit-window-btn')) {
            const schedule = ui.getScheduleById(event.target.dataset.schedule);
            if (!schedule) return;
            ui.populateForm(schedule, schedule.day_of_week);
            scheduleModal.show();
        }
        if (event.target.matches('.delete-window-btn')) {
            handleDelete(parseInt(event.target.dataset.schedule, 10));
        }
    });
}

async function handleDelete(scheduleId) {
    if (!confirm(translations.deleteWindowConfirmation)) {
        return;
    }
    try {
        await api.deleteSchedule(scheduleId);
        await loadSchedules();
        ui.showToast(translations.windowRemovedMessage);
    } catch (error) {
        ui.showToast(translations.deleteScheduleErrorMessage, 'danger');
    }
}

let isSubmitting = false;

function setupForm() {
    const form = document.getElementById('schedule-form');
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        ui.clearFormErrors();
        if (isSubmitting) {
            return;
        }
        isSubmitting = true;
        ui.setFormProcessing(true);
        const scheduleId = document.getElementById('schedule-id-field').value;
        const locationValue = document.getElementById('location')?.value;
        const payload = {
            day_of_week: parseInt(document.getElementById('schedule-day-field').value, 10),
            start_time: document.getElementById('start-time').value,
            end_time: document.getElementById('end-time').value,
            capacity_per_slot: parseInt(document.getElementById('capacity').value, 10),
            location: locationValue ? parseInt(locationValue, 10) : null,
        };
        try {
            if (scheduleId) {
                await api.updateSchedule(scheduleId, payload);
                ui.showToast(translations.windowUpdatedMessage);
            } else {
                await api.createSchedule(payload);
                ui.showToast(translations.windowAddedMessage);
            }
            scheduleModal.hide();
            await loadSchedules();
        } catch (error) {
            const messages = error?.payload?.detail ?? error?.payload?.non_field_errors ?? error?.payload;
            ui.showFormErrors(messages);
        } finally {
            ui.setFormProcessing(false);
            isSubmitting = false;
        }
    });
}

function bindRefresh() {
    document.getElementById('refresh-schedules').addEventListener('click', () => loadSchedules());
}

export function attachPresetHandlers() {
    const buttons = document.querySelectorAll('[data-preset]');
    buttons.forEach((button) => {
        button.addEventListener('click', () => {
            const preset = getPreset(button.dataset.preset);
            if (!preset) {
                ui.showToast(translations.presetUnavailableMessage, 'danger');
                return;
            }
            ui.clearFormErrors();
            const targetDay = readPresetDay();
            ui.populateForm(null, targetDay, {
                start_time: preset.start_time,
                end_time: preset.end_time,
                capacity_per_slot: preset.capacity_per_slot,
            });
            scheduleModal.show();
        });
    });
}

function initModal() {
    scheduleModal = new bootstrap.Modal(document.getElementById('scheduleModal'));
}

async function initializeScheduler() {
    if (schedulerBootstrapped) {
        return;
    }
    schedulerBootstrapped = true;
    ui.configureScheduleUiTranslations(translations);

    initModal();
    await loadSchedules();
    setupForm();
    attachCardHandlers();
    bindRefresh();
    attachPresetHandlers();
}

if (typeof window !== 'undefined') {
    const boot = () => initializeScheduler().catch((error) => console.error(error));
    if (document.readyState === 'loading') {
        window.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
}

export { initializeScheduler, setupForm };
