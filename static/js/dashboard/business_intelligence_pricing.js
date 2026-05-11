import { fetchBusinessIntelligence } from './api.js';

const root = document.getElementById('foodtruck-bi-page');

function getLabels() {
    return {
        currency: root?.dataset.currency || 'EUR',
        biConfidenceLabel: root?.dataset.biConfidenceLabel || 'Confidence',
        biEmptyPricingLabel: root?.dataset.biEmptyPricingLabel || 'No pricing suggestions yet.',
        biPredictedRevenueLabel: root?.dataset.biPredictedRevenueLabel || 'Predicted revenue (D+1)',
        biRevenueDetailsLabel: root?.dataset.biRevenueDetailsLabel || 'How is this estimate calculated?',
        biRevenueModalTitle: root?.dataset.biRevenueModalTitle || 'Revenue estimate breakdown',
        biRevenueModalSubtitle: root?.dataset.biRevenueModalSubtitle || 'This estimate combines recent sales, basket value, pickup activity and event potential.',
        biRevenueModalEmptyLabel: root?.dataset.biRevenueModalEmptyLabel || 'No revenue breakdown is available yet.',
        biRevenueMethodLabel: root?.dataset.biRevenueMethodLabel || 'Method',
        biRevenueFormulaLabel: root?.dataset.biRevenueFormulaLabel || 'Formula',
        biRevenueInputsLabel: root?.dataset.biRevenueInputsLabel || 'Inputs used',
        biRevenueFloorLabel: root?.dataset.biRevenueFloorLabel || 'Minimum floor',
        biRevenueFactorHistorical: root?.dataset.biRevenueFactorHistorical || 'Historical daily average',
        biRevenueFactorWeekday: root?.dataset.biRevenueFactorWeekday || 'Weekday factor',
        biRevenueFactorSlot: root?.dataset.biRevenueFactorSlot || 'Slot factor',
        biRevenueFactorEvent: root?.dataset.biRevenueFactorEvent || 'Event factor',
        biRevenueFactorAi: root?.dataset.biRevenueFactorAi || 'AI adjustment',
    };
}

function toCurrency(value, currency) {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value || 0));
}

function toPercent(value) {
    return `${Number(value || 0).toFixed(0)}%`;
}

