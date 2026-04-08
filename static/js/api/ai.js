import apiClient from './client.js';

/**
 * Generate a foodtruck with menu using AI
 * @param {Object} data - Generation parameters
 * @param {string} data.concept - Foodtruck concept
 * @param {string} [data.cuisine_type] - Cuisine type
 * @param {string} [data.price_range] - Price range
 * @param {Array<string>} [data.dietary_tags] - Dietary preferences
 * @returns {Promise<Object>} Generated foodtruck data
 */
export async function generateFoodtruck(data) {
    return apiClient.post('/onboarding/generate-foodtruck/', data);
}

/**
 * Create foodtruck with menu
 * @param {Object} foodtruckData - Foodtruck data to save
 * @returns {Promise<Object>} Created foodtruck
 */
export async function createFoodtruckWithMenu(foodtruckData) {
    return apiClient.post('/foodtrucks/create-with-menu/', foodtruckData);
}