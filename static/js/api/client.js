/**
 * Centralized API client for making HTTP requests
 * Handles JSON parsing, errors, and CSRF tokens
 */

class ApiClient {
    constructor() {
        this.baseURL = '/api';
    }

    /**
     * Get CSRF token from meta tag or global variable
     * @returns {string|null} CSRF token
     */
    getCsrfToken() {
        // Try to get from global variable set in base template
        if (window.CSRF_TOKEN) {
            return window.CSRF_TOKEN;
        }

        // Fallback: try to get from meta tag
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            return metaToken.getAttribute('content');
        }

        return null;
    }

    /**
     * Build full URL for API endpoint
     * @param {string} endpoint - API endpoint (e.g., '/foodtrucks/')
     * @returns {string} Full URL
     */
    buildUrl(endpoint) {
        if (endpoint.startsWith('http')) {
            return endpoint;
        }
        return `${this.baseURL}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    }

    /**
     * Handle API response
     * @param {Response} response - Fetch response object
     * @returns {Promise<Object>} Parsed JSON data
     * @throws {Error} If response is not ok
     */
    async handleResponse(response) {
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;

            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorData.message || errorMessage;
            } catch (e) {
                // If we can't parse error response, use default message
            }

            throw new Error(errorMessage);
        }

        // Handle empty responses (204 No Content)
        if (response.status === 204) {
            return null;
        }

        return await response.json();
    }

    /**
     * Make HTTP request with common configuration
     * @param {string} url - Request URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Object>} Response data
     */
    async request(url, options = {}) {
        const config = {
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        // Add CSRF token for non-GET requests
        if (config.method && config.method !== 'GET') {
            const csrfToken = this.getCsrfToken();
            if (csrfToken) {
                config.headers['X-CSRFToken'] = csrfToken;
            }
        }

        try {
            const response = await fetch(url, config);
            return await this.handleResponse(response);
        } catch (error) {
            // Re-throw network errors or API errors
            if (error.message.includes('HTTP')) {
                throw error;
            }
            throw new Error(`Network error: ${error.message}`);
        }
    }

    /**
     * GET request
     * @param {string} endpoint - API endpoint
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Response data
     */
    async get(endpoint, params = {}) {
        let url = this.buildUrl(endpoint);

        // Add query parameters
        if (Object.keys(params).length > 0) {
            const searchParams = new URLSearchParams();
            Object.entries(params).forEach(([key, value]) => {
                if (value !== null && value !== undefined) {
                    searchParams.append(key, value);
                }
            });
            url += `?${searchParams.toString()}`;
        }

        return this.request(url, { method: 'GET' });
    }

    /**
     * POST request
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise<Object>} Response data
     */
    async post(endpoint, data = {}) {
        return this.request(this.buildUrl(endpoint), {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * PUT request
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise<Object>} Response data
     */
    async put(endpoint, data = {}) {
        return this.request(this.buildUrl(endpoint), {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    /**
     * PATCH request
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise<Object>} Response data
     */
    async patch(endpoint, data = {}) {
        return this.request(this.buildUrl(endpoint), {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    /**
     * DELETE request
     * @param {string} endpoint - API endpoint
     * @returns {Promise<Object>} Response data
     */
    async delete(endpoint) {
        return this.request(this.buildUrl(endpoint), { method: 'DELETE' });
    }
}

// Export singleton instance
const apiClient = new ApiClient();
export default apiClient;