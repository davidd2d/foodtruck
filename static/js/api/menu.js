import apiClient from './client.js';

/**
 * Fetch the menu for a specific foodtruck by slug.
 * @param {string} slug
 * @returns {Promise<Object>}
 */
export async function fetchFoodtruckMenu(slug) {
    return apiClient.get(`/foodtrucks/${slug}/menu/`);
}

export async function fetchFoodtruckPickupSlots(slug) {
    return apiClient.get(`/orders/foodtrucks/${slug}/pickup-slots/`);
}
