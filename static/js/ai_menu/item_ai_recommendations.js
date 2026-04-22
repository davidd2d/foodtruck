import apiClient from '../api/client.js';
import { getDatasetTranslations } from '../i18n.js';

class ItemAIRecommendations {
    constructor() {
        this.analyzeSelector = '.js-ai-analyze-button';
        this.decisionSelector = '.js-ai-recommendation-action';
        this.app = document.getElementById('ai-menu-dashboard-app');
        this.translations = getDatasetTranslations(this.app, {
            loadingRecommendationsMessage: 'Chargement des recommandations IA...',
            analyzeErrorMessage: 'Impossible d\'analyser cet article.',
            decisionErrorMessage: 'Impossible de mettre à jour cette recommandation.',
        });
        if (!document.querySelector(this.analyzeSelector) && !document.querySelector(this.decisionSelector)) {
            return;
        }

        document.addEventListener('click', (event) => {
            const analyzeButton = event.target.closest(this.analyzeSelector);
            if (analyzeButton) {
                event.preventDefault();
                this.handleAnalyze(analyzeButton);
                return;
            }

            const decisionButton = event.target.closest(this.decisionSelector);
            if (decisionButton) {
                event.preventDefault();
                this.handleDecision(decisionButton);
            }
        });
    }

    async handleAnalyze(button) {
        if (button.disabled) {
            return;
        }

        const panelId = button.dataset.panelTarget;
        const analyzeUrl = button.dataset.analyzeUrl;
        const panel = document.getElementById(panelId);
        const defaultLabel = button.dataset.defaultLabel || button.textContent.trim();
        const loadingLabel = button.dataset.loadingLabel || 'Analyzing...';

        if (!panel || !analyzeUrl) {
            return;
        }

        button.disabled = true;
        button.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${loadingLabel}`;
        panel.innerHTML = this.buildLoadingState();

        try {
            const response = await apiClient.request(analyzeUrl, {
                method: 'POST',
            });

            if (!response.success) {
                throw new Error(response.message || this.translations.analyzeErrorMessage);
            }

            panel.innerHTML = response.html;
        } catch (error) {
            panel.innerHTML = this.buildErrorState(error.message || this.translations.analyzeErrorMessage);
        } finally {
            button.disabled = false;
            button.textContent = defaultLabel;
        }
    }

    async handleDecision(button) {
        if (button.disabled) {
            return;
        }

        const panel = button.closest('[id^="ai-panel-"]');
        const actionUrl = button.dataset.actionUrl;
        const decision = button.dataset.decision;

        if (!panel || !actionUrl || !decision) {
            return;
        }

        this.setDecisionButtonsState(panel, true);
        panel.innerHTML = this.buildLoadingState();

        try {
            const csrfToken = apiClient.getCsrfToken();
            const body = new URLSearchParams({ decision });
            const response = await apiClient.request(actionUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Accept': 'application/json',
                    ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                },
                body: body.toString(),
            });

            if (!response.success) {
                throw new Error(response.message || this.translations.decisionErrorMessage);
            }

            panel.innerHTML = response.html;
        } catch (error) {
            panel.innerHTML = this.buildErrorState(error.message || this.translations.decisionErrorMessage);
        }
    }

    buildLoadingState() {
        return `
            <div class="border rounded bg-light-subtle p-3 text-muted small">
                <div class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></div>
                ${this.translations.loadingRecommendationsMessage}
            </div>
        `;
    }

    setDecisionButtonsState(panel, disabled) {
        panel.querySelectorAll(this.decisionSelector).forEach((button) => {
            button.disabled = disabled;
        });
    }

    buildErrorState(message) {
        return `
            <div class="alert alert-danger mb-0" role="alert">
                ${this.escapeHtml(message)}
            </div>
        `;
    }

    escapeHtml(value) {
        const element = document.createElement('div');
        element.textContent = value;
        return element.innerHTML;
    }
}

if (typeof window !== 'undefined') {
    const boot = () => new ItemAIRecommendations();
    if (document.readyState === 'loading') {
        window.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
}