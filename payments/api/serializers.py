from rest_framework import serializers
from payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""

    class Meta:
        model = Payment
        fields = [
            'id',
            'order',
            'amount',
            'status',
            'provider',
            'stripe_session_id',
            'stripe_payment_intent',
            'paid_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
