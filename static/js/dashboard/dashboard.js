import { fetchBusinessIntelligence, fetchKpis, fetchMenuPerformance, fetchOrders, fetchRevenue, fetchMenuCategoryPerformance } from './api.js';
import { initMenuCategoryChart, initRevenueChart, updateMenuCategoryChart, updateRevenueChart, initOptionsChart, updateOptionsChart } from './charts.js';
import { loadSlotAnalytics } from './slots.js';
import { applyCategoryChipActiveState, collectCategoryChips } from '../shared/categoryFilter.js';

const root = document.getElementById('foodtruck-dashboard');
const AUTO_REFRESH_MS = 10000;

function getLabels() {
    if (!root) {
        return {
            chartRevenueLabel: 'Revenue',
            chartMenuCategoryLabel: 'Revenue by category',
            emptyOrdersLabel: 'No paid orders in this range.',
            emptyMenuLabel: 'No menu performance data.',
            emptyMenuCategoriesLabel: 'No category performance data.',
            emptySlotsLabel: 'No slot data.',
            emptyInsightsLabel: 'No slot insights available.',
            emptyRecommendationsLabel: 'No slot recommendations available.',
            emptyHourlyLabel: 'No hourly performance data.',
            insightsMoreLabel: 'more slots',
            recommendationsMoreLabel: 'more recommendations',
            demandLabel: 'demand',
            ordersLabel: 'orders',
            slotActiveLabel: 'Active slots',
            slotAverageUtilizationLabel: 'Avg utilization',
            slotRevenueLabel: 'Slot revenue',
            slotUnderperformingLabel: 'Underperforming',
            slotOptimalLabel: 'Optimal',
            slotSaturatedLabel: 'Saturated',
            slotTopSlotLabel: 'Best slot',
            optionsOrdersPctLabel: 'orders include options',
            optionsTotalRevenueLabel: 'Options revenue',
            optionsAvgRevenueLabel: 'Avg. option uplift / order',
            emptyOptionsLabel: 'No option data.',
            weekdayShortLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datePlaceholderLabel: 'N/A',
            currency: 'EUR',
            biPredictedRevenueLabel: 'Revenu predit (J+1)',
            biConfidenceLabel: 'Confiance',
            biSuggestedEventsLabel: 'Opportunites evenementielles suggerees',
            biEmptySpotsLabel: 'Aucune recommandation d emplacement pour le moment.',
            biScoreLabel: 'Score',
            biLatLabel: 'Lat',
            biLngLabel: 'Lng',
            biEmptyPricingLabel: 'Aucune suggestion tarifaire pour le moment.',
            biPredictedLabel: 'Predit',
            biEmptyEventsLabel: 'Aucune opportunite evenementielle detectee.',
            indicatorDefinitionTitle: 'Indicator definition',
            indicatorDefinitionFallback: 'Definition is not available yet.',
            indicatorDefinitions: {},
        };
    }

    return {
        chartRevenueLabel: root.dataset.chartRevenueLabel || 'Revenue',
        chartMenuCategoryLabel: root.dataset.chartMenuCategoryLabel || 'Revenue by category',
        emptyOrdersLabel: root.dataset.emptyOrdersLabel || 'No paid orders in this range.',
        emptyMenuLabel: root.dataset.emptyMenuLabel || 'No menu performance data.',
        emptyMenuCategoriesLabel: root.dataset.emptyMenuCategoriesLabel || 'No category performance data.',
        emptySlotsLabel: root.dataset.emptySlotsLabel || 'No slot data.',
        emptyInsightsLabel: root.dataset.emptyInsightsLabel || 'No slot insights available.',
        emptyRecommendationsLabel: root.dataset.emptyRecommendationsLabel || 'No slot recommendations available.',
        emptyHourlyLabel: root.dataset.emptyHourlyLabel || 'No hourly performance data.',
        insightsMoreLabel: root.dataset.insightsMoreLabel || 'more slots',
        recommendationsMoreLabel: root.dataset.recommendationsMoreLabel || 'more recommendations',
        demandLabel: root.dataset.demandLabel || 'demand',
        ordersLabel: root.dataset.ordersLabel || 'orders',
        slotActiveLabel: root.dataset.slotActiveLabel || 'Active slots',
        slotAverageUtilizationLabel: root.dataset.slotAverageUtilizationLabel || 'Avg utilization',
        slotRevenueLabel: root.dataset.slotRevenueLabel || 'Slot revenue',
        slotUnderperformingLabel: root.dataset.slotUnderperformingLabel || 'Underperforming',
        slotOptimalLabel: root.dataset.slotOptimalLabel || 'Optimal',
        slotSaturatedLabel: root.dataset.slotSaturatedLabel || 'Saturated',
        slotTopSlotLabel: root.dataset.slotTopSlotLabel || 'Best slot',
        optionsOrdersPctLabel: root.dataset.optionsOrdersPctLabel || 'orders include options',
        optionsTotalRevenueLabel: root.dataset.optionsTotalRevenueLabel || 'Options revenue',
        optionsAvgRevenueLabel: root.dataset.optionsAvgRevenueLabel || 'Avg. option uplift / order',
        emptyOptionsLabel: root.dataset.emptyOptionsLabel || 'No option data.',
        weekdayShortLabels: (root.dataset.weekdayShortLabels || 'Mon,Tue,Wed,Thu,Fri,Sat,Sun').split(','),
        datePlaceholderLabel: root.dataset.datePlaceholderLabel || 'N/A',
        currency: root.dataset.currency || 'EUR',
        biPredictedRevenueLabel: root.dataset.biPredictedRevenueLabel || 'Revenu predit (J+1)',
        biConfidenceLabel: root.dataset.biConfidenceLabel || 'Confiance',
        biSuggestedEventsLabel: root.dataset.biSuggestedEventsLabel || 'Opportunites evenementielles suggerees',
        biEmptySpotsLabel: root.dataset.biEmptySpotsLabel || 'Aucune recommandation d emplacement pour le moment.',
        biScoreLabel: root.dataset.biScoreLabel || 'Score',
        biLatLabel: root.dataset.biLatLabel || 'Lat',
        biLngLabel: root.dataset.biLngLabel || 'Lng',
        biEmptyPricingLabel: root.dataset.biEmptyPricingLabel || 'Aucune suggestion tarifaire pour le moment.',
        biPredictedLabel: root.dataset.biPredictedLabel || 'Predit',
        biEmptyEventsLabel: root.dataset.biEmptyEventsLabel || 'Aucune opportunite evenementielle detectee.',
        indicatorDefinitionTitle: root.dataset.indicatorDefinitionTitle || 'Indicator definition',
        indicatorDefinitionFallback: root.dataset.indicatorDefinitionFallback || 'Definition is not available yet.',
        indicatorDefinitions: {
            total_orders: root.dataset.indicatorDefTotalOrders,
            total_revenue: root.dataset.indicatorDefTotalRevenue,
            average_order_value: root.dataset.indicatorDefAverageOrderValue,
            options_revenue_pct: root.dataset.indicatorDefOptionsRevenuePct,
            revenue_trend: root.dataset.indicatorDefRevenueTrend,
            top_menu_performance: root.dataset.indicatorDefTopMenuPerformance,
            recent_paid_orders: root.dataset.indicatorDefRecentPaidOrders,
            slot_utilization_revenue: root.dataset.indicatorDefSlotUtilizationRevenue,
            options_performance: root.dataset.indicatorDefOptionsPerformance,
            slot_heatmap: root.dataset.indicatorDefSlotHeatmap,
            slot_insights: root.dataset.indicatorDefSlotInsights,
            slot_recommendations: root.dataset.indicatorDefSlotRecommendations,
        },
    };
}

