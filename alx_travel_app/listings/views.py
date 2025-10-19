# listings/views.py

import requests
import uuid
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Booking, Payment, Listing
from .tasks import send_payment_confirmation_email


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_booking(request):
    """
    Create a new booking for a listing
    """
    try:
        listing_id = request.data.get('listing_id')
        check_in = request.data.get('check_in')
        check_out = request.data.get('check_out')
        guests = request.data.get('guests', 1)
        
        # Get the listing
        listing = get_object_or_404(Listing, id=listing_id)
        
        # Calculate total price (simplified - you might want to add date calculation)
        total_price = listing.price_per_night * guests
        
        # Create booking
        booking = Booking.objects.create(
            listing=listing,
            user=request.user,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            total_price=total_price,
            status='pending'
        )
        
        return Response({
            'message': 'Booking created successfully',
            'booking_id': str(booking.booking_id),
            'total_price': str(total_price)
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """
    Initiate payment with Chapa API
    """
    try:
        booking_id = request.data.get('booking_id')
        
        # Get the booking
        booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
        
        # Check if booking already has a completed payment
        if booking.payments.filter(payment_status='completed').exists():
            return Response({
                'error': 'This booking already has a completed payment'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate unique transaction reference
        tx_ref = f"tx-{uuid.uuid4()}"
        
        # Prepare payment data for Chapa
        payment_data = {
            "amount": str(booking.total_price),
            "currency": "ETB",
            "email": request.user.email,
            "first_name": request.user.first_name or request.user.username,
            "last_name": request.user.last_name or "",
            "tx_ref": tx_ref,
            "callback_url": f"{request.build_absolute_uri('/api/payments/verify/')}",
            "return_url": f"{request.build_absolute_uri('/bookings/')}",
            "customization": {
                "title": "Travel Booking Payment",
                "description": f"Payment for booking {booking.booking_id}"
            }
        }
        
        # Make request to Chapa API
        headers = {
            "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{settings.CHAPA_BASE_URL}/transaction/initialize",
            json=payment_data,
            headers=headers,
            timeout=30
        )
        
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('status') == 'success':
            # Create payment record
            payment = Payment.objects.create(
                booking=booking,
                transaction_id=tx_ref,
                amount=booking.total_price,
                currency='ETB',
                payment_status='pending',
                chapa_reference=tx_ref,
                checkout_url=response_data['data']['checkout_url']
            )
            
            return Response({
                'message': 'Payment initiated successfully',
                'payment_id': str(payment.payment_id),
                'checkout_url': response_data['data']['checkout_url'],
                'transaction_reference': tx_ref
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Failed to initiate payment',
                'details': response_data
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Payment initiation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
def verify_payment(request):
    """
    Verify payment status with Chapa API
    """
    try:
        # Get transaction reference from query params or body
        tx_ref = request.GET.get('tx_ref') or request.data.get('tx_ref')
        
        if not tx_ref:
            return Response({
                'error': 'Transaction reference is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Make request to Chapa verify endpoint
        headers = {
            "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"
        }
        
        response = requests.get(
            f"{settings.CHAPA_BASE_URL}/transaction/verify/{tx_ref}",
            headers=headers,
            timeout=30
        )
        
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('status') == 'success':
            payment_info = response_data['data']
            
            # Find the payment record
            payment = Payment.objects.filter(transaction_id=tx_ref).first()
            
            if not payment:
                return Response({
                    'error': 'Payment record not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Update payment status based on Chapa response
            if payment_info['status'] == 'success':
                payment.payment_status = 'completed'
                payment.payment_method = payment_info.get('payment_method', '')
                payment.save()
                
                # Update booking status
                booking = payment.booking
                booking.status = 'confirmed'
                booking.save()
                
                # Send confirmation email (async)
                send_payment_confirmation_email.delay(
                    booking.user.email,
                    str(booking.booking_id),
                    str(payment.amount)
                )
                
                return Response({
                    'message': 'Payment verified and completed successfully',
                    'payment_status': 'completed',
                    'booking_id': str(booking.booking_id),
                    'amount': str(payment.amount)
                }, status=status.HTTP_200_OK)
            else:
                payment.payment_status = 'failed'
                payment.save()
                
                return Response({
                    'message': 'Payment verification failed',
                    'payment_status': 'failed',
                    'details': payment_info
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'error': 'Failed to verify payment',
                'details': response_data
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Payment verification failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_status(request, payment_id):
    """
    Get payment status
    """
    try:
        payment = get_object_or_404(Payment, payment_id=payment_id)
        
        # Check if user owns this payment
        if payment.booking.user != request.user:
            return Response({
                'error': 'Unauthorized'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return Response({
            'payment_id': str(payment.payment_id),
            'booking_id': str(payment.booking.booking_id),
            'amount': str(payment.amount),
            'currency': payment.currency,
            'status': payment.payment_status,
            'transaction_id': payment.transaction_id,
            'created_at': payment.created_at,
            'updated_at': payment.updated_at
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)