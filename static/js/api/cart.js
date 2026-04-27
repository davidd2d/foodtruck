import apiClient from './client.js';

export async function fetchCart() {
    return apiClient.get('/cart/');
}

export async function addCartItem(payload) {
    return apiClient.post('/cart/add/', payload);
}

export async function removeCartItem(lineKey) {
    return apiClient.post('/cart/remove/', { line_key: lineKey });
}

export async function updateCartItemQuantity(lineKey, quantity) {
    return apiClient.post('/cart/update/', { line_key: lineKey, quantity });
}
