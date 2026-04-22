const dashboardElement = document.getElementById('order-dashboard');

const POLL_INTERVAL_MS = 10000;

function getCsrfToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find((row) => row.startsWith('csrftoken='))
        ?.split('=')[1];

    return window.CSRF_TOKEN || cookieValue || document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
}

function getStatusActions(status, labels) {
    switch (status) {
        case 'pending':
            return [
                { status: 'confirmed', label: labels.confirmLabel, buttonClass: 'btn btn-sm btn-primary' },
                { status: 'cancelled', label: labels.cancelLabel, buttonClass: 'btn btn-sm btn-outline-danger' },
            ];
        case 'confirmed':
            return [
                { status: 'preparing', label: labels.startPreparingLabel, buttonClass: 'btn btn-sm btn-primary' },
                { status: 'cancelled', label: labels.cancelLabel, buttonClass: 'btn btn-sm btn-outline-danger' },
            ];
        case 'preparing':
            return [{ status: 'ready', label: labels.markReadyLabel, buttonClass: 'btn btn-sm btn-success' }];
        case 'ready':
            return [{ status: 'completed', label: labels.completeLabel, buttonClass: 'btn btn-sm btn-dark' }];
        default:
            return [];
    }
}

function isUrgentPickup(pickupTime) {
    if (!pickupTime) {
        return false;
    }
    const pickupDate = new Date(pickupTime);
    const delta = pickupDate.getTime() - Date.now();
    return delta >= 0 && delta <= 15 * 60 * 1000;
}

function formatPickupTime(value) {
    const date = new Date(value);
    return new Intl.DateTimeFormat(undefined, {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    }).format(date);
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function renderOrderLine(item) {
    const comboComponentsMarkup = (item.combo_components || []).length
        ? `
            <ul class="small text-muted ps-3 mt-2 mb-0">
                ${item.combo_components.map((component) => `
                    <li>
                        ${escapeHtml(String(component.quantity || 1))}x ${escapeHtml(component.item_name || component.label || '')}
                        ${(component.selected_options || []).length
                            ? `<span class="text-muted"> · ${(component.selected_options || []).map((option) => escapeHtml(option.name || '')).join(', ')}</span>`
                            : ''}
                    </li>
                `).join('')}
            </ul>
        `
        : '';

    const optionsMarkup = (item.selected_options || []).length
        ? `
            <div class="d-flex flex-wrap gap-1 mt-1">
                ${item.selected_options.map((option) => `<span class="badge rounded-pill text-bg-light border">${escapeHtml(option.name)}</span>`).join('')}
            </div>
        `
        : '';

    return `
        <li class="mb-2">
            <div class="d-flex justify-content-between gap-3">
                <div>
                    <span class="fw-medium">${escapeHtml(item.item_name)}</span>
                    <span class="text-muted">x${item.quantity}</span>
                </div>
                <span class="text-nowrap">€${item.total_price}</span>
            </div>
            ${optionsMarkup}
            ${comboComponentsMarkup}
        </li>
    `;
}

function renderOrderCard(order, labels) {
    const urgent = isUrgentPickup(order.pickup_time);
    const itemsMarkup = (order.items || []).map((item) => renderOrderLine(item)).join('');
    const actionsMarkup = getStatusActions(order.status, labels)
        .map((action) => `
            <button type="button" class="${action.buttonClass} js-order-status" data-next-status="${action.status}">
                ${action.label}
            </button>
        `)
        .join('');

    return `
        <article class="card border mb-3 dashboard-order-card ${urgent ? 'border-danger-subtle dashboard-order-card-urgent' : ''}"
                 data-order-id="${order.id}"
                 data-order-status="${order.status}"
                 data-pickup-time="${order.pickup_time}">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start gap-3 mb-2">
                    <div>
                        <div class="fw-semibold">${labels.orderLabel} #${order.id}</div>
                        <div class="small text-muted">${formatPickupTime(order.pickup_time)}</div>
                    </div>
                    <div class="text-end">
                        <div class="fw-semibold">€${order.total_price}</div>
                        ${urgent ? `<span class="badge text-bg-danger mt-1">${labels.urgentLabel}</span>` : ''}
                    </div>
                </div>
                <ul class="small mb-3 dashboard-order-lines">${itemsMarkup}</ul>
                <div class="d-flex flex-wrap gap-2">${actionsMarkup}</div>
            </div>
        </article>
    `;
}

async function fetchOrders(state) {
    const url = new URL(state.dashboardUrl, window.location.origin);
    if (state.statusFilter.value) {
        url.searchParams.set('status', state.statusFilter.value);
    }

    const response = await fetch(url.toString(), {
        headers: {
            Accept: 'application/json',
        },
        credentials: 'same-origin',
    });

    if (!response.ok) {
        throw new Error(state.labels.errorMessage);
    }

    return response.json();
}

function renderOrders(state, orders) {
    const grouped = {
        pending: [],
        confirmed: [],
        preparing: [],
        ready: [],
        completed: [],
    };

    orders.forEach((order) => {
        if (grouped[order.status]) {
            grouped[order.status].push(order);
        }
    });

    state.sections.forEach((section) => {
        const status = section.dataset.dashboardSection;
        const body = section.querySelector('[data-section-body]');
        const count = section.querySelector('[data-section-count]');
        const sectionOrders = grouped[status] || [];

        count.textContent = String(sectionOrders.length);
        body.innerHTML = sectionOrders.length
            ? sectionOrders.map((order) => renderOrderCard(order, state.labels)).join('')
            : `<p class="text-muted small mb-0" data-section-empty>${state.labels.emptyMessage}</p>`;
    });
}

async function updateOrderStatus(state, orderId, nextStatus) {
    const url = state.statusUrlTemplate.replace('/0/status/', `/${orderId}/status/`);
    const response = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ status: nextStatus }),
    });

    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || state.labels.updateErrorMessage);
    }

    return response.json();
}

