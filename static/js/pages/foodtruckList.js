/**
 * Foodtruck List Page Logic
 * Handles loading and displaying foodtrucks on the list page
 */

import { fetchFoodtrucks } from '../api/foodtruck.js';
import {
    createFoodtruckCard,
    createEmptyState,
    createLoadingState,
    createErrorState,
} from '../components/foodtruckCard.js';

/**
 * Foodtruck List Page Controller
 */
class FoodtruckListPage {
    constructor() {
        this.container = document.getElementById('foodtruck-list');
        this.isLoading = false;
        this.currentData = null;

        if (!this.container) {
            console.error('Foodtruck list container not found');
            return;
        }

        this.init();
    }

    /**
     * Initialize the page
     */
    async init() {
        await this.loadFoodtrucks();
    }

    /**
     * Load foodtrucks from API and render them
     */
    async loadFoodtrucks() {
        if (this.isLoading) return;

        this.isLoading = true;
        this.showLoading();

        try {
            const data = await fetchFoodtrucks();
            this.currentData = data;
            this.renderFoodtrucks(data);
        } catch (error) {
            console.error('Failed to load foodtrucks:', error);
            this.showError(error.message);
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Render foodtrucks list
     * @param {Object} data - API response data
     */
    renderFoodtrucks(data) {
        if (!data || !data.results) {
            this.showEmpty();
            return;
        }

        const foodtrucks = data.results;
        if (foodtrucks.length === 0) {
            this.showEmpty();
            return;
        }

        const html = foodtrucks.map(foodtruck => createFoodtruckCard(foodtruck)).join('');
        this.container.innerHTML = `<div class="row">${html}</div>`;

        // Add pagination if needed
        if (data.next || data.previous) {
            this.addPagination(data);
        }
    }

    /**
     * Show loading state
     */
    showLoading() {
        this.container.innerHTML = `<div class="row">${createLoadingState()}</div>`;
    }

    /**
     * Show empty state
     */
    showEmpty() {
        this.container.innerHTML = `<div class="row">${createEmptyState()}</div>`;
    }

    /**
     * Show error state
     * @param {string} message - Error message
     */
    showError(message) {
        this.container.innerHTML = `<div class="row">${createErrorState(message)}</div>`;
    }

    /**
     * Add pagination controls
     * @param {Object} data - Pagination data from API
     */
    addPagination(data) {
        // This would be implemented when pagination is added to the API
        // For now, just log the pagination info
        console.log('Pagination data:', data);
    }

    /**
     * Refresh the foodtrucks list
     */
    async refresh() {
        await this.loadFoodtrucks();
    }
}

// Initialize the page when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new FoodtruckListPage();
});

// Export for potential reuse
export default FoodtruckListPage;