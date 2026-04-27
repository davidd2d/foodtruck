import apiClient from './client.js';

/**
 * Create an order from the current session cart.
 * The optional pickupSlotId can be provided for backwards compatibility.
 */
export async function checkoutCart(pickupSlotId = null, paymentMethod = 'online') {
    const payload = {};
    if (pickupSlotId) {
        payload.pickup_slot = pickupSlotId;
    }
    payload.payment_method = paymentMethod;
    return apiClient.post('/cart/checkout/', payload);
}

/**
 * Assign a pickup slot to a draft order.
 */
export async function setPickupSlot(orderId, pickupSlot) {
    return apiClient.post('/orders/set-slot/', {
        order_id: orderId,
        pickup_slot: pickupSlot,
    });
}

/**
 * Submit a draft order once a pickup slot is assigned.
 */
export async function submitOrder(orderId) {
    return apiClient.post('/orders/submit/', { order_id: orderId });
}
