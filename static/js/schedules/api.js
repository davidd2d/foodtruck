const API_BASE = '/api/schedules/';

const defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
};

function handleErrors(response) {
    if (response.ok) {
        return response.json().catch(() => ({}));
    }

    return response.json().then((payload) => {
        const error = new Error('API_ERROR');
        error.payload = payload;
        error.status = response.status;
        throw error;
    });
}

export async function fetchSchedules() {
    const response = await fetch(API_BASE, {
        method: 'GET',
        headers: defaultHeaders,
        credentials: 'same-origin'
    });
    return handleErrors(response);
}

export async function createSchedule(schedule) {
    const response = await fetch(API_BASE, {
        method: 'POST',
        headers: {
            ...defaultHeaders,
            'X-CSRFToken': window.CSRF_TOKEN
        },
        credentials: 'same-origin',
        body: JSON.stringify(schedule)
    });
    return handleErrors(response);
}

export async function updateSchedule(scheduleId, schedule) {
    const response = await fetch(`${API_BASE}${scheduleId}/`, {
        method: 'PATCH',
        headers: {
            ...defaultHeaders,
            'X-CSRFToken': window.CSRF_TOKEN
        },
        credentials: 'same-origin',
        body: JSON.stringify(schedule)
    });
    return handleErrors(response);
}

export async function deleteSchedule(scheduleId) {
    const response = await fetch(`${API_BASE}${scheduleId}/`, {
        method: 'DELETE',
        headers: {
            ...defaultHeaders,
            'X-CSRFToken': window.CSRF_TOKEN
        },
        credentials: 'same-origin'
    });
    if (!response.ok) {
        const payload = await response.json();
        const error = new Error('API_ERROR');
        error.payload = payload;
        error.status = response.status;
        throw error;
    }
    return null;
}
