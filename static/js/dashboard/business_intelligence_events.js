import { fetchBusinessIntelligence } from './api.js';

const root = document.getElementById('foodtruck-bi-page');

// localStorage keys
const STORAGE_PREFIX = 'bi-targeting-';
const STORAGE_CUSTOM_KEYWORDS = STORAGE_PREFIX + 'custom-keywords';
const STORAGE_FORM_STATE = STORAGE_PREFIX + 'form-state';

function normalizeKeyword(value) {
    return (value || '')
        .toString()
        .trim()
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '');
}

function deduplicateKeywords(values) {
    const seen = new Set();
    return values.filter((value) => {
        const key = normalizeKeyword(value);
        if (!key || seen.has(key)) {
            return false;
        }
        seen.add(key);
        return true;
    });
}

function getStoredCustomKeywords() {
    try {
        const stored = localStorage.getItem(STORAGE_CUSTOM_KEYWORDS);
        return stored ? JSON.parse(stored) : [];
    } catch (error) {
        console.warn('Failed to parse custom keywords from localStorage:', error);
        return [];
    }
}

function saveCustomKeywords(keywords) {
    try {
        localStorage.setItem(STORAGE_CUSTOM_KEYWORDS, JSON.stringify(deduplicateKeywords(keywords)));
    } catch (error) {
        console.warn('Failed to save custom keywords to localStorage:', error);
    }
}

function saveFormState() {
    try {
        const form = document.getElementById('dashboard-bi-target-form');
        if (!form) return;
        
        const formData = new FormData(form);
        const state = {
            horizon_days: formData.get('horizon_days'),
            min_attendance: formData.get('min_attendance'),
            min_score: formData.get('min_score'),
            period: formData.get('period'),
            limit: formData.get('limit'),
            radius_km: formData.get('radius_km'),
            keywords: formData.getAll('keywords'),
            custom_keywords: getStoredCustomKeywords(),
        };
        localStorage.setItem(STORAGE_FORM_STATE, JSON.stringify(state));
    } catch (error) {
        console.warn('Failed to save form state to localStorage:', error);
    }
}

function restoreFormState() {
    try {
        const stored = localStorage.getItem(STORAGE_FORM_STATE);
        if (!stored) return;
        
        const state = JSON.parse(stored);
        const form = document.getElementById('dashboard-bi-target-form');
        if (!form) return;
        
        if (state.horizon_days && form.horizon_days) {
            form.horizon_days.value = state.horizon_days;
        }
        if (state.min_attendance && form.min_attendance) {
            form.min_attendance.value = state.min_attendance;
        }
        if (state.min_score && form.min_score) {
            form.min_score.value = state.min_score;
        }
        if (state.period && form.period) {
            form.period.value = state.period;
        }
        if (state.limit && form.limit) {
            form.limit.value = state.limit;
        }
        if (state.radius_km && form.radius_km) {
            form.radius_km.value = state.radius_km;
        }
        
        if (Array.isArray(state.keywords) && state.keywords.length) {
            state.keywords.forEach((keyword) => {
                const checkbox = form.querySelector(`input[name="keywords"][value="${keyword}"]`);
                if (checkbox) {
                    checkbox.checked = true;
                }
            });
        }
    } catch (error) {
        console.warn('Failed to restore form state from localStorage:', error);
    }
}

function renderCustomKeywordTags() {
    const container = document.getElementById('bi-custom-keywords-tags');
    if (!container) return;
    
    const keywords = getStoredCustomKeywords();
    container.innerHTML = keywords.map((keyword) => `
        <span class="badge text-bg-secondary">
            ${keyword}
            <button type="button" class="btn-close btn-close-white bi-custom-keyword-remove ms-1" aria-label="Remove" data-keyword="${keyword}" style="transform: scale(0.75)"></button>
        </span>
    `).join('');
}

function removeCustomKeyword(keyword, event) {
    event.preventDefault();
    event.stopPropagation();
    const keywords = getStoredCustomKeywords().filter((k) => normalizeKeyword(k) !== normalizeKeyword(keyword));
    saveCustomKeywords(keywords);
    renderCustomKeywordTags();
}

