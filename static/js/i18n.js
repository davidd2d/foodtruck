export function getDatasetTranslations(element, defaults = {}) {
    const translations = { ...defaults };

    if (!element) {
        return translations;
    }

    Object.keys(defaults).forEach((key) => {
        const value = element.dataset[key];
        if (typeof value === 'string' && value !== '') {
            translations[key] = value;
        }
    });

    return translations;
}

export function interpolate(message, values = {}) {
    return String(message).replace(/\{(\w+)\}/g, (match, key) => {
        return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : match;
    });
}