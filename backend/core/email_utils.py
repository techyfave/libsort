"""
Email utility functions for LibSort email notifications.
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_html_email(subject, recipient_email, template_name, context, from_email=None):
    """
    Send an HTML email using Django templates.
    
    Args:
        subject: Email subject line
        recipient_email: Recipient's email address
        template_name: Path to the email template (e.g., 'emails/reminder.html')
        context: Dictionary of context variables for the template
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
    
    Returns:
        Number of messages sent (1 on success, 0 on failure)
    """
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    if not from_email:
        logger.error(f"Cannot send email to {recipient_email}: DEFAULT_FROM_EMAIL not configured")
        return 0
    
    try:
        # Render HTML content
        html_content = render_to_string(template_name, context)
        
        # Create email message
        msg = EmailMultiAlternatives(
            subject=subject,
            body=f"Please view this email in an HTML-compatible email client.\n\n{subject}",
            from_email=from_email,
            to=[recipient_email]
        )
        
        # Attach HTML version
        msg.attach_alternative(html_content, "text/html")
        
        # Send email
        result = msg.send(fail_silently=False)
        logger.info(f"Email sent successfully to {recipient_email}: {subject}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}", exc_info=True)
        return 0


def get_reminder_subject(book_title):
    """Generate a subject line for reminder emails."""
    return f"Library Reminder: Please return '{book_title}'"


def get_checkout_subject(book_title):
    """Generate a subject line for checkout confirmation emails."""
    return f"Book Checkout Confirmation: {book_title}"


def get_overdue_subject(book_title):
    """Generate a subject line for overdue emails."""
    return f"URGENT: Book Overdue - {book_title}"