function processAndStoreCustomKeywords(value) {
    const newKeywords = value
        .split(',')
        .map((v) => v.trim())
        .filter((v) => v.length > 0);
    const existing = getStoredCustomKeywords();
    const combined = deduplicateKeywords([...existing, ...newKeywords]);
    saveCustomKeywords(combined);
    renderCustomKeywordTags();
}

function commitPendingCustomKeywordsInput() {
    const customKeywordsInput = document.getElementById('bi-custom-keywords');
    if (!customKeywordsInput) {
        return;
    }
    const value = customKeywordsInput.value.trim().replace(/[,]$/, '');
    if (value) {
        processAndStoreCustomKeywords(value);
        customKeywordsInput.value = '';
    }
}

function getSelectedPresetKeywordTokens(form) {
    const checkedInputs = Array.from(form.querySelectorAll('.bi-keyword-preset:checked'));
    const tokens = [];

    checkedInputs.forEach((input) => {
        const value = normalizeKeyword(input.value);
        const label = normalizeKeyword(input.dataset.label || '');
        if (value) {
            tokens.push(value);
        }
        if (label) {
            tokens.push(label);
        }
    });

    return deduplicateKeywords(tokens);
}

function getTargetingParams() {
    const form = document.getElementById('dashboard-bi-target-form');
    if (!form) {
        return {};
    }

    commitPendingCustomKeywordsInput();

    const formData = new FormData(form);
    const presetKeywordTokens = getSelectedPresetKeywordTokens(form);
    const customKeywords = deduplicateKeywords(getStoredCustomKeywords().map((value) => normalizeKeyword(value)));
    const allKeywords = deduplicateKeywords([...presetKeywordTokens, ...customKeywords]);
    
    const params = {
        horizon_days: formData.get('horizon_days'),
        min_attendance: formData.get('min_attendance'),
        min_score: formData.get('min_score'),
        period: formData.get('period'),
        limit: formData.get('limit'),
        radius_km: formData.get('radius_km'),
    };
    
    if (allKeywords.length > 0) {
        params.keywords = allKeywords.join(',');
    }

    return params;
}

