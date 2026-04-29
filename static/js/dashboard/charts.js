let revenueChart = null;
let menuCategoryChart = null;
let optionsChart = null;

export function initRevenueChart(canvas, label = 'Revenue') {
    if (!canvas) {
        return null;
    }

    const context = canvas.getContext('2d');
    revenueChart = new Chart(context, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label,
                    data: [],
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                },
            },
            plugins: {
                legend: {
                    display: false,
                },
            },
        },
    });

    return revenueChart;
}

export function updateRevenueChart(points = []) {
    if (!revenueChart) {
        return;
    }

    revenueChart.data.labels = points.map((point) => point.date);
    revenueChart.data.datasets[0].data = points.map((point) => Number(point.revenue || 0));
    revenueChart.update();
}

export function initMenuCategoryChart(canvas, label = 'Revenue by category') {
    if (!canvas) {
        return null;
    }

    const context = canvas.getContext('2d');
    menuCategoryChart = new Chart(context, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label,
                    data: [],
                    backgroundColor: 'rgba(25, 135, 84, 0.35)',
                    borderColor: '#198754',
                    borderWidth: 1,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                },
            },
            plugins: {
                legend: {
                    display: false,
                },
            },
        },
    });

    return menuCategoryChart;
}

export function updateMenuCategoryChart(rows = []) {
    if (!menuCategoryChart) {
        return;
    }

    menuCategoryChart.data.labels = rows.map((row) => row.category_name || 'N/A');
    menuCategoryChart.data.datasets[0].data = rows.map((row) => Number(row.revenue_generated || 0));
    menuCategoryChart.update();
}

export function initOptionsChart(canvas, label = 'Revenue from options') {
    if (!canvas) {
        return null;
    }

    const context = canvas.getContext('2d');
    optionsChart = new Chart(context, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label,
                    data: [],
                    backgroundColor: 'rgba(111, 66, 193, 0.30)',
                    borderColor: '#6f42c1',
                    borderWidth: 1,
                },
            ],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true,
                },
            },
            plugins: {
                legend: {
                    display: false,
                },
            },
        },
    });

    return optionsChart;
}

export function updateOptionsChart(rows = []) {
    if (!optionsChart) {
        return;
    }

    optionsChart.data.labels = rows.map((row) => row.option_name || 'N/A');
    optionsChart.data.datasets[0].data = rows.map((row) => Number(row.total_revenue || 0));
    optionsChart.update();
}
