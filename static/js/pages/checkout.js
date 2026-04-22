import { checkoutCart, setPickupSlot, submitOrder } from '../api/order.js';
import { interpolate } from '../i18n.js';

export function createCheckoutHandler({
    slotSelector,
    checkoutButton,
    checkoutHelp,
    refreshCart,
    setCheckoutState,
    userAuthenticated,
    paymentCheckoutUrlTemplate,
    translations = {},
}) {
    const labels = {
        loginRequiredMessage: 'Veuillez vous connecter avant de valider une commande.',
        selectSlotMessage: 'Sélectionnez un créneau de retrait avant de valider.',
        processingLabel: 'Traitement...',
        finalizingMessage: 'Finalisation de votre commande...',
        orderSubmittedMessage: 'Commande envoyée (#{orderId}).',
        redirectingToPaymentMessage: 'Commande envoyée. Redirection vers le paiement...',
        cartContinueMessage: 'Ajoutez des articles à votre panier pour continuer.',
        checkoutErrorMessage: 'Impossible de finaliser la commande.',
        checkoutLabel: checkoutButton?.textContent?.trim() || 'Valider',
        ...translations,
    };

    const buildPaymentCheckoutUrl = (orderId) => {
        if (paymentCheckoutUrlTemplate) {
            return paymentCheckoutUrlTemplate.replace(/0\/?$/, `${orderId}/`);
        }
        return `/payments/checkout/${orderId}/`;
    };

    return async function handleCheckout() {
        if (!checkoutButton) {
            return;
        }

        if (!userAuthenticated) {
            if (checkoutHelp) {
                checkoutHelp.classList.remove('d-none');
                checkoutHelp.textContent = labels.loginRequiredMessage;
            }
            return;
        }

        const slotId = slotSelector?.getSelectedSlotId();
        if (!slotId) {
            setCheckoutState(false, labels.selectSlotMessage);
            return;
        }

        checkoutButton.disabled = true;
        checkoutButton.textContent = labels.processingLabel;
        if (checkoutHelp) {
            checkoutHelp.classList.remove('text-danger');
            checkoutHelp.classList.remove('text-success');
            checkoutHelp.classList.remove('d-none');
            checkoutHelp.textContent = labels.finalizingMessage;
        }

        try {
            const { order_id } = await checkoutCart();
            await setPickupSlot(order_id, slotId);
            await submitOrder(order_id);

            if (checkoutHelp) {
                checkoutHelp.classList.remove('text-danger');
                checkoutHelp.classList.add('text-success');
                checkoutHelp.textContent = labels.redirectingToPaymentMessage;
            }
            window.location.assign(buildPaymentCheckoutUrl(order_id));
        } catch (error) {
            if (checkoutHelp) {
                checkoutHelp.classList.remove('text-success');
                checkoutHelp.classList.add('text-danger');
                checkoutHelp.textContent = error.message || labels.checkoutErrorMessage;
            }
        } finally {
            checkoutButton.disabled = false;
            checkoutButton.textContent = labels.checkoutLabel;
        }
    };
}
