import {
    fetchSlotHeatmap,
    fetchSlotHourly,
    fetchSlotInsights,
    fetchSlotRecommendations,
    fetchSlotRevenue,
    fetchSlotUtilization,
} from './api.js';
import { renderHeatmap } from './heatmap.js';

const MAX_VISIBLE_INSIGHTS = 5;

function toCurrency(value, currency) {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value || 0));
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

function renderSlotUtilization(root, utilizationPayload, revenuePayload, labels) {
    const summaryContainer = document.getElementById('dashboard-slot-utilization-summary');
    const segmentsContainer = document.getElementById('dashboard-slot-utilization-segments');
    const topContainer = document.getElementById('dashboard-slot-utilization-top');
    if (!summaryContainer || !segmentsContainer || !topContainer) {
        return;
    }

    const utilizationRows = utilizationPayload?.data || [];
    const revenueBySlot = new Map((revenuePayload?.data || []).map((row) => [Number(row.slot_id), row]));

    if (!utilizationRows.length) {
        summaryContainer.innerHTML = `<div class="col-12"><div class="text-muted text-center py-3">${labels.emptySlotsLabel}</div></div>`;
        segmentsContainer.innerHTML = '';
        topContainer.textContent = '';
        return;
    }

    const totalSlots = utilizationRows.length;
    const activeSlots = utilizationRows.filter((row) => Number(row.total_orders || 0) > 0).length;
    const avgUtilization = utilizationRows.reduce((acc, row) => acc + Number(row.utilization_pct || 0), 0) / totalSlots;

    const revenueRows = Array.from(revenueBySlot.values());
    const totalRevenue = revenueRows.reduce((acc, row) => acc + Number(row.total_revenue || 0), 0);

    const underperforming = utilizationRows.filter((row) => Number(row.utilization_pct || 0) < 40).length;
    const optimal = utilizationRows.filter((row) => Number(row.utilization_pct || 0) >= 40 && Number(row.utilization_pct || 0) <= 80).length;
    const saturated = utilizationRows.filter((row) => Number(row.utilization_pct || 0) > 80).length;

    const topRevenue = revenueRows.sort((a, b) => Number(b.total_revenue || 0) - Number(a.total_revenue || 0))[0];

    summaryContainer.innerHTML = `
        <div class="col-4">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.slotActiveLabel}</div>
                <div class="slot-summary-value">${activeSlots}/${totalSlots}</div>
            </div>
        </div>
        <div class="col-4">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.slotAverageUtilizationLabel}</div>
                <div class="slot-summary-value">${toPercent(avgUtilization)}</div>
            </div>
        </div>
        <div class="col-4">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.slotRevenueLabel}</div>
                <div class="slot-summary-value">${toCurrency(totalRevenue, labels.currency)}</div>
            </div>
        </div>
    `;

    const buildSegment = (label, count, barClass) => {
        const pct = totalSlots > 0 ? (count * 100) / totalSlots : 0;
        return `
            <div>
                <div class="d-flex justify-content-between small mb-1">
                    <span>${label}</span>
                    <span>${count}</span>
                </div>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar ${barClass}" role="progressbar" style="width: ${pct.toFixed(2)}%"></div>
                </div>
            </div>
        `;
    };

    segmentsContainer.innerHTML = [
        buildSegment(labels.slotUnderperformingLabel, underperforming, 'bg-danger'),
        buildSegment(labels.slotOptimalLabel, optimal, 'bg-success'),
        buildSegment(labels.slotSaturatedLabel, saturated, 'bg-warning'),
    ].join('');

    if (topRevenue) {
        topContainer.textContent = `${labels.slotTopSlotLabel}: ${formatDateTime(topRevenue.start_time, labels.datePlaceholderLabel)} (${toCurrency(topRevenue.total_revenue, labels.currency)})`;
    } else {
        topContainer.textContent = '';
    }
}

function renderHourlyPerformance(payload, labels) {
    const body = document.getElementById('dashboard-hourly-performance-body');
    if (!body) {
        return;
    }

    const rows = payload?.data || [];
    if (!rows.length) {
        body.innerHTML = `<tr><td colspan="4" class="text-muted text-center py-3">${labels.emptyHourlyLabel}</td></tr>`;
        return;
    }

    body.innerHTML = rows.map((row) => `
        <tr>
            <td>${row.hour}:00</td>
            <td class="text-end">${row.orders}</td>
            <td class="text-end">${toCurrency(row.revenue, labels.currency)}</td>
            <td class="text-end">${toCurrency(row.avg_order_value, labels.currency)}</td>
        </tr>
    `).join('');
}

