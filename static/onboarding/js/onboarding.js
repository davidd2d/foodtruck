/**
 * Onboarding page JavaScript
 * Handles the import form and initial processing
 */

import { createImport, pollImportStatus } from './api.js';

class OnboardingForm {
    constructor() {
        this.form = document.getElementById('import-form');
        this.submitBtn = document.getElementById('submit-btn');
        this.statusArea = document.getElementById('status-area');
        this.statusMessage = document.getElementById('status-message');
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.imageInput = document.getElementById('images');
        this.imagePreview = document.getElementById('image-preview');
        this.logoInput = document.getElementById('logo');
        this.logoPreview = document.getElementById('logo-preview');

        this.init();
    }

    init() {
        this.form.addEventListener('submit', this.handleSubmit.bind(this));
        this.imageInput.addEventListener('change', this.handleImagePreview.bind(this));
        this.logoInput?.addEventListener('change', this.handleLogoPreview.bind(this));
    }

    async handleSubmit(event) {
        event.preventDefault();

        if (!this.validateForm()) {
            return;
        }

        this.setLoading(true);
        this.updateStatus('AI is analyzing your content...');

        try {
            const formData = new FormData(this.form);
            const result = await createImport(formData);

            this.updateStatus('Processing your data...');
            const finalData = await pollImportStatus(result.id);

            // Redirect to preview page with import ID
            window.location.href = `/onboarding/preview/${finalData.id}/`;

        } catch (error) {
            this.showError(error.message);
            this.setLoading(false);
        }
    }

    handleImagePreview(event) {
        const files = Array.from(event.target.files);
        this.imagePreview.innerHTML = '';

        files.forEach((file, index) => {
            if (file.type.startsWith('image/')) {
                const container = document.createElement('div');
                container.className = 'image-container position-relative d-inline-block';

                const img = document.createElement('img');
                img.className = 'file-preview img-thumbnail';
                img.src = URL.createObjectURL(file);
                img.onload = () => URL.revokeObjectURL(img.src);

                const removeBtn = document.createElement('button');
                removeBtn.className = 'remove-file';
                removeBtn.innerHTML = '×';
                removeBtn.onclick = () => this.removeImage(index);

                container.appendChild(img);
                container.appendChild(removeBtn);
                this.imagePreview.appendChild(container);
            }
        });
        this.updateLogoPreview();
    }

    updateLogoPreview() {
        if (!this.logoPreview || !this.logoInput) {
            return;
        }

        const file = this.logoInput.files[0];
        this.logoPreview.innerHTML = '';

        if (!file || !file.type.startsWith('image/')) {
            return;
        }

        const container = document.createElement('div');
        container.className = 'image-container position-relative d-inline-block';

        const img = document.createElement('img');
        img.className = 'file-preview img-thumbnail shadow-sm';
        img.src = URL.createObjectURL(file);
        img.onload = () => URL.revokeObjectURL(img.src);

        const removeBtn = document.createElement('button');
        removeBtn.className = 'remove-file';
        removeBtn.innerHTML = '×';
        removeBtn.type = 'button';
        removeBtn.onclick = () => this.removeLogo();

        container.appendChild(img);
        container.appendChild(removeBtn);
        this.logoPreview.appendChild(container);
    }

    handleLogoPreview() {
        this.updateLogoPreview();
    }

    removeLogo() {
        if (!this.logoInput) {
            return;
        }

        this.logoInput.value = '';
        if (this.logoPreview) {
            this.logoPreview.innerHTML = '';
        }
    }

    removeImage(index) {
        const dt = new DataTransfer();
        const files = Array.from(this.imageInput.files);

        files.forEach((file, i) => {
            if (i !== index) {
                dt.items.add(file);
            }
        });

        this.imageInput.files = dt.files;
        this.handleImagePreview({ target: this.imageInput });
    }

    validateForm() {
        const rawText = this.form.raw_text.value.trim();
        if (!rawText) {
            this.showError('Please enter some content to import');
            return false;
        }

        if (rawText.length < 10) {
            this.showError('Please enter at least 10 characters of content');
            return false;
        }

        return true;
    }

    setLoading(loading) {
        this.submitBtn.disabled = loading;
        this.submitBtn.innerHTML = loading ?
            '<span class="spinner-border spinner-border-sm me-2"></span>Processing...' :
            '<i class="bi bi-magic me-2"></i>Generate My Foodtruck';

        this.statusArea.classList.toggle('d-none', !loading);
        this.loadingOverlay.style.display = loading ? 'flex' : 'none';
    }

    updateStatus(message) {
        this.statusMessage.textContent = message;
    }

    showError(message) {
        // Create alert element
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.innerHTML = `
            <i class="bi bi-exclamation-triangle me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Insert at top of form
        this.form.insertBefore(alert, this.form.firstChild);

        // Auto remove after 5 seconds
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new OnboardingForm();
});
