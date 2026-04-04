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
            'currency',
            'status',
            'provider',
            'provider_payment_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
