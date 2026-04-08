function toggleFoodtruckHeader() {
    const toggleButton = document.getElementById('foodtruck-description-toggle');
    const header = document.getElementById('foodtruck-header');
    if (!toggleButton || !header) {
        return;
    }

    const showText = toggleButton.dataset.showText || 'Show description';
    const hideText = toggleButton.dataset.hideText || 'Hide description';
    const label = toggleButton.querySelector('small') || toggleButton;

    const updateState = () => {
        const isVisible = !header.classList.contains('d-none');
        const nextText = isVisible ? hideText : showText;
        if (label) {
            label.textContent = nextText;
        }
        toggleButton.setAttribute('aria-expanded', String(isVisible));
    };

    toggleButton.addEventListener('click', () => {
        header.classList.toggle('d-none');
        updateState();
    });
    // initialize state
    updateState();
}

document.addEventListener('DOMContentLoaded', () => {
    toggleFoodtruckHeader();
});
