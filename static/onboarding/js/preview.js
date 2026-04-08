/**
 * Preview page JavaScript
 * Handles editing and final creation of foodtruck
 */

import { getImportPreview, createFromImport } from './api.js';

class FoodtruckPreview {
    constructor() {
        this.importId = this.getImportIdFromUrl();
        this.previewContent = document.getElementById('preview-content');
        this.loadingState = document.getElementById('loading-state');
        this.successState = document.getElementById('success-state');
        this.createBtn = document.getElementById('create-btn');
        this.backBtn = document.getElementById('back-btn');
        this.addCategoryBtn = document.getElementById('add-category-btn');

        this.data = null;
        this.init();
    }

    init() {
        this.loadPreview();
        this.setupEventListeners();
    }

    getImportIdFromUrl() {
        const pathParts = window.location.pathname.split('/');
        return pathParts[pathParts.length - 2]; // Extract ID from /onboarding/preview/{id}/
    }

    async loadPreview() {
        try {
            this.data = await getImportPreview(this.importId);
            this.renderPreview();
        } catch (error) {
            this.showError('Failed to load preview: ' + error.message);
        }
    }

    renderPreview() {
        // Render foodtruck details
        this.renderFoodtruck();

        // Render menu
        this.renderMenu();

        // Render branding
        this.renderBranding();

        // Setup editable fields
        this.setupEditableFields();
    }

    renderFoodtruck() {
        const foodtruck = this.data.foodtruck || {};
        const container = document.querySelector('[data-field="foodtruck.name"]').closest('.card-body');

        // Update name
        const nameField = container.querySelector('[data-field="foodtruck.name"]');
        nameField.textContent = foodtruck.name || '';

        // Update cuisine
        const cuisineField = container.querySelector('[data-field="foodtruck.cuisine_type"]');
        cuisineField.textContent = foodtruck.cuisine_type || '';

        // Update description
        const descField = container.querySelector('[data-field="foodtruck.description"]');
        descField.textContent = foodtruck.description || '';

        // Update preferences
        this.renderPreferences(foodtruck.preferences || []);
    }

