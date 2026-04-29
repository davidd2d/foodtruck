export function extractCategoryIdFromChip(chip) {
    const href = chip.getAttribute('href') || '';
    const anchorPart = href.includes('#') ? href.split('#')[1] : '';
    const match = anchorPart.match(/^category-(\d+)$/);
    return match ? match[1] : null;
}

export function collectCategoryChips(selector = '.foodtruck-category-chip') {
    const chips = Array.from(document.querySelectorAll(selector));
    chips.forEach((chip) => {
        const categoryId = extractCategoryIdFromChip(chip);
        if (categoryId) {
            chip.dataset.categoryId = categoryId;
        }
    });
    return chips;
}

export function applyCategoryChipActiveState(categoryChips, activeCategoryId, clearCategoryFilterButton) {
    categoryChips.forEach((chip) => {
        const chipCategoryId = chip.dataset.categoryId || '';
        const isActive = activeCategoryId && chipCategoryId === activeCategoryId;
        chip.classList.toggle('active', Boolean(isActive));
        chip.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    if (clearCategoryFilterButton) {
        clearCategoryFilterButton.classList.toggle('d-none', !activeCategoryId);
    }
}
