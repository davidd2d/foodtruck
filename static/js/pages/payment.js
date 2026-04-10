import PaymentAPI from '../api/payment.js';

/**
 * Initializes the payment page logic.
 *
 * @param {Object} config
 * @param {number} config.orderId
 * @param {string} config.orderTotal
 * @param {string} config.successUrl
 * @param {string} config.paymentCurrency
 */
export default function initPaymentPage(config = {}) {
    const payButton = document.getElementById('payment-button');
    const statusEl = document.getElementById('payment-status');

    if (!payButton || !statusEl) {
        return;
    }

    const { orderId, successUrl } = config;
    const translations = {
        genericErrorMessage: 'Something went wrong. Please try again.',
        missingOrderIdMessage: 'Order ID is missing.',
        creatingPaymentMessage: 'Creating payment...',
        authorizingPaymentMessage: 'Authorizing payment...',
        capturingPaymentMessage: 'Capturing payment...',
        paymentCapturedMessage: 'Payment captured! Redirecting...',
        ...config.translations,
    };

    const updateStatus = (message, isError = false) => {
        statusEl.textContent = message;
        statusEl.classList.toggle('text-danger', isError);
        statusEl.classList.toggle('text-muted', !isError);
    };

    const handleError = (error) => {
        const message = error?.message || translations.genericErrorMessage;
        updateStatus(message, true);
    };

    payButton.addEventListener('click', async () => {
        if (!orderId) {
            handleError(new Error(translations.missingOrderIdMessage));
            return;
        }

        payButton.disabled = true;

        try {
            updateStatus(translations.creatingPaymentMessage);
            const payment = await PaymentAPI.create(orderId);

            updateStatus(translations.authorizingPaymentMessage);
            await PaymentAPI.authorize(payment.id);

            updateStatus(translations.capturingPaymentMessage);
            await PaymentAPI.capture(payment.id);

            updateStatus(translations.paymentCapturedMessage, false);
            setTimeout(() => {
                window.location.href = successUrl;
            }, 1200);
        } catch (error) {
            handleError(error);
        } finally {
            payButton.disabled = false;
        }
    });
}