function setLoading(state, isLoading) {
    state.loading.classList.toggle('d-none', !isLoading);
    state.loading.textContent = isLoading ? state.labels.loadingMessage : '';
}

function setFeedback(state, message = '') {
    state.feedback.classList.toggle('d-none', !message);
    state.feedback.textContent = message;
}

async function refreshOrders(state) {
    setLoading(state, true);
    setFeedback(state);
    try {
        const data = await fetchOrders(state);
        renderOrders(state, data);
    } catch (error) {
        setFeedback(state, error.message || state.labels.errorMessage);
    } finally {
        setLoading(state, false);
    }
}

function startPolling(state) {
    state.pollHandle = window.setInterval(() => {
        refreshOrders(state);
    }, POLL_INTERVAL_MS);
}

function stopPolling(state) {
    if (state.pollHandle) {
        window.clearInterval(state.pollHandle);
        state.pollHandle = null;
    }
}

function buildState(root) {
    return {
        root,
        dashboardUrl: root.dataset.dashboardUrl,
        statusUrlTemplate: root.dataset.statusUrlTemplate,
        statusFilter: document.getElementById('dashboard-status-filter'),
        refreshButton: document.getElementById('dashboard-refresh-button'),
        feedback: document.getElementById('dashboard-feedback'),
        loading: document.getElementById('dashboard-loading'),
        sections: Array.from(document.querySelectorAll('[data-dashboard-section]')),
        pollHandle: null,
        labels: {
            emptyMessage: root.dataset.emptyMessage,
            loadingMessage: root.dataset.loadingMessage,
            errorMessage: root.dataset.errorMessage,
            updateErrorMessage: root.dataset.updateErrorMessage,
            confirmLabel: root.dataset.confirmLabel,
            cancelLabel: root.dataset.cancelLabel,
            startPreparingLabel: root.dataset.startPreparingLabel,
            markReadyLabel: root.dataset.markReadyLabel,
            completeLabel: root.dataset.completeLabel,
            urgentLabel: root.dataset.urgentLabel,
            orderLabel: root.dataset.orderLabel,
        },
    };
}

function attachEvents(state) {
    state.refreshButton.addEventListener('click', () => refreshOrders(state));
    state.statusFilter.addEventListener('change', () => refreshOrders(state));
    state.root.addEventListener('click', async (event) => {
        const button = event.target.closest('.js-order-status');
        if (!button) {
            return;
        }

        const card = button.closest('[data-order-id]');
        const orderId = card?.dataset.orderId;
        const nextStatus = button.dataset.nextStatus;
        if (!orderId || !nextStatus) {
            return;
        }

        button.disabled = true;
        try {
            await updateOrderStatus(state, orderId, nextStatus);
            await refreshOrders(state);
        } catch (error) {
            setFeedback(state, error.message || state.labels.updateErrorMessage);
        } finally {
            button.disabled = false;
        }
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopPolling(state);
            return;
        }
        if (!state.pollHandle) {
            refreshOrders(state);
            startPolling(state);
        }
    });

    window.addEventListener('beforeunload', () => stopPolling(state));
}

function initDashboard() {
    if (!dashboardElement) {
        return;
    }
    const state = buildState(dashboardElement);
    attachEvents(state);
    refreshOrders(state);
    startPolling(state);
}

initDashboard();