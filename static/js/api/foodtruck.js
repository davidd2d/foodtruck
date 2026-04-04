/**
 * Foodtruck API module
 * Handles all foodtruck-related API calls
 */

import apiClient from './client.js';

/**
 * Fetch all foodtrucks
 * @param {Object} params - Query parameters (pagination, filters, etc.)
 * @returns {Promise<Object>} Foodtrucks data with pagination info
 */
export async function fetchFoodtrucks(params = {}) {
    try {
        return await apiClient.get('/foodtrucks/', params);
    } catch (error) {
        console.error('Error fetching foodtrucks:', error);
        throw error;
    }
}

/**
 * Fetch single foodtruck by ID
 * @param {number|string} id - Foodtruck ID
 * @returns {Promise<Object>} Foodtruck data
 */
export async function fetchFoodtruck(id) {
    try {
        return await apiClient.get(`/foodtrucks/${id}/`);
    } catch (error) {
        console.error(`Error fetching foodtruck ${id}:`, error);
        throw error;
    }
}

/**
 * Search foodtrucks
 * @param {string} query - Search query
 * @param {Object} additionalParams - Additional query parameters
 * @returns {Promise<Object>} Search results
 */
export async function searchFoodtrucks(query, additionalParams = {}) {
    try {
        return await apiClient.get('/foodtrucks/', {
            search: query,
            ...additionalParams,
        });
    } catch (error) {
        console.error('Error searching foodtrucks:', error);
        throw error;
    }
}

/**
 * Get foodtrucks by location (if location filtering is implemented)
 * @param {Object} location - Location parameters (lat, lng, radius, etc.)
 * @returns {Promise<Object>} Filtered foodtrucks
 */
export async function fetchFoodtrucksByLocation(location) {
    try {
        return await apiClient.get('/foodtrucks/', {
            ...location,
        });
    } catch (error) {
        console.error('Error fetching foodtrucks by location:', error);
        throw error;
    }
}