function getLabels() {
    return {
        currency: root?.dataset.currency || 'EUR',
        biPredictedRevenueLabel: root?.dataset.biPredictedRevenueLabel || 'Predicted revenue (D+1)',
        biConfidenceLabel: root?.dataset.biConfidenceLabel || 'Confidence',
        biRevenueDetailsLabel: root?.dataset.biRevenueDetailsLabel || 'How is this estimate calculated?',
        biRevenueModalTitle: root?.dataset.biRevenueModalTitle || 'Revenue estimate breakdown',
        biRevenueModalSubtitle: root?.dataset.biRevenueModalSubtitle || 'This estimate combines recent sales, basket value, pickup activity and event potential.',
        biRevenueModalEmptyLabel: root?.dataset.biRevenueModalEmptyLabel || 'No revenue breakdown is available yet.',
        biRevenueMethodLabel: root?.dataset.biRevenueMethodLabel || 'Method',
        biRevenueFormulaLabel: root?.dataset.biRevenueFormulaLabel || 'Formula',
        biRevenueInputsLabel: root?.dataset.biRevenueInputsLabel || 'Inputs used',
        biRevenueFloorLabel: root?.dataset.biRevenueFloorLabel || 'Minimum floor',
        biSuggestedEventsLabel: root?.dataset.biSuggestedEventsLabel || 'Suggested event opportunities',
        biEmptySpotsLabel: root?.dataset.biEmptySpotsLabel || 'No spot recommendations yet.',
        biScoreLabel: root?.dataset.biScoreLabel || 'Score',
        biLatLabel: root?.dataset.biLatLabel || 'Lat',
        biLngLabel: root?.dataset.biLngLabel || 'Lng',
        biEmptyPricingLabel: root?.dataset.biEmptyPricingLabel || 'No pricing suggestions yet.',
        biPredictedLabel: root?.dataset.biPredictedLabel || 'Estimated revenue',
        biEventDateLabel: root?.dataset.biEventDateLabel || 'Date',
        biEventLocationLabel: root?.dataset.biEventLocationLabel || 'Location',
        biEventDistanceLabel: root?.dataset.biEventDistanceLabel || 'Distance',
        biEventAttendanceLabel: root?.dataset.biEventAttendanceLabel || 'Attendance',
        biEventInfoLabel: root?.dataset.biEventInfoLabel || 'Available info',
        biEventUnavailableLabel: root?.dataset.biEventUnavailableLabel || 'Unavailable',
        biEventAddressUnavailableLabel: root?.dataset.biEventAddressUnavailableLabel || 'Address unavailable',
        biEventCoordinatesLabel: root?.dataset.biEventCoordinatesLabel || 'Coordinates',
        biEventSourceLinkLabel: root?.dataset.biEventSourceLinkLabel || 'View event details',
        biEmptyEventsLabel: root?.dataset.biEmptyEventsLabel || 'No event opportunities were found for the next 14 days.',
        biTargetingProgressLabel: root?.dataset.biTargetingProgressLabel || 'Opportunity search in progress...',
        biTargetingAnalyzedLabel: root?.dataset.biTargetingAnalyzedLabel || 'events analyzed',
        biTargetingRetainedLabel: root?.dataset.biTargetingRetainedLabel || 'opportunities retained',
        biFilterTraceLabel: root?.dataset.biFilterTraceLabel || 'Filter detail',
        biFilterColLabel: root?.dataset.biFilterColLabel || 'Filter',
        biEventsRemainingLabel: root?.dataset.biEventsRemainingLabel || 'Remaining events',
        biEventsInDbLabel: root?.dataset.biEventsInDbLabel || 'event(s) in database',
        biEventModalCalcSubtitle: root?.dataset.biEventModalCalcSubtitle || 'Calculation detail for this event.',
        biEventModalTitleSuffix: root?.dataset.biEventModalTitleSuffix || 'revenue estimate',
        biRevenueFactorHistorical: root?.dataset.biRevenueFactorHistorical || 'Historical daily average',
        biRevenueFactorWeekday: root?.dataset.biRevenueFactorWeekday || 'Weekday factor',
        biRevenueFactorSlot: root?.dataset.biRevenueFactorSlot || 'Slot factor',
        biRevenueFactorEvent: root?.dataset.biRevenueFactorEvent || 'Event factor',
        biRevenueFactorAi: root?.dataset.biRevenueFactorAi || 'AI adjustment',
        biScoreFactorDistance: root?.dataset.biScoreFactorDistance || 'Distance score',
        biScoreFactorAttendance: root?.dataset.biScoreFactorAttendance || 'Attendance score',
        biScoreFactorCategory: root?.dataset.biScoreFactorCategory || 'Menu compatibility',
        biScoreFactorTiming: root?.dataset.biScoreFactorTiming || 'Time slot',
        biScoreFactorAi: root?.dataset.biScoreFactorAi || 'AI adjustment',
        biEventScoreMethodAi: root?.dataset.biEventScoreMethodAi || 'AI',
        biEventScoreMethodBase: root?.dataset.biEventScoreMethodBase || 'Base signal',
        biEventOpportunityScoreLabel: root?.dataset.biEventOpportunityScoreLabel || 'Opportunity score',
        biEventRevenueCalcDesc: root?.dataset.biEventRevenueCalcDesc || 'The estimate combines recent daily revenue (weighted by attractiveness) and the event potential (attendance × basket × conversion rate).',
        biScoreOpportunityFactorsLabel: root?.dataset.biScoreOpportunityFactorsLabel || 'Opportunity score factors',
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

function formatEventRevenueBreakdown(entry, labels) {
    const breakdown = entry?.breakdown || {};
    const predictedRevenue = Number(entry?.predicted_revenue || 0);
    const opportunityScore = Number(entry?.opportunity_score || 0);
    const source = breakdown.source || 'legacy';

    const scoreFactors = [
        ['distance_score', labels.biScoreFactorDistance],
        ['attendance_score', labels.biScoreFactorAttendance],
        ['category_match_score', labels.biScoreFactorCategory],
        ['timing_score', labels.biScoreFactorTiming],
        ['ai_adjustment', labels.biScoreFactorAi],
    ];

    const factorRows = scoreFactors
        .filter(([key]) => breakdown[key] !== undefined && breakdown[key] !== null)
        .map(([key, label]) => {
            const v = Number(breakdown[key]);
            const badgeClass = v >= 70 ? 'text-success' : v >= 40 ? 'text-warning' : 'text-danger';
            return `<li><span class="fw-semibold">${label}:</span> <span class="${badgeClass}">${v.toFixed(1)}/100</span></li>`;
        })
        .join('');

    const distanceRow = breakdown.distance_km !== undefined
        ? `<li><span class="fw-semibold">Distance:</span> ${Number(breakdown.distance_km).toFixed(1)} km</li>`
        : '';

    const sourceBadge = source === 'ai_analysis'
        ? `<span class="badge text-bg-primary ms-2" style="font-size:0.65rem;">${labels.biEventScoreMethodAi}</span>`
        : `<span class="badge text-bg-secondary ms-2" style="font-size:0.65rem;">${labels.biEventScoreMethodBase}</span>`;

    return `
        <div class="row g-3">
            <div class="col-12 col-lg-4">
                <div class="border rounded-3 p-3 h-100 bg-light">
                    <div class="small text-muted">${labels.biPredictedLabel}</div>
                    <div class="h3 mb-1">${toCurrency(predictedRevenue, labels.currency)}</div>
                    <div class="small text-muted">${labels.biEventOpportunityScoreLabel}: <strong>${opportunityScore.toFixed(1)}/100</strong></div>
                    <div class="small text-muted mt-1">${labels.biRevenueMethodLabel} ${sourceBadge}</div>
                </div>
            </div>
            <div class="col-12 col-lg-8">
                <div class="border rounded-3 p-3 h-100">
                    <div class="mb-3">
                        <div class="small text-muted mb-1">${labels.biRevenueDetailsLabel}</div>
                        <p class="small mb-0">${labels.biEventRevenueCalcDesc}</p>
                    </div>
                    ${factorRows || distanceRow ? `
                    <div>
                        <div class="small text-muted mb-1">${labels.biScoreOpportunityFactorsLabel}</div>
                        <ul class="mb-0 small ps-3">${factorRows}${distanceRow}</ul>
                    </div>` : ''}
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

        const triggerKind = trigger.dataset.revenueBreakdownTrigger || 'summary';
        const eventId = trigger.dataset.eventId;
        const eventName = trigger.dataset.eventName || '';

        titleElement.textContent = eventName
            ? `${eventName} — ${labels.biEventModalTitleSuffix}`
            : labels.biRevenueModalTitle;
        if (subtitleElement) {
            subtitleElement.textContent = eventName
                ? labels.biEventModalCalcSubtitle
                : labels.biRevenueModalSubtitle;
        }
        if (noteElement) {
            noteElement.textContent = '';
        }

        if (triggerKind === 'event' && eventId) {
            const entry = window.__dashboardEventRevenueDetails?.get(String(eventId)) || {};
            bodyElement.innerHTML = formatEventRevenueBreakdown(entry, labels);
        } else {
            const revenuePrediction = window.__dashboardRevenuePrediction || {};
            if (!Object.keys(revenuePrediction.breakdown || {}).length) {
                bodyElement.innerHTML = `<div class="text-muted small">${labels.biRevenueModalEmptyLabel}</div>`;
            } else {
                bodyElement.innerHTML = formatRevenueBreakdown(revenuePrediction, labels);
            }
        }

        modal.show();
    });

    return modal;
}

function formatDate(value) {
    if (!value) {
        return null;
    }
    const parsed = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
    }).format(parsed);
}

function formatDateRange(startDate, endDate, labels) {
    const start = formatDate(startDate);
    const end = formatDate(endDate);
    if (!start && !end) {
        return labels.biEventUnavailableLabel;
    }
    if (start && end && start === end) {
        return start;
    }
    if (start && end) {
        return `${start} -> ${end}`;
    }
    return start || end;
}

function formatLocation(entry, labels) {
    if (entry.location_text) {
        return entry.location_text;
    }
    if (entry.latitude !== null && entry.latitude !== undefined && entry.longitude !== null && entry.longitude !== undefined) {
        return `${labels.biEventCoordinatesLabel}: ${Number(entry.latitude).toFixed(4)}, ${Number(entry.longitude).toFixed(4)}`;
    }
    if (entry.location_label) {
        return entry.location_label;
    }
    return labels.biEventAddressUnavailableLabel;
}

function renderSearchFeedback(payload, labels) {
    const feedbackBlock = document.getElementById('bi-target-feedback');
    if (!feedbackBlock) {
        return;
    }

    const feedback = payload?.search_feedback || {};
    const retained = Number(feedback.retained_events_count ?? 0);
    const totalInDb = feedback.total_events_in_db;
    const reasons = Array.isArray(feedback.empty_reasons) ? feedback.empty_reasons : [];
    const trace = Array.isArray(feedback.filter_trace) ? feedback.filter_trace : [];

    let traceHtml = '';
    if (trace.length) {
        const rows = trace.map((step) => {
            const emphasis = step.count === 0 ? ' class="text-danger fw-semibold"' : '';
            return `<tr><td${emphasis}>${step.label}</td><td${emphasis}>${step.count}</td></tr>`;
        }).join('');
        traceHtml = `
            <details class="mt-2">
                <summary class="small text-muted" style="cursor:pointer">${labels.biFilterTraceLabel}</summary>
                <table class="table table-sm table-borderless mt-2 mb-0 small">
                    <thead><tr><th>${labels.biFilterColLabel}</th><th>${labels.biEventsRemainingLabel}</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </details>
        `;
    }

    const reasonsHtml = reasons.length
        ? `<ul class="mb-0 mt-2">${reasons.map((reason) => `<li>${reason}</li>`).join('')}</ul>`
        : '';

    feedbackBlock.classList.remove('d-none', 'alert-secondary', 'alert-warning');
    feedbackBlock.classList.add(retained > 0 ? 'alert-secondary' : 'alert-warning');
    const dbInfo = totalInDb !== undefined
        ? `<span class="text-muted small ms-2">(${totalInDb} ${labels.biEventsInDbLabel})</span>`
        : '';
    feedbackBlock.innerHTML = `
        <div><strong>${retained}</strong> ${labels.biTargetingRetainedLabel}${dbInfo}</div>
        ${reasonsHtml}
        ${traceHtml}
    `;
}

function setLoadingState(isLoading) {
    const loader = document.getElementById('bi-target-loading');
    const submitButton = document.getElementById('bi-target-submit');
    const feedbackBlock = document.getElementById('bi-target-feedback');

    if (loader) {
        if (isLoading) {
            loader.classList.remove('d-none');
        } else {
            loader.classList.add('d-none');
        }
    }

    if (submitButton) {
        submitButton.disabled = isLoading;
    }

    if (isLoading && feedbackBlock) {
        feedbackBlock.classList.add('d-none');
        feedbackBlock.textContent = '';
    }
}

function renderBusinessIntelligence(payload, labels) {
    const data = payload?.data || {};
    const dateBadge = document.getElementById('dashboard-bi-date');
    const summary = document.getElementById('dashboard-bi-summary');
    const spotsContainer = document.getElementById('dashboard-bi-spots');
    const pricingContainer = document.getElementById('dashboard-bi-pricing');
    const eventsContainer = document.getElementById('dashboard-bi-events');

    if (!summary || !spotsContainer || !pricingContainer || !eventsContainer) {
        console.log('Missing containers: summary=', !!summary, 'spots=', !!spotsContainer, 'pricing=', !!pricingContainer, 'events=', !!eventsContainer);
        return;
    }

    renderSearchFeedback(payload, labels);

    if (dateBadge) {
        dateBadge.textContent = payload?.date || '-';
    }

    const revenuePrediction = data.revenue_prediction || {};
    window.__dashboardRevenuePrediction = revenuePrediction;
    window.__dashboardEventRevenueDetails = new Map();
    summary.innerHTML = `
        <div class="col-12 col-md-4">
            <div class="slot-summary-card">
                <div class="slot-summary-label">${labels.biPredictedRevenueLabel}</div>
                <div class="slot-summary-value">${toCurrency(revenuePrediction.predicted_revenue || 0, labels.currency)}</div>
                <button type="button" class="btn btn-link btn-sm p-0 mt-1" data-revenue-breakdown-trigger="summary">${labels.biRevenueDetailsLabel}</button>
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
                <div class="small text-muted">${toCurrency(entry.current_price, labels.currency)} -> ${toCurrency(entry.suggested_price, labels.currency)}</div>
                <div class="small text-muted">${labels.biConfidenceLabel} ${Number((entry.confidence_score || 0) * 100).toFixed(0)}%</div>
            </div>
        `).join('');
    }

    const events = [...(data.event_opportunities || [])].sort((a, b) => {
        const aDate = a.start_date || '';
        const bDate = b.start_date || '';
        return aDate.localeCompare(bDate);
    });
    if (!events.length) {
        eventsContainer.innerHTML = `<div class="text-muted small">${labels.biEmptyEventsLabel}</div>`;
    } else {
        window.__dashboardEventRevenueDetails = new Map(events.map((entry) => [String(entry.event_id), entry]));
        eventsContainer.innerHTML = events.map((entry) => {
            const scoreExplain = entry.scoring_explanation || {};
            const hasImage = entry.image_url && entry.image_url.trim();
            const hasDescription = entry.description && entry.description.trim();
            const hasSource = entry.source_url && entry.source_url.trim();
            
            let factorList = '';
            if (scoreExplain.factors && Array.isArray(scoreExplain.factors)) {
                factorList = scoreExplain.factors.map(f => 
                    `<div class="small ps-2 py-1"><strong>${f.label}:</strong> ${f.score.toFixed(0)}/100 — ${f.explanation}</div>`
                ).join('');
            }
            
            return `
            <div class="list-group-item px-0 py-3 bg-transparent border-0 border-bottom">
                <div class="row g-2">
                    ${hasImage ? '<div class="col-12"><a href="' + entry.image_url + '" target="_blank" rel="noopener noreferrer" title="Afficher l\'image en taille réelle"><img src="' + entry.image_url + '" alt="' + entry.event_name + '" class="img-fluid rounded" style="max-height:220px; object-fit:contain; width:100%; background:#f8f9fa;"></a></div>' : ''}
                    <div class="col-12">
                        <div class="fw-semibold d-flex align-items-center gap-2">
                            ${entry.event_name}
                            ${entry.ai_analyzed ? '<span class="badge text-bg-primary" style="font-size:0.65rem;">' + labels.biEventScoreMethodAi + '</span>' : '<span class="badge text-bg-secondary" style="font-size:0.65rem;">…</span>'}
                        </div>
                        ${hasDescription ? '<div class="small text-muted mt-1">' + entry.description + '</div>' : ''}
                        ${hasSource ? '<div class="small mt-1"><a href="' + entry.source_url + '" target="_blank" rel="noopener noreferrer">' + labels.biEventSourceLinkLabel + '</a></div>' : ''}
                    </div>
                    <div class="col-12">
                        <div class="small text-muted"><strong>${labels.biScoreLabel} ${Number(entry.opportunity_score || 0).toFixed(1)}/100</strong>
                            ${scoreExplain.summary ? '<br><em>' + scoreExplain.summary + '</em>' : ''}
                        </div>
                        ${factorList ? '<div class="small bg-light rounded p-2 mt-2">' + factorList + '</div>' : ''}
                    </div>
                    <div class="col-12">
                        <div class="small text-muted d-flex flex-wrap align-items-center gap-2">
                            <span>${labels.biPredictedLabel} ${toCurrency(entry.predicted_revenue || 0, labels.currency)}</span>
                            <button type="button" class="btn btn-link btn-sm p-0 align-baseline" data-revenue-breakdown-trigger="event" data-event-id="${entry.event_id}" data-event-name="${entry.event_name}">${labels.biRevenueDetailsLabel}</button>
                        </div>
                        <div class="small text-muted">${labels.biEventDateLabel} ${formatDateRange(entry.start_date, entry.end_date, labels)}</div>
                        <div class="small text-muted">${labels.biEventLocationLabel} ${formatLocation(entry, labels)}</div>
                        <div class="small text-muted">${labels.biEventDistanceLabel} ${entry.distance_km !== null && entry.distance_km !== undefined ? `${Number(entry.distance_km).toFixed(1)} km` : labels.biEventUnavailableLabel}</div>
                        <div class="small text-muted">${labels.biEventAttendanceLabel} ${entry.expected_attendance || labels.biEventUnavailableLabel}</div>
                    </div>
                </div>
            </div>
            `;
        }).join('');
    }
}

async function init() {
    if (!root) {
        console.error('Root element #foodtruck-bi-page not found');
        return;
    }

    const labels = getLabels();
    initRevenueEstimateModal(labels);

    // Restore form state from localStorage
    restoreFormState();
    renderCustomKeywordTags();

    // Setup event listeners for form changes to auto-save
    const form = document.getElementById('dashboard-bi-target-form');
    if (form) {
        form.addEventListener('change', saveFormState);
        form.addEventListener('input', saveFormState);
    }

    const customKeywordsContainer = document.getElementById('bi-custom-keywords-tags');
    if (customKeywordsContainer) {
        customKeywordsContainer.addEventListener('click', (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) {
                return;
            }
            if (!target.classList.contains('bi-custom-keyword-remove')) {
                return;
            }
            removeCustomKeyword(target.dataset.keyword || '', event);
        });
    }

    // Setup custom keywords input
    const customKeywordsInput = document.getElementById('bi-custom-keywords');
    if (customKeywordsInput) {
        customKeywordsInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ',') {
                event.preventDefault();
                const value = customKeywordsInput.value.trim().replace(/[,]$/, '');
                if (value) {
                    processAndStoreCustomKeywords(value);
                    customKeywordsInput.value = '';
                }
            }
        });
        customKeywordsInput.addEventListener('blur', () => {
            commitPendingCustomKeywordsInput();
        });
        customKeywordsInput.addEventListener('paste', () => {
            setTimeout(() => {
                const value = customKeywordsInput.value.trim();
                if (value && value.includes(',')) {
                    processAndStoreCustomKeywords(value);
                    customKeywordsInput.value = '';
                }
            }, 0);
        });
    }

    const load = async () => {
        setLoadingState(true);
        try {
            const payload = await fetchBusinessIntelligence(root.dataset.biUrl, getTargetingParams());
            renderBusinessIntelligence(payload, labels);
        } catch (error) {
            console.error('Error loading business intelligence:', error);
            const eventsContainer = document.getElementById('dashboard-bi-events');
            const feedbackBlock = document.getElementById('bi-target-feedback');
            if (eventsContainer) {
                eventsContainer.innerHTML = `<div class="text-danger small">${labels.biEmptyEventsLabel}</div>`;
            }
            if (feedbackBlock) {
                feedbackBlock.classList.remove('d-none', 'alert-secondary');
                feedbackBlock.classList.add('alert-warning');
                feedbackBlock.textContent = `${labels.biEmptyEventsLabel} (Error: ${error.message})`;
            }
        } finally {
            setLoadingState(false);
        }
    };

    if (form) {
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            load();
        });
    }

    await load();
}

init();
