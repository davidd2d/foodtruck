from django.core.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from payments.models import Payment
from payments.services.payment_service import PaymentService
from .serializers import PaymentSerializer


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to payments owned by the current user."""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(
            order__user=self.request.user
        ).select_related('order')


class PaymentCreateAPIView(APIView):
    """Create a simulated payment in the pending state."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')

        if not order_id:
            return Response({'detail': 'order_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(
            id=order_id,
            user=request.user
        ).select_related('payment').first()

        if not order:
            return Response({'detail': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = PaymentService.create_payment(order)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PaymentAuthorizeAPIView(APIView):
    """Transition a pending payment to authorized."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get('payment_id')

        if not payment_id:
            return Response({'detail': 'payment_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.filter(
            pk=payment_id,
            order__user=request.user
        ).select_related('order').first()

        if not payment:
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = PaymentService.authorize_payment(payment)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PaymentCaptureAPIView(APIView):
    """Capture funds and mark the order as paid."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get('payment_id')

        if not payment_id:
            return Response({'detail': 'payment_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.filter(
            pk=payment_id,
            order__user=request.user
        ).select_related('order').first()

        if not payment:
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = PaymentService.capture_payment(payment)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)