    renderPreferences(preferences) {
        const tagsContainer = document.getElementById('preferences-tags');
        const input = document.getElementById('preference-input');

        // Clear existing tags except input
        Array.from(tagsContainer.children).forEach(child => {
            if (child !== input) {
                child.remove();
            }
        });

        // Add preference tags
        preferences.forEach(pref => {
            const tag = document.createElement('span');
            tag.className = 'tag';
            tag.innerHTML = `
                ${pref}
                <span class="tag-remove" data-preference="${pref}">×</span>
            `;
            tagsContainer.insertBefore(tag, input);
        });

        // Setup preference input
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                const value = input.value.trim();
                if (value && !preferences.includes(value)) {
                    preferences.push(value);
                    this.renderPreferences(preferences);
                    input.value = '';
                }
            }
        });

        // Setup tag removal
        tagsContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('tag-remove')) {
                const pref = e.target.dataset.preference;
                const index = preferences.indexOf(pref);
                if (index > -1) {
                    preferences.splice(index, 1);
                    this.renderPreferences(preferences);
                }
            }
        });
    }

    renderMenu() {
        const menu = this.data.menu || [];
        const container = document.getElementById('menu-content');
        container.innerHTML = '';

        menu.forEach((category, categoryIndex) => {
            const categoryDiv = document.createElement('div');
            categoryDiv.className = 'category-section mb-4';
            categoryDiv.dataset.categoryIndex = categoryIndex;

            categoryDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h4 class="mb-0">
                        <span class="editable-field category-name" data-field="menu.${categoryIndex}.category" contenteditable="true">${category.category || ''}</span>
                    </h4>
                    <button class="btn btn-outline-danger btn-sm remove-category-btn">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
                <div class="menu-items">
                    ${this.renderMenuItems(category.items || [], categoryIndex)}
                    <button class="btn add-item-btn w-100" data-category-index="${categoryIndex}">
                        <i class="bi bi-plus-circle me-2"></i>Add Menu Item
                    </button>
                </div>
            `;

            container.appendChild(categoryDiv);
        });
    }

    renderMenuItems(items, categoryIndex) {
        return items.map((item, itemIndex) => `
            <div class="menu-item" data-item-index="${itemIndex}">
                <div class="row">
                    <div class="col-md-6 mb-2">
                        <label class="form-label fw-bold">Name</label>
                        <div class="editable-field" data-field="menu.${categoryIndex}.items.${itemIndex}.name" contenteditable="true">${item.name || ''}</div>
                    </div>
                    <div class="col-md-3 mb-2">
                        <label class="form-label fw-bold">Price</label>
                        <div class="editable-field" data-field="menu.${categoryIndex}.items.${itemIndex}.price" contenteditable="true">$${item.price || '0.00'}</div>
                    </div>
                    <div class="col-md-3 mb-2 d-flex align-items-end">
                        <button class="btn btn-outline-danger btn-sm remove-item-btn">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="mb-2">
                    <label class="form-label fw-bold">Description</label>
                    <div class="editable-field" data-field="menu.${categoryIndex}.items.${itemIndex}.description" contenteditable="true">${item.description || ''}</div>
                </div>
            </div>
        `).join('');
    }

    renderBranding() {
        const branding = this.data.branding || {};

        // Update color inputs
        const primaryColor = document.getElementById('primary-color');
        const secondaryColor = document.getElementById('secondary-color');
        const primaryPreview = document.getElementById('primary-color-preview');
        const secondaryPreview = document.getElementById('secondary-color-preview');

        primaryColor.value = branding.primary_color || '#000000';
        secondaryColor.value = branding.secondary_color || '#ffffff';
        primaryPreview.style.backgroundColor = primaryColor.value;
        secondaryPreview.style.backgroundColor = secondaryColor.value;

        // Update style
        const styleField = document.querySelector('[data-field="branding.style"]');
        styleField.textContent = branding.style || 'Classic';
    }

    setupEditableFields() {
        // Color inputs
        document.getElementById('primary-color').addEventListener('input', (e) => {
            document.getElementById('primary-color-preview').style.backgroundColor = e.target.value;
        });

        document.getElementById('secondary-color').addEventListener('input', (e) => {
            document.getElementById('secondary-color-preview').style.backgroundColor = e.target.value;
        });
    }

    setupEventListeners() {
        // Create button
        this.createBtn.addEventListener('click', this.handleCreate.bind(this));

        // Back button
        this.backBtn.addEventListener('click', () => {
            window.location.href = '/onboarding/import/';
        });

        // Add category button
        this.addCategoryBtn.addEventListener('click', this.addCategory.bind(this));

        // Dynamic event listeners for menu items
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-category-btn')) {
                this.removeCategory(e.target);
            } else if (e.target.classList.contains('remove-item-btn')) {
                this.removeMenuItem(e.target);
            } else if (e.target.classList.contains('add-item-btn')) {
                this.addMenuItem(e.target);
            }
        });
    }

    addCategory() {
        if (!this.data.menu) this.data.menu = [];
        this.data.menu.push({
            category: 'New Category',
            items: []
        });
        this.renderMenu();
    }

    removeCategory(button) {
        const categoryDiv = button.closest('.category-section');
        const index = parseInt(categoryDiv.dataset.categoryIndex);
        this.data.menu.splice(index, 1);
        this.renderMenu();
    }

    addMenuItem(button) {
        const categoryIndex = parseInt(button.dataset.categoryIndex);
        if (!this.data.menu[categoryIndex].items) {
            this.data.menu[categoryIndex].items = [];
        }
        this.data.menu[categoryIndex].items.push({
            name: 'New Item',
            description: '',
            price: '0.00'
        });
        this.renderMenu();
    }

    removeMenuItem(button) {
        const menuItem = button.closest('.menu-item');
        const itemIndex = parseInt(menuItem.dataset.itemIndex);
        const categoryDiv = button.closest('.category-section');
        const categoryIndex = parseInt(categoryDiv.dataset.categoryIndex);

        this.data.menu[categoryIndex].items.splice(itemIndex, 1);
        this.renderMenu();
    }

    async handleCreate() {
        this.setLoading(true);

        try {
            // Collect edited data
            const editedData = this.collectEditedData();

            // For now, just create from import (editing will be handled in future)
            const result = await createFromImport(this.importId);

            this.showSuccess(result);

        } catch (error) {
            this.showError('Failed to create foodtruck: ' + error.message);
            this.setLoading(false);
        }
    }

    collectEditedData() {
        // Collect data from editable fields
        const editedData = {
            foodtruck: { ...this.data.foodtruck },
            menu: [...this.data.menu],
            branding: { ...this.data.branding }
        };

        // Update from editable fields
        document.querySelectorAll('.editable-field').forEach(field => {
            const path = field.dataset.field;
            const value = field.textContent.trim();
            this.setNestedValue(editedData, path, value);
        });

        // Update colors
        editedData.branding.primary_color = document.getElementById('primary-color').value;
        editedData.branding.secondary_color = document.getElementById('secondary-color').value;

        return editedData;
    }

    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        let current = obj;

        for (let i = 0; i < keys.length - 1; i++) {
            const key = keys[i];
            if (key.includes('[')) {
                // Handle array indices
                const [arrayKey, index] = key.split('[');
                const arrayIndex = parseInt(index.replace(']', ''));
                if (!current[arrayKey]) current[arrayKey] = [];
                if (!current[arrayKey][arrayIndex]) current[arrayKey][arrayIndex] = {};
                current = current[arrayKey][arrayIndex];
            } else {
                if (!current[key]) current[key] = {};
                current = current[key];
            }
        }

        current[keys[keys.length - 1]] = value;
    }

    setLoading(loading) {
        this.previewContent.classList.toggle('d-none', loading);
        this.loadingState.classList.toggle('d-none', !loading);
        this.createBtn.disabled = loading;
    }

    showSuccess(result) {
        this.loadingState.classList.add('d-none');
        this.successState.classList.remove('d-none');
    }

    showError(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show position-fixed';
        alert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alert.innerHTML = `
            <i class="bi bi-exclamation-triangle me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alert);

        setTimeout(() => {
            alert.remove();
        }, 5000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new FoodtruckPreview();
});