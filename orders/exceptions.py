from django.core.exceptions import ValidationError


class OrderTransitionError(ValidationError):
    """Raised when an order status transition violates the domain rules."""
