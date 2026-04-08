import { generateFoodtruck, createFoodtruckWithMenu } from '../api/ai.js';
import { renderFoodtruckPreview, getEditedFoodtruckData, setupMenuEditing } from '../components/foodtruckPreview.js';

const aiForm = document.getElementById('ai-form');
const generateBtn = document.getElementById('generate-btn');
const errorMessage = document.getElementById('error-message');
const previewContainer = document.getElementById('preview-container');
const backToEditBtn = document.getElementById('back-to-edit');
const saveBtn = document.getElementById('save-btn');
const foodtruckPreview = document.getElementById('foodtruck-preview');

let generatedData = null;

/**
 * Show loading state
 */
function showLoading() {
    generateBtn.disabled = true;
    generateBtn.querySelector('.spinner-border').classList.remove('d-none');
    generateBtn.textContent = ' Generating...';
    errorMessage.classList.add('d-none');
}

/**
 * Hide loading state
 */
function hideLoading() {
    generateBtn.disabled = false;
    generateBtn.querySelector('.spinner-border').classList.add('d-none');
    generateBtn.textContent = 'Generate my foodtruck';
}

/**
 * Show error message
 * @param {string} message
 */
function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.remove('d-none');
}

/**
 * Switch to preview mode
 * @param {Object} data
 */
function showPreview(data) {
    generatedData = data;
    foodtruckPreview.innerHTML = renderFoodtruckPreview(data);
    document.querySelector('.container').classList.add('d-none');
    previewContainer.classList.remove('d-none');

    // Setup editing
    setupMenuEditing(validateData);
    validateData();
}

/**
 * Switch back to input mode
 */
function showInput() {
    previewContainer.classList.add('d-none');
    document.querySelector('.container').classList.remove('d-none');
    generatedData = null;
}

/**
 * Validate current data
 */
function validateData() {
    const data = getEditedFoodtruckData();

    // Basic validation
    const isValid = data.name &&
                   data.description &&
                   data.menu.length > 0 &&
                   data.menu.every(cat => cat.items.length > 0 && cat.items.every(item => item.name && item.price > 0));

    saveBtn.disabled = !isValid;
}

/**
 * Handle form submission
 * @param {Event} e
 */
async function handleGenerate(e) {
    e.preventDefault();

    const formData = new FormData(aiForm);
    const data = {
        concept: formData.get('concept'),
        cuisine_type: formData.get('cuisine_type') || undefined,
        price_range: formData.get('price_range') || undefined,
        dietary_tags: formData.getAll('dietary_tags') || []
    };

    showLoading();

    try {
        const result = await generateFoodtruck(data);
        showPreview(result);
    } catch (error) {
        showError(error.message || 'Failed to generate foodtruck. Please try again.');
    } finally {
        hideLoading();
    }
}

/**
 * Handle save submission
 */
async function handleSave() {
    const data = getEditedFoodtruckData();

    saveBtn.disabled = true;
    saveBtn.querySelector('.spinner-border').classList.remove('d-none');
    saveBtn.textContent = ' Creating...';

    try {
        const result = await createFoodtruckWithMenu(data);
        // Redirect to foodtruck detail or dashboard
        window.location.href = result.url || '/foodtrucks/';
    } catch (error) {
        showError(error.message || 'Failed to create foodtruck. Please try again.');
        saveBtn.disabled = false;
        saveBtn.querySelector('.spinner-border').classList.add('d-none');
        saveBtn.textContent = 'Create my foodtruck';
    }
}

/**
 * Initialize event listeners
 */
function init() {
    aiForm.addEventListener('submit', handleGenerate);
    backToEditBtn.addEventListener('click', showInput);
    saveBtn.addEventListener('click', handleSave);
}

init();