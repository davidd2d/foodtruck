/**
 * API module for onboarding functionality
 * Handles all API calls to the backend
 */

const API_BASE = '/api/onboarding/';

/**
 * Create a new onboarding import
 * @param {FormData} formData - Form data with raw_text, images, source_url
 * @returns {Promise<Object>} - API response with import data
 */
export async function createImport(formData) {
    try {
        const response = await fetch(`${API_BASE}imports/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'same-origin',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create import');
        }

        return await response.json();
    } catch (error) {
        console.error('Error creating import:', error);
        throw error;
    }
}

/**
 * Get import status and data
 * @param {number} importId - Import ID
 * @returns {Promise<Object>} - Import data
 */
export async function getImportStatus(importId) {
    try {
        const response = await fetch(`${API_BASE}imports/${importId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error('Failed to get import status');
        }

        return await response.json();
    } catch (error) {
        console.error('Error getting import status:', error);
        throw error;
    }
}

/**
 * Get preview data for an import
 * @param {number} importId - Import ID
 * @returns {Promise<Object>} - Preview data
 */
export async function getImportPreview(importId) {
    try {
        const response = await fetch(`${API_BASE}imports/${importId}/preview/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'same-origin'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to get preview');
        }

        return await response.json();
    } catch (error) {
        console.error('Error getting preview:', error);
        throw error;
    }
}

/**
 * Create foodtruck from import data
 * @param {number} importId - Import ID
 * @returns {Promise<Object>} - Creation result
 */
export async function createFromImport(importId) {
    try {
        const response = await fetch(`${API_BASE}imports/${importId}/create/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'same-origin'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to create foodtruck');
        }

        return await response.json();
    } catch (error) {
        console.error('Error creating foodtruck:', error);
        throw error;
    }
}

/**
 * Poll import status until completed
 * @param {number} importId - Import ID
 * @param {number} maxAttempts - Maximum polling attempts
 * @param {number} interval - Polling interval in ms
 * @returns {Promise<Object>} - Final import data
 */
export async function pollImportStatus(importId, maxAttempts = 30, interval = 2000) {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            const data = await getImportStatus(importId);

            if (data.status === 'completed') {
                return data;
            }

            if (data.status === 'failed') {
                throw new Error('Import processing failed');
            }

            // Wait before next attempt
            await new Promise(resolve => setTimeout(resolve, interval));
        } catch (error) {
            if (attempt === maxAttempts - 1) {
                throw error;
            }
            await new Promise(resolve => setTimeout(resolve, interval));
        }
    }

    throw new Error('Import processing timeout');
}

/**
 * Get CSRF token from the page
 * @returns {string} - CSRF token
 */
function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}
