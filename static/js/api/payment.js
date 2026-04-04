import apiClient from './client.js';

/**
 * Client wrapper for payment-related API endpoints.
 *
 * These endpoints power the simulated Stripe flow without invoking external
 * services. They rely on the server-side PaymentService for validation.
 */
const PaymentAPI = {
    create(orderId) {
        return apiClient.post('/payments/create/', { order_id: orderId });
    },

    authorize(paymentId) {
        return apiClient.post('/payments/authorize/', { payment_id: paymentId });
    },

    capture(paymentId) {
        return apiClient.post('/payments/capture/', { payment_id: paymentId });
    },

};

export default PaymentAPI;
