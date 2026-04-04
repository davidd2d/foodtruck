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

    const updateStatus = (message, isError = false) => {
        statusEl.textContent = message;
        statusEl.classList.toggle('text-danger', isError);
        statusEl.classList.toggle('text-muted', !isError);
    };

    const handleError = (error) => {
        const message = error?.message || 'Something went wrong. Please try again.';
        updateStatus(message, true);
    };

    payButton.addEventListener('click', async () => {
        if (!orderId) {
            handleError(new Error('Order ID is missing.'));
            return;
        }

        payButton.disabled = true;

        try {
            updateStatus('Creating payment...');
            const payment = await PaymentAPI.create(orderId);

            updateStatus('Authorizing payment...');
            await PaymentAPI.authorize(payment.id);

            updateStatus('Capturing payment...');
            await PaymentAPI.capture(payment.id);

            updateStatus('Payment captured! Redirecting...', false);
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
