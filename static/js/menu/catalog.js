function initMenuCatalogAutosave() {
    const root = document.getElementById('menu-catalog-app');
    if (!root) {
        return;
    }

    const labels = {
        saving: root.dataset.savingLabel || 'Enregistrement...',
        saved: root.dataset.savedLabel || 'Enregistré',
        error: root.dataset.errorLabel || 'Erreur',
    };
    const csrfToken = root.dataset.csrfToken || window.CSRF_TOKEN || '';

    const rows = root.querySelectorAll('.js-menu-autosave-row');
    rows.forEach((row) => {
        const fields = row.querySelectorAll('input, select, textarea');
        const statusNode = row.querySelector('.menu-autosave-status');
        let resetTimer = null;
        let inflightController = null;

        const setStatus = (text, className = 'text-muted') => {
            if (!statusNode) {
                return;
            }
            statusNode.textContent = text;
            statusNode.className = `small menu-autosave-status ${className}`;
        };

        const clearStatusLater = () => {
            window.clearTimeout(resetTimer);
            resetTimer = window.setTimeout(() => {
                setStatus('', 'text-muted');
            }, 1800);
        };

        const submitForm = async () => {
            if (inflightController) {
                inflightController.abort();
            }
            inflightController = new AbortController();

            fields.forEach((field) => {
                field.disabled = true;
            });
            setStatus(labels.saving, 'text-warning');

            const body = new FormData();
            body.append('csrfmiddlewaretoken', csrfToken);
            fields.forEach((field) => {
                if (!field.name || field.type === 'hidden') {
                    return;
                }
                if (field.type === 'checkbox') {
                    if (field.checked) {
                        body.append(field.name, field.value || 'on');
                    }
                    return;
                }
                body.append(field.name, field.value);
            });

            try {
                const response = await fetch(row.dataset.updateUrl, {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body,
                    credentials: 'same-origin',
                    signal: inflightController.signal,
                });

                const payload = await response.json();
                if (!response.ok || !payload.success) {
                    throw new Error(extractError(payload));
                }

                setStatus(labels.saved, 'text-success');
                clearStatusLater();
            } catch (error) {
                if (error.name === 'AbortError') {
                    return;
                }
                setStatus(error.message || labels.error, 'text-danger');
            } finally {
                fields.forEach((field) => {
                    field.disabled = false;
                });
                inflightController = null;
            }
        };

        fields.forEach((field) => {
            if (field.type === 'hidden') {
                return;
            }
            field.addEventListener('change', () => {
                submitForm();
            });
        });
    });
}

function extractError(payload) {
    if (!payload || !payload.errors) {
        return 'Error';
    }

    const messages = [];
    Object.values(payload.errors).forEach((errors) => {
        errors.forEach((error) => messages.push(error));
    });
    return messages.join(' ');
}

initMenuCatalogAutosave();