/**
 * Foodtruck Card Component
 * Renders a foodtruck card with image, name, description, and action buttons
 */

/**
 * Create HTML string for a foodtruck card
 * @param {Object} foodtruck - Foodtruck data object
 * @returns {string} HTML string for the card
 */
export function createFoodtruckCard(foodtruck) {
    if (!foodtruck) {
        return '';
    }

    const {
        id,
        slug,
        name,
        description,
        image,
        logo,
        is_active = true,
        address,
        phone,
        website,
    } = foodtruck;

    // Use logo if available, otherwise fallback to image or placeholder
    const displayImage = logo || image || '/static/images/foodtruck-placeholder.jpg';

    // Truncate description if too long
    const shortDescription = description && description.length > 120
        ? `${description.substring(0, 120)}...`
        : description || 'No description available';

    // Status badge
    const statusBadge = is_active
        ? '<span class="badge bg-success">Open</span>'
        : '<span class="badge bg-secondary">Closed</span>';

    return `
        <div class="col-lg-4 col-md-6 mb-4">
            <div class="card h-100 shadow-sm">
                <div class="card-img-container" style="height: 200px; overflow: hidden;">
                    <img src="${displayImage}"
                         class="card-img-top"
                         alt="${name}"
                         style="width: 100%; height: 100%; object-fit: cover;"
                         onerror="this.src='/static/images/foodtruck-placeholder.jpg'">
                </div>
                <div class="card-body d-flex flex-column">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h5 class="card-title mb-0">${name}</h5>
                        ${statusBadge}
                    </div>
                    <p class="card-text text-muted flex-grow-1">${shortDescription}</p>

                    ${address ? `<p class="card-text small text-muted mb-2"><i class="bi bi-geo-alt"></i> ${address}</p>` : ''}

                    <div class="mt-auto">
                        <div class="d-flex gap-2">
                            <a href="/foodtrucks/${slug || id}/" class="btn btn-primary btn-sm flex-fill">
                                <i class="bi bi-eye"></i> View Menu
                            </a>
                            ${phone ? `<a href="tel:${phone}" class="btn btn-outline-secondary btn-sm">
                                <i class="bi bi-telephone"></i>
                            </a>` : ''}
                            ${website ? `<a href="${website}" target="_blank" class="btn btn-outline-secondary btn-sm">
                                <i class="bi bi-globe"></i>
                            </a>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Create HTML for empty state when no foodtrucks are found
 * @param {string} message - Custom message (optional)
 * @returns {string} HTML string for empty state
 */
export function createEmptyState(message = 'No foodtrucks found') {
    return `
        <div class="col-12">
            <div class="text-center py-5">
                <div class="mb-3">
                    <i class="bi bi-shop display-1 text-muted"></i>
                </div>
                <h3 class="text-muted">${message}</h3>
                <p class="text-muted">Check back later for new foodtrucks in your area.</p>
            </div>
        </div>
    `;
}

/**
 * Create HTML for loading state
 * @returns {string} HTML string for loading spinner
 */
export function createLoadingState() {
    return `
        <div class="col-12">
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-3 text-muted">Loading foodtrucks...</p>
            </div>
        </div>
    `;
}

/**
 * Create HTML for error state
 * @param {string} errorMessage - Error message to display
 * @returns {string} HTML string for error state
 */
export function createErrorState(errorMessage = 'Failed to load foodtrucks') {
    return `
        <div class="col-12">
            <div class="alert alert-danger text-center" role="alert">
                <i class="bi bi-exclamation-triangle display-4 mb-3"></i>
                <h4 class="alert-heading">Oops!</h4>
                <p>${errorMessage}</p>
                <button type="button" class="btn btn-outline-danger" onclick="window.location.reload()">
                    <i class="bi bi-arrow-clockwise"></i> Try Again
                </button>
            </div>
        </div>
    `;
}