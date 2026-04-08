import { checkoutCart, setPickupSlot, submitOrder } from '../api/order.js';

export function createCheckoutHandler({
    slotSelector,
    checkoutButton,
    checkoutHelp,
    refreshCart,
    setCheckoutState,
    userAuthenticated,
}) {
    return async function handleCheckout() {
        if (!checkoutButton) {
            return;
        }

        if (!userAuthenticated) {
            if (checkoutHelp) {
                checkoutHelp.classList.remove('d-none');
                checkoutHelp.textContent = 'Please log in before submitting an order.';
            }
            return;
        }

        const slotId = slotSelector?.getSelectedSlotId();
        if (!slotId) {
            setCheckoutState(false, 'Select a pickup slot before checkout.');
            return;
        }

        checkoutButton.disabled = true;
        checkoutButton.textContent = 'Processing...';
        if (checkoutHelp) {
            checkoutHelp.classList.remove('text-danger');
            checkoutHelp.classList.remove('text-success');
            checkoutHelp.classList.remove('d-none');
            checkoutHelp.textContent = 'Finalizing your order…';
        }

        try {
            const { order_id } = await checkoutCart();
            await setPickupSlot(order_id, slotId);
            await submitOrder(order_id);
            await refreshCart();

            if (checkoutHelp) {
                checkoutHelp.classList.remove('text-danger');
                checkoutHelp.classList.add('text-success');
                checkoutHelp.textContent = `Order submitted (#${order_id}).`;
            }
            slotSelector?.reset('Add items to your cart to continue.');
            setCheckoutState(false, 'Add items to your cart to continue.');
        } catch (error) {
            if (checkoutHelp) {
                checkoutHelp.classList.remove('text-success');
                checkoutHelp.classList.add('text-danger');
                checkoutHelp.textContent = error.message || 'Unable to complete checkout.';
            }
        } finally {
            checkoutButton.disabled = false;
            checkoutButton.textContent = 'Checkout';
        }
    };
}
