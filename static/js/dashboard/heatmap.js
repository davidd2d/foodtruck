const DEFAULT_WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function getOrderCount(rows, weekday, hour) {
    const row = rows.find((entry) => Number(entry.weekday) === weekday && Number(entry.hour) === hour);
    return row ? Number(row.orders || 0) : 0;
}

function getIntensityClass(value, maxValue) {
    if (maxValue <= 0 || value <= 0) {
        return 'heatmap-intensity-0';
    }
    const ratio = value / maxValue;
    if (ratio < 0.25) {
        return 'heatmap-intensity-1';
    }
    if (ratio < 0.5) {
        return 'heatmap-intensity-2';
    }
    if (ratio < 0.75) {
        return 'heatmap-intensity-3';
    }
    return 'heatmap-intensity-4';
}

export function renderHeatmap(container, rows = [], labels = {}) {
    if (!container) {
        return;
    }

    const weekdayLabels = Array.isArray(labels.weekdayShortLabels) && labels.weekdayShortLabels.length === 7
        ? labels.weekdayShortLabels
        : DEFAULT_WEEKDAY_LABELS;
    const ordersLabel = labels.ordersLabel || 'orders';

    const maxValue = rows.reduce((max, row) => Math.max(max, Number(row.orders || 0)), 0);

    const header = ['<div class="heatmap-cell heatmap-head"></div>'];
    for (let hour = 0; hour < 24; hour += 1) {
        header.push(`<div class="heatmap-cell heatmap-head">${hour}</div>`);
    }

    const cells = [header.join('')];
    for (let weekday = 0; weekday < 7; weekday += 1) {
        cells.push(`<div class="heatmap-cell heatmap-head">${weekdayLabels[weekday]}</div>`);
        for (let hour = 0; hour < 24; hour += 1) {
            const orders = getOrderCount(rows, weekday, hour);
            const intensityClass = getIntensityClass(orders, maxValue);
            cells.push(`<div class="heatmap-cell ${intensityClass}" title="${weekdayLabels[weekday]} ${hour}:00 - ${orders} ${ordersLabel}">${orders || ''}</div>`);
        }
    }

    container.innerHTML = cells.join('');
}