function renderInsights(payload, labels) {
    const data = payload?.data || {};

    const targetMap = [
        ['underperforming_slots', 'dashboard-insights-underperforming'],
        ['optimal_slots', 'dashboard-insights-optimal'],
        ['saturated_slots', 'dashboard-insights-saturated'],
    ];

    targetMap.forEach(([key, elementId]) => {
        const container = document.getElementById(elementId);
        if (!container) {
            return;
        }

        const rows = data[key] || [];
        if (!rows.length) {
            container.innerHTML = `<div class="text-muted">${labels.emptyInsightsLabel}</div>`;
            return;
        }

        const visible = rows.slice(0, MAX_VISIBLE_INSIGHTS);
        const hiddenCount = Math.max(0, rows.length - visible.length);

        container.innerHTML = `
            <div class="d-flex flex-column gap-1">
                ${visible.map((row) => `<div class="d-flex justify-content-between"><span>${formatDateTime(row.start_time, labels.datePlaceholderLabel)}</span><strong>${toPercent(row.utilization_pct)}</strong></div>`).join('')}
                ${hiddenCount > 0 ? `<div class="text-muted small">+${hiddenCount} ${labels.insightsMoreLabel}</div>` : ''}
            </div>
        `;
    });
}

function renderRecommendations(payload, labels) {
    const data = payload?.data || {};

    const increaseContainer = document.getElementById('dashboard-reco-increase');
    const reduceContainer = document.getElementById('dashboard-reco-reduce');
    const newContainer = document.getElementById('dashboard-reco-new');

    const increaseRows = data.increase_capacity_slots || [];
    const reduceRows = data.reduce_capacity_slots || [];
    const newRows = data.suggested_new_slots || [];

    if (increaseContainer) {
        const visible = increaseRows.slice(0, MAX_VISIBLE_INSIGHTS);
        const hiddenCount = Math.max(0, increaseRows.length - visible.length);
        increaseContainer.innerHTML = increaseRows.length
            ? `${visible.map((row) => `<div class="d-flex justify-content-between"><span>${formatDateTime(row.start_time, labels.datePlaceholderLabel)}</span><strong>${toPercent(row.utilization_pct)}</strong></div>`).join('')}${hiddenCount > 0 ? `<div class="text-muted small">+${hiddenCount} ${labels.recommendationsMoreLabel}</div>` : ''}`
            : `<div class="text-muted">${labels.emptyRecommendationsLabel}</div>`;
    }

    if (reduceContainer) {
        const visible = reduceRows.slice(0, MAX_VISIBLE_INSIGHTS);
        const hiddenCount = Math.max(0, reduceRows.length - visible.length);
        reduceContainer.innerHTML = reduceRows.length
            ? `${visible.map((row) => `<div class="d-flex justify-content-between"><span>${formatDateTime(row.start_time, labels.datePlaceholderLabel)}</span><strong>${toPercent(row.utilization_pct)}</strong></div>`).join('')}${hiddenCount > 0 ? `<div class="text-muted small">+${hiddenCount} ${labels.recommendationsMoreLabel}</div>` : ''}`
            : `<div class="text-muted">${labels.emptyRecommendationsLabel}</div>`;
    }

    if (newContainer) {
        const visible = newRows.slice(0, MAX_VISIBLE_INSIGHTS);
        const hiddenCount = Math.max(0, newRows.length - visible.length);
        newContainer.innerHTML = newRows.length
            ? `${visible.map((row) => `<div class="d-flex justify-content-between"><span>${row.hour}:00</span><strong>${labels.demandLabel}: ${row.demand_orders}</strong></div>`).join('')}${hiddenCount > 0 ? `<div class="text-muted small">+${hiddenCount} ${labels.recommendationsMoreLabel}</div>` : ''}`
            : `<div class="text-muted">${labels.emptyRecommendationsLabel}</div>`;
    }
}

export async function loadSlotAnalytics(root, range, labels, categoryId = null, displayMode = null) {
    const [utilization, revenue, hourly, heatmap, insights, recommendations] = await Promise.all([
        fetchSlotUtilization(root.dataset.slotsUtilizationUrl, range, categoryId),
        fetchSlotRevenue(root.dataset.slotsRevenueUrl, range, categoryId, displayMode),
        fetchSlotHourly(root.dataset.slotsHourlyUrl, range, categoryId, displayMode),
        fetchSlotHeatmap(root.dataset.slotsHeatmapUrl, range, categoryId),
        fetchSlotInsights(root.dataset.slotsInsightsUrl, categoryId),
        fetchSlotRecommendations(root.dataset.slotsRecommendationsUrl, categoryId),
    ]);

    renderSlotUtilization(root, utilization, revenue, labels);
    renderHourlyPerformance(hourly, labels);
    renderHeatmap(document.getElementById('dashboard-slot-heatmap'), heatmap?.data || [], labels);
    renderInsights(insights, labels);
    renderRecommendations(recommendations, labels);
}