function toCurrency(value, currency) {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value || 0));
}

function initIndicatorHelpModal(labels) {
    const modalElement = document.getElementById('dashboard-indicator-help-modal');
    const titleElement = document.getElementById('dashboard-indicator-help-title');
    const bodyElement = document.getElementById('dashboard-indicator-help-body');

    if (!modalElement || !titleElement || !bodyElement) {
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

function toPercent(value) {
    return `${Number(value || 0).toFixed(2)}%`;
}

function formatDateTime(value, fallbackLabel) {
    if (!value) {
        return fallbackLabel;
    }
    return new Date(value).toLocaleString();
}

function renderKpis(payload, labels) {
    const data = payload?.data || {};
    document.getElementById('kpi-total-orders').textContent = String(data.total_orders || 0);
    document.getElementById('kpi-total-revenue').textContent = toCurrency(data.total_revenue, labels.currency);
    document.getElementById('kpi-average-order-value').textContent = toCurrency(data.average_order_value, labels.currency);
    document.getElementById('kpi-options-revenue-rate').textContent = toPercent(data.options_revenue_pct);
}

function renderOrders(payload, labels) {
    const body = document.getElementById('dashboard-orders-body');
    const orders = payload?.data || [];

    if (!orders.length) {
        body.innerHTML = `<tr><td colspan="5" class="text-muted text-center py-3">${labels.emptyOrdersLabel}</td></tr>`;
        return;
    }

    body.innerHTML = orders.map((order) => `
        <tr>
            <td>#${order.id}</td>
            <td><span class="badge text-bg-secondary text-capitalize">${order.status}</span></td>
            <td>${formatDateTime(order.paid_at, labels.datePlaceholderLabel)}</td>
            <td>${formatDateTime(order.pickup_time, labels.datePlaceholderLabel)}</td>
            <td class="text-end">${toCurrency(order.total_amount, labels.currency)}</td>
        </tr>
    `).join('');
}

function renderMenuPerformance(payload, labels) {
    const body = document.getElementById('dashboard-menu-body');
    const items = payload?.data || [];

    if (!items.length) {
        body.innerHTML = `<tr><td colspan="3" class="text-muted text-center py-3">${labels.emptyMenuLabel}</td></tr>`;
        return;
    }

    body.innerHTML = items.map((item) => `
        <tr>
            <td>${item.item_name}</td>
            <td class="text-end">${item.quantity_sold}</td>
            <td class="text-end">${toCurrency(item.revenue_generated, labels.currency)}</td>
        </tr>
    `).join('');
}

function renderMenuCategoryPerformance(payload, labels) {
    const rows = payload?.data || [];
    if (!rows.length) {
        updateMenuCategoryChart([]);
        return;
    }
    updateMenuCategoryChart(rows);
}

function renderOptionPerformance(payload, labels) {
    const data = payload?.data || {};
    const kpiContainer = document.getElementById('dashboard-options-kpis');
    const badge = document.getElementById('dashboard-options-orders-pct-badge');
    const body = document.getElementById('dashboard-options-body');

    if (!kpiContainer || !body) {
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

function renderBusinessIntelligence(payload, labels) {
    const data = payload?.data || {};
    const dateBadge = document.getElementById('dashboard-bi-date');
    const summary = document.getElementById('dashboard-bi-summary');
    const spotsContainer = document.getElementById('dashboard-bi-spots');
    const pricingContainer = document.getElementById('dashboard-bi-pricing');
    const eventsContainer = document.getElementById('dashboard-bi-events');

    if (!summary || !spotsContainer || !pricingContainer || !eventsContainer) {
        return;
    }

    if (dateBadge) {
        dateBadge.textContent = payload?.date || '-';
    }

    const revenuePrediction = data.revenue_prediction || {};
    summary.innerHTML = `
        <div class="col-12 col-md-4">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.biPredictedRevenueLabel}</div>
                <div class="slot-summary-value">${toCurrency(revenuePrediction.predicted_revenue || 0, labels.currency)}</div>
            </div>
        </div>
        <div class="col-12 col-md-4">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.biConfidenceLabel}</div>
                <div class="slot-summary-value">${Number((revenuePrediction.confidence_score || 0) * 100).toFixed(0)}%</div>
            </div>
        </div>
        <div class="col-12 col-md-4">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.biSuggestedEventsLabel}</div>
                <div class="slot-summary-value">${(data.event_opportunities || []).length}</div>
            </div>
        </div>
    `;

    const bestSpots = data.best_spots || [];
    if (!bestSpots.length) {
        spotsContainer.innerHTML = `<div class="text-muted small">${labels.biEmptySpotsLabel}</div>`;
    } else {
        spotsContainer.innerHTML = bestSpots.map((spot) => `
            <div class="list-group-item px-0 py-2 bg-transparent border-0 border-bottom">
                <div class="fw-semibold">${labels.biScoreLabel} ${Number(spot.score || 0).toFixed(1)}/100</div>
                <div class="small text-muted">${labels.biLatLabel} ${Number(spot.latitude).toFixed(4)}, ${labels.biLngLabel} ${Number(spot.longitude).toFixed(4)}</div>
            </div>
        `).join('');
    }

    const pricing = data.pricing_suggestions || [];
    if (!pricing.length) {
        pricingContainer.innerHTML = `<div class="text-muted small">${labels.biEmptyPricingLabel}</div>`;
    } else {
        pricingContainer.innerHTML = pricing.map((entry) => `
            <div class="list-group-item px-0 py-2 bg-transparent border-0 border-bottom">
                <div class="fw-semibold">${entry.item_name}</div>
                <div class="small text-muted">${toCurrency(entry.current_price, labels.currency)} → ${toCurrency(entry.suggested_price, labels.currency)}</div>
                <div class="small text-muted">${labels.biConfidenceLabel} ${Number((entry.confidence_score || 0) * 100).toFixed(0)}%</div>
            </div>
        `).join('');
    }

    const events = data.event_opportunities || [];
    if (!events.length) {
        eventsContainer.innerHTML = `<div class="text-muted small">${labels.biEmptyEventsLabel}</div>`;
    } else {
        eventsContainer.innerHTML = events.map((entry) => `
            <div class="list-group-item px-0 py-2 bg-transparent border-0 border-bottom">
                <div class="fw-semibold">${entry.event_name}</div>
                <div class="small text-muted">${labels.biScoreLabel} ${Number(entry.opportunity_score || 0).toFixed(1)}/100</div>
                <div class="small text-muted">${labels.biPredictedLabel} ${toCurrency(entry.predicted_revenue || 0, labels.currency)}</div>
            </div>
        `).join('');
    }
}

async function loadDashboard(range, interval = 'day', labels, categoryId = null, displayMode = null) {
    const [kpis, revenue, orders, menuPerformance, menuCategories, businessIntelligence] = await Promise.all([
        fetchKpis(root.dataset.kpisUrl, range, categoryId, displayMode),
        fetchRevenue(root.dataset.revenueUrl, range, interval, categoryId, displayMode),
        fetchOrders(root.dataset.ordersUrl, range, 20, categoryId, displayMode),
        fetchMenuPerformance(root.dataset.menuPerformanceUrl, range, 10, categoryId, displayMode),
        fetchMenuCategoryPerformance(root.dataset.menuCategoriesUrl, range, 8, categoryId, displayMode),
        fetchBusinessIntelligence(root.dataset.biUrl),
    ]);

    renderKpis(kpis, labels);
    updateRevenueChart(revenue.data || []);
    renderOrders(orders, labels);
    renderMenuPerformance(menuPerformance, labels);
    renderMenuCategoryPerformance(menuCategories, labels);
    renderBusinessIntelligence(businessIntelligence, labels);
    await loadSlotAnalytics(root, range, labels, categoryId, displayMode);
}

async function refreshOrders(range, labels, categoryId = null, displayMode = null) {
    const payload = await fetchOrders(root.dataset.ordersUrl, range, 20, categoryId, displayMode);
    renderOrders(payload, labels);
}

function init() {
    if (!root) {
        return;
    }

    const rangeSelect = document.getElementById('dashboard-range-select');
    const displayModeSelect = document.getElementById('dashboard-display-mode-select');
    const intervalSelect = document.getElementById('dashboard-interval-select');
    const refreshOrdersButton = document.getElementById('dashboard-orders-refresh');
    const chartCanvas = document.getElementById('dashboard-revenue-chart');
    const menuCategoryCanvas = document.getElementById('dashboard-menu-category-chart');
    const optionsCanvas = document.getElementById('dashboard-options-chart');
    const clearCategoryFilterButton = document.getElementById('dashboard-clear-category-filter');
    const categoryChips = collectCategoryChips();
    const labels = getLabels();

    initRevenueChart(chartCanvas, labels.chartRevenueLabel);
    initMenuCategoryChart(menuCategoryCanvas, labels.chartMenuCategoryLabel);
    initOptionsChart(optionsCanvas, labels.optionsTotalRevenueLabel);

    let activeRange = root.dataset.activeRange || '7d';
    let activeInterval = intervalSelect.value || 'day';
    let activeCategoryId = null;
    let activeDisplayMode = displayModeSelect?.value || root.dataset.displayMode || 'tax_included';

    const refreshDashboard = () => loadDashboard(activeRange, activeInterval, labels, activeCategoryId, activeDisplayMode);
    const refreshOrdersOnly = () => refreshOrders(activeRange, labels, activeCategoryId, activeDisplayMode);

    applyCategoryChipActiveState(categoryChips, activeCategoryId, clearCategoryFilterButton);

    refreshDashboard().catch(() => {
        renderOrders({ data: [] }, labels);
        renderMenuPerformance({ data: [] }, labels);
    });

    rangeSelect.addEventListener('change', () => {
        activeRange = rangeSelect.value;
        refreshDashboard().catch(() => {});
    });

    intervalSelect.addEventListener('change', () => {
        activeInterval = intervalSelect.value;
        refreshDashboard().catch(() => {});
    });

    displayModeSelect?.addEventListener('change', () => {
        activeDisplayMode = displayModeSelect.value;
        refreshDashboard().catch(() => {});
    });

    refreshOrdersButton.addEventListener('click', () => {
        refreshOrdersOnly().catch(() => {});
    });

    clearCategoryFilterButton?.addEventListener('click', () => {
        activeCategoryId = null;
        applyCategoryChipActiveState(categoryChips, activeCategoryId, clearCategoryFilterButton);
        refreshDashboard().catch(() => {});
    });

    categoryChips.forEach((chip) => {
        chip.addEventListener('click', (event) => {
            const categoryId = chip.dataset.categoryId;
            if (!categoryId) {
                return;
            }

            event.preventDefault();
            activeCategoryId = activeCategoryId === categoryId ? null : categoryId;
            applyCategoryChipActiveState(categoryChips, activeCategoryId, clearCategoryFilterButton);
            refreshDashboard().catch(() => {});
        });
    });

    window.setInterval(() => {
        refreshOrdersOnly().catch(() => {});
    }, AUTO_REFRESH_MS);

    initIndicatorHelpModal(labels);
}

init();