function formatRevenueBreakdown(details, labels) {
    const breakdown = details?.breakdown || {};
    const predictedRevenue = Number(details?.predicted_revenue || 0);
    const hasConfidence = details?.confidence_score !== undefined && details?.confidence_score !== null;
    const confidenceScore = Number(details?.confidence_score || 0);
    const factorRows = [];
    const factorMap = [
        ['historical_daily_average', labels.biRevenueFactorHistorical, true],
        ['weekday_factor', labels.biRevenueFactorWeekday, false],
        ['slot_factor', labels.biRevenueFactorSlot, false],
        ['event_factor', labels.biRevenueFactorEvent, false],
        ['ai_adjustment', labels.biRevenueFactorAi, true],
    ];

    factorMap.forEach(([key, label, isCurrency]) => {
        if (breakdown[key] !== undefined && breakdown[key] !== null) {
            const value = isCurrency
                ? toCurrency(breakdown[key], labels.currency)
                : `${Number(breakdown[key]).toFixed(2)}x`;
            factorRows.push(`<li><span class="fw-semibold">${label}:</span> ${value}</li>`);
        }
    });

    const method = (breakdown.method || labels.biRevenueModalEmptyLabel).replace(/_/g, ' ');
    const formula = breakdown.method === 'fallback_simple_average'
        ? `${labels.biRevenueFloorLabel}: ${toCurrency(predictedRevenue, labels.currency)}`
        : `(${toCurrency(breakdown.historical_daily_average || 0, labels.currency)} × ${Number(breakdown.weekday_factor || 1).toFixed(2)} × ${Number(breakdown.slot_factor || 1).toFixed(2)} × ${Number(breakdown.event_factor || 1).toFixed(2)}) ${Number(breakdown.ai_adjustment || 0) >= 0 ? '+' : ''} ${toCurrency(breakdown.ai_adjustment || 0, labels.currency)}`;

    return `
        <div class="row g-3">
            <div class="col-12 col-lg-4">
                <div class="border rounded-3 p-3 h-100 bg-light">
                    <div class="small text-muted">${labels.biPredictedRevenueLabel}</div>
                    <div class="h3 mb-1">${toCurrency(predictedRevenue, labels.currency)}</div>
                    ${hasConfidence ? `<div class="small text-muted">${labels.biConfidenceLabel}: ${toPercent(confidenceScore * 100)}</div>` : ''}
                </div>
            </div>
            <div class="col-12 col-lg-8">
                <div class="border rounded-3 p-3 h-100">
                    <div class="mb-3">
                        <div class="small text-muted mb-1">${labels.biRevenueMethodLabel}</div>
                        <div class="fw-semibold text-capitalize">${method}</div>
                    </div>
                    <div class="mb-3">
                        <div class="small text-muted mb-1">${labels.biRevenueFormulaLabel}</div>
                        <div class="font-monospace small text-break">${formula}</div>
                    </div>
                    <div>
                        <div class="small text-muted mb-1">${labels.biRevenueInputsLabel}</div>
                        <ul class="mb-0 small ps-3">${factorRows.join('')}</ul>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function initRevenueEstimateModal(labels) {
    const modalElement = document.getElementById('dashboardRevenueModal');
    const titleElement = document.getElementById('dashboardRevenueModalLabel');
    const bodyElement = document.getElementById('dashboard-revenue-modal-body');
    const subtitleElement = document.getElementById('dashboard-revenue-modal-subtitle');
    const noteElement = document.getElementById('dashboard-revenue-modal-note');

    if (!modalElement || !titleElement || !bodyElement) {
        return null;
    }

    const modal = new bootstrap.Modal(modalElement);
    document.addEventListener('click', (event) => {
        const trigger = event.target instanceof HTMLElement
            ? event.target.closest('[data-revenue-breakdown-trigger]')
            : null;
        if (!trigger) {
            return;
        }

        titleElement.textContent = labels.biRevenueModalTitle;
        if (subtitleElement) {
            subtitleElement.textContent = labels.biRevenueModalSubtitle;
        }
        if (noteElement) {
            noteElement.textContent = '';
        }

        const revenuePrediction = window.__dashboardRevenuePrediction || {};
        if (!Object.keys(revenuePrediction.breakdown || {}).length) {
            bodyElement.innerHTML = `<div class="text-muted small">${labels.biRevenueModalEmptyLabel}</div>`;
        } else {
            bodyElement.innerHTML = formatRevenueBreakdown(revenuePrediction, labels);
        }

        modal.show();
    });

    return modal;
}

function renderPricing(payload, labels) {
    const data = payload?.data || {};
    const pricingContainer = document.getElementById('dashboard-bi-pricing');

    if (!pricingContainer) {
        console.log('Missing container: pricing');
        return;
    }

    // Store revenue prediction globally for modal use
    window.__dashboardRevenuePrediction = data.revenue_prediction || {};

    const pricing = data.pricing_suggestions || [];
    if (!pricing.length) {
        pricingContainer.innerHTML = `<div class="text-muted small">${labels.biEmptyPricingLabel}</div>`;
    } else {
        pricingContainer.innerHTML = pricing.map((entry) => `
            <div class="list-group-item px-0 py-2 bg-transparent border-0 border-bottom">
                <div class="fw-semibold">${entry.item_name}</div>
                <div class="small text-muted">${toCurrency(entry.current_price, labels.currency)} -> ${toCurrency(entry.suggested_price, labels.currency)}</div>
                <div class="small text-muted">${labels.biConfidenceLabel} ${Number((entry.confidence_score || 0) * 100).toFixed(0)}%</div>
            </div>
        `).join('');
    }
}

async function init() {
    if (!root) {
        console.error('Root element #foodtruck-bi-page not found');
        return;
    }

    const labels = getLabels();
    initRevenueEstimateModal(labels);

    const load = async () => {
        try {
            const payload = await fetchBusinessIntelligence(root.dataset.biUrl, {});
            renderPricing(payload, labels);
        } catch (error) {
            console.error('Error loading pricing data:', error);
            const pricingContainer = document.getElementById('dashboard-bi-pricing');
            if (pricingContainer) {
                pricingContainer.innerHTML = `<div class="text-danger small">${labels.biEmptyPricingLabel} (Error: ${error.message})</div>`;
            }
        }
    };

    await load();
}

init();
