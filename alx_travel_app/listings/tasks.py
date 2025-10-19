# listings/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_payment_confirmation_email(user_email, booking_id, amount):
    """
    Send payment confirmation email to user
    """
    subject = 'Payment Confirmation - Your Booking is Confirmed!'
    message = f"""
    Dear Customer,
    
    Thank you for your payment!
    
    Your booking (ID: {booking_id}) has been confirmed.
    Amount Paid: ETB {amount}
    
    We look forward to hosting you!
    
    Best regards,
    ALX Travel App Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user_email],
            fail_silently=False,
        )
        return f"Email sent successfully to {user_email}"
    except Exception as e:
        return f"Failed to send email: {str(e)}"