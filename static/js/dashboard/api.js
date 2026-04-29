function buildUrl(url, params = {}) {
    const finalUrl = new URL(url, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            finalUrl.searchParams.set(key, value);
        }
    });
    return finalUrl.toString();
}

async function getJson(url, params = {}) {
    const response = await fetch(buildUrl(url, params), {
        credentials: 'same-origin',
        headers: {
            Accept: 'application/json',
        },
    });

    if (!response.ok) {
        throw new Error(`Dashboard API request failed: ${response.status}`);
    }

    return response.json();
}

export function fetchKpis(url, range, categoryId = null, displayMode = null) {
    return getJson(url, { range, category_id: categoryId, display_mode: displayMode });
}

export function fetchRevenue(url, range, interval, categoryId = null, displayMode = null) {
    return getJson(url, { range, interval, category_id: categoryId, display_mode: displayMode });
}

export function fetchOrders(url, range, limit = 20, categoryId = null, displayMode = null) {
    return getJson(url, { range, limit, category_id: categoryId, display_mode: displayMode });
}

export function fetchMenuPerformance(url, range, limit = 10, categoryId = null, displayMode = null) {
    return getJson(url, { range, limit, category_id: categoryId, display_mode: displayMode });
}

export function fetchMenuCategoryPerformance(url, range, limit = 8, categoryId = null, displayMode = null) {
    return getJson(url, { range, limit, category_id: categoryId, display_mode: displayMode });
}

export function fetchSlotPerformance(url, range, categoryId = null) {
    return getJson(url, { range, category_id: categoryId });
}

export function fetchSlotUtilization(url, range, categoryId = null) {
    return getJson(url, { range, category_id: categoryId });
}

export function fetchSlotRevenue(url, range, categoryId = null, displayMode = null) {
    return getJson(url, { range, category_id: categoryId, display_mode: displayMode });
}

export function fetchSlotHourly(url, range, categoryId = null, displayMode = null) {
    return getJson(url, { range, category_id: categoryId, display_mode: displayMode });
}

export function fetchSlotHeatmap(url, range, categoryId = null) {
    return getJson(url, { range, category_id: categoryId });
}

export function fetchSlotInsights(url, categoryId = null) {
    return getJson(url, { category_id: categoryId });
}

export function fetchSlotRecommendations(url, categoryId = null) {
    return getJson(url, { category_id: categoryId });
}

export function fetchOptionPerformance(url, range, limit = 10, categoryId = null, displayMode = null) {
    return getJson(url, { range, limit, category_id: categoryId, display_mode: displayMode });
}
