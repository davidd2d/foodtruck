from django.core.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from orders.models import Order
from payments.models import Payment
from .serializers import PaymentSerializer


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Payment model.

    Provides payment initialization, pay, and fail actions.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(
            order__customer=self.request.user
        ).select_related('order')

    @action(detail=False, methods=['post'], url_path=r'(?P<order_id>[^/.]+)/initialize')
    def initialize(self, request, order_id=None):
        order = Order.objects.filter(
            id=order_id,
            customer=request.user
        ).first()

        if not order:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        if hasattr(order, 'payment'):
            return Response({'error': 'Payment already exists for this order'}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment(order=order, amount=order.total_price)

        try:
            payment.initialize()
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(payment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        payment = self.get_object()

        try:
            payment.mark_as_paid()
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def fail(self, request, pk=None):
        payment = self.get_object()
        payment.mark_as_failed()
        serializer = self.get_serializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)
