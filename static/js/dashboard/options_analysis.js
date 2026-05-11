import { fetchOptionPerformance } from './api.js';
import { initOptionsChart, updateOptionsChart } from './charts.js';

const root = document.getElementById('foodtruck-options-analysis');

function toCurrency(value, currency) {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value || 0));
}

function getLabels() {
    if (!root) {
        return {
            optionsOrdersPctLabel: 'orders include options',
            optionsTotalRevenueLabel: 'Options revenue',
            optionsAvgRevenueLabel: 'Avg. option uplift / order',
            emptyOptionsLabel: 'No option data.',
            indicatorDefinitionTitle: 'Indicator definition',
            indicatorDefinitionFallback: 'Definition is not available yet.',
            indicatorDefinitions: {},
            currency: 'EUR',
        };
    }

    return {
        optionsOrdersPctLabel: root.dataset.optionsOrdersPctLabel || 'orders include options',
        optionsTotalRevenueLabel: root.dataset.optionsTotalRevenueLabel || 'Options revenue',
        optionsAvgRevenueLabel: root.dataset.optionsAvgRevenueLabel || 'Avg. option uplift / order',
        emptyOptionsLabel: root.dataset.emptyOptionsLabel || 'No option data.',
        indicatorDefinitionTitle: root.dataset.indicatorDefinitionTitle || 'Indicator definition',
        indicatorDefinitionFallback: root.dataset.indicatorDefinitionFallback || 'Definition is not available yet.',
        indicatorDefinitions: {
            options_performance: root.dataset.indicatorDefOptionsPerformance,
        },
        currency: root.dataset.currency || 'EUR',
    };
}

function initIndicatorHelpModal(labels) {
    const titleElement = document.getElementById('dashboard-indicator-help-title');
    const bodyElement = document.getElementById('dashboard-indicator-help-body');

    if (!titleElement || !bodyElement) {
        return;
    }

    document.querySelectorAll('[data-indicator-key]').forEach((trigger) => {
        trigger.addEventListener('click', () => {
            const key = trigger.dataset.indicatorKey;
            const title = trigger.dataset.indicatorTitle || labels.indicatorDefinitionTitle;
            titleElement.textContent = title;
            bodyElement.textContent = labels.indicatorDefinitions[key] || labels.indicatorDefinitionFallback;
        });
    });
}

function renderOptionPerformance(payload, labels) {
    const data = payload?.data || {};
    const kpiContainer = document.getElementById('dashboard-options-kpis');
    const badge = document.getElementById('dashboard-options-orders-pct-badge');
    const body = document.getElementById('dashboard-options-body');

    if (!kpiContainer || !badge || !body) {
        return;
    }

    const topOptions = data.top_options || [];
    const topPayingOptions = data.top_paying_options || [];

    if (!topOptions.length && !topPayingOptions.length) {
        badge.textContent = '';
        kpiContainer.innerHTML = '';
        body.innerHTML = `<tr><td colspan="3" class="text-muted text-center py-3">${labels.emptyOptionsLabel}</td></tr>`;
        updateOptionsChart([]);
        return;
    }

    const pct = Number(data.orders_with_options_pct || 0).toFixed(1);
    badge.textContent = `${pct}% ${labels.optionsOrdersPctLabel}`;

    kpiContainer.innerHTML = `
        <div class="col-6">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.optionsTotalRevenueLabel}</div>
                <div class="slot-summary-value">${toCurrency(data.total_option_revenue || 0, labels.currency)}</div>
            </div>
        </div>
        <div class="col-6">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.optionsAvgRevenueLabel}</div>
                <div class="slot-summary-value">${toCurrency(data.avg_option_revenue_per_order || 0, labels.currency)}</div>
            </div>
        </div>
    `;

    updateOptionsChart(topPayingOptions.length ? topPayingOptions : topOptions);

    body.innerHTML = topOptions.map((row) => `
        <tr>
            <td>${row.option_name}</td>
            <td class="text-end">${row.selection_count}</td>
            <td class="text-end">${toCurrency(row.total_revenue, labels.currency)}</td>
        </tr>
    `).join('');
}

async function loadOptions(range, labels, displayMode) {
    const payload = await fetchOptionPerformance(root.dataset.optionsUrl, range, 10, null, displayMode);
    renderOptionPerformance(payload, labels);
}

function init() {
    if (!root) {
        return;
    }

    const labels = getLabels();
    const rangeSelect = document.getElementById('options-range-select');
    const displayModeSelect = document.getElementById('options-display-mode-select');
    const optionsCanvas = document.getElementById('dashboard-options-chart');

    initOptionsChart(optionsCanvas, labels.optionsTotalRevenueLabel);
    initIndicatorHelpModal(labels);

    let activeRange = root.dataset.activeRange || '7d';
    let activeDisplayMode = displayModeSelect?.value || root.dataset.displayMode || 'tax_included';

    const refresh = () => loadOptions(activeRange, labels, activeDisplayMode);

    refresh().catch(() => {
        renderOptionPerformance({ data: {} }, labels);
    });

    rangeSelect?.addEventListener('change', () => {
        activeRange = rangeSelect.value;
        refresh().catch(() => {});
    });

    displayModeSelect?.addEventListener('change', () => {
        activeDisplayMode = displayModeSelect.value;
        refresh().catch(() => {});
    });
}

init();
