import apiClient from './client.js';

/**
 * Return available pickup slots for a food truck identified by slug.
 * @param {string} slug
 * @returns {Promise<Array>}
 */
export async function fetchPickupSlots(slug) {
    return apiClient.get(`/foodtrucks/${slug}/pickup-slots/`);
}
