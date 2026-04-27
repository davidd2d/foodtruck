import { checkoutCart, setPickupSlot, submitOrder } from '../api/order.js';
import { interpolate } from '../i18n.js';

export function createCheckoutHandler({
    slotSelector,
    checkoutButton,
    payOnSiteButton,
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
        payOnSiteSubmittedMessage: 'Commande envoyée. Paiement au foodtruck lors du retrait.',
        cartContinueMessage: 'Ajoutez des articles à votre panier pour continuer.',
        checkoutErrorMessage: 'Impossible de finaliser la commande.',
        checkoutLabel: checkoutButton?.textContent?.trim() || 'Valider',
        payOnSiteLabel: payOnSiteButton?.textContent?.trim() || 'Payer au foodtruck',
        ...translations,
    };

    const buildPaymentCheckoutUrl = (orderId) => {
        if (paymentCheckoutUrlTemplate) {
            return paymentCheckoutUrlTemplate.replace(/0\/?$/, `${orderId}/`);
        }
        return `/payments/checkout/${orderId}/`;
    };

    return async function handleCheckout(paymentMethod = 'online', triggerButton = checkoutButton) {
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

        const buttons = [checkoutButton, payOnSiteButton].filter(Boolean);
        buttons.forEach((button) => {
            button.disabled = true;
        });
        if (triggerButton) {
            triggerButton.textContent = labels.processingLabel;
        }
        if (checkoutHelp) {
            checkoutHelp.classList.remove('text-danger');
            checkoutHelp.classList.remove('text-success');
            checkoutHelp.classList.remove('d-none');
            checkoutHelp.textContent = labels.finalizingMessage;
        }

        let completedOnSiteCheckout = false;

        try {
            const { order_id } = await checkoutCart(null, paymentMethod);
            await setPickupSlot(order_id, slotId);
            await submitOrder(order_id);

            if (checkoutHelp) {
                checkoutHelp.classList.remove('text-danger');
                checkoutHelp.classList.add('text-success');
                checkoutHelp.textContent = paymentMethod === 'on_site'
                    ? labels.payOnSiteSubmittedMessage
                    : labels.redirectingToPaymentMessage;
            }
            if (paymentMethod === 'on_site') {
                await refreshCart();
                completedOnSiteCheckout = true;
                return;
            }
            window.location.assign(buildPaymentCheckoutUrl(order_id));
        } catch (error) {
            if (checkoutHelp) {
                checkoutHelp.classList.remove('text-success');
                checkoutHelp.classList.add('text-danger');
                checkoutHelp.textContent = error.message || labels.checkoutErrorMessage;
            }
        } finally {
            if (!completedOnSiteCheckout) {
                checkoutButton.disabled = false;
                checkoutButton.textContent = labels.checkoutLabel;
                if (payOnSiteButton) {
                    payOnSiteButton.disabled = false;
                    payOnSiteButton.textContent = labels.payOnSiteLabel;
                }
            }
        }
    };
}
