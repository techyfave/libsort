"""
Celery tasks for LibSort email notifications.
"""
import logging
from celery import shared_task
from django.utils import timezone
from .models import BorrowRecord
from .email_utils import send_html_email, get_reminder_subject, get_checkout_subject, get_overdue_subject

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_reminder_email(self, loan_id):
    """Send a reminder email for an overdue or due-soon book."""
    try:
        loan = BorrowRecord.objects.select_related('student', 'book').get(id=loan_id)
        
        if not loan.student.contact:
            logger.warning(f"Cannot send reminder: Student {loan.student.id} has no email")
            return "Student has no email address"
        
        context = {
            'student_name': loan.student.name,
            'book_title': loan.book.title,
            'book_author': loan.book.author,
            'book_accession': loan.book.accession,
            'due_date': loan.due_date,
            'borrowed_date': loan.borrowed_date,
            'days_overdue': (timezone.localdate() - loan.due_date).days if timezone.localdate() > loan.due_date else 0,
            'is_overdue': timezone.localdate() > loan.due_date,
        }
        
        subject = get_reminder_subject(loan.book.title)
        result = send_html_email(
            subject=subject,
            recipient_email=loan.student.contact,
            template_name='emails/reminder.html',
            context=context
        )
        
        if result:
            return f"Reminder email sent to {loan.student.contact}"
        raise Exception("Email send returned 0")
            
    except BorrowRecord.DoesNotExist:
        logger.error(f"BorrowRecord with id {loan_id} not found")
        return "Loan record not found"
    except Exception as exc:
        logger.error(f"Error sending reminder email for loan {loan_id}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_checkout_email(self, loan_id):
    """Send a checkout confirmation email."""
    try:
        loan = BorrowRecord.objects.select_related('student', 'book').get(id=loan_id)
        
        if not loan.student.contact:
            logger.warning(f"Cannot send checkout email: Student {loan.student.id} has no email")
            return "Student has no email address"
        
        context = {
            'student_name': loan.student.name,
            'book_title': loan.book.title,
            'book_author': loan.book.author,
            'book_accession': loan.book.accession,
            'borrowed_date': loan.borrowed_date,
            'due_date': loan.due_date,
            'days_borrowed': (loan.due_date - loan.borrowed_date).days,
        }
        
        subject = get_checkout_subject(loan.book.title)
        result = send_html_email(
            subject=subject,
            recipient_email=loan.student.contact,
            template_name='emails/checkout.html',
            context=context
        )
        
        if result:
            return f"Checkout email sent to {loan.student.contact}"
        raise Exception("Email send returned 0")
            
    except BorrowRecord.DoesNotExist:
        logger.error(f"BorrowRecord with id {loan_id} not found")
        return "Loan record not found"
    except Exception as exc:
        logger.error(f"Error sending checkout email for loan {loan_id}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_overdue_email(self, loan_id):
    """Send an overdue notice email."""
    try:
        loan = BorrowRecord.objects.select_related('student', 'book').get(id=loan_id)
        
        if not loan.student.contact:
            logger.warning(f"Cannot send overdue email: Student {loan.student.id} has no email")
            return "Student has no email address"
        
        if loan.returned_at:
            logger.info(f"Loan {loan_id} already returned, skipping overdue email")
            return "Loan already returned"
        
        days_overdue = (timezone.localdate() - loan.due_date).days
        if days_overdue <= 0:
            logger.info(f"Loan {loan_id} not yet overdue, skipping")
            return "Loan not yet overdue"
        
        context = {
            'student_name': loan.student.name,
            'book_title': loan.book.title,
            'book_author': loan.book.author,
            'book_accession': loan.book.accession,
            'due_date': loan.due_date,
            'days_overdue': days_overdue,
        }
        
        subject = get_overdue_subject(loan.book.title)
        result = send_html_email(
            subject=subject,
            recipient_email=loan.student.contact,
            template_name='emails/overdue.html',
            context=context
        )
        
        if result:
            return f"Overdue email sent to {loan.student.contact}"
        raise Exception("Email send returned 0")
            
    except BorrowRecord.DoesNotExist:
        logger.error(f"BorrowRecord with id {loan_id} not found")
        return "Loan record not found"
    except Exception as exc:
        logger.error(f"Error sending overdue email for loan {loan_id}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def send_bulk_reminders(self, loan_ids):
    """Send reminder emails for multiple loans."""
    results = {}
    for loan_id in loan_ids:
        try:
            result = send_reminder_email(loan_id)
            results[loan_id] = {'status': 'sent', 'message': result}
        except Exception as e:
            logger.error(f"Failed to send reminder for loan {loan_id}: {str(e)}")
            results[loan_id] = {'status': 'failed', 'message': str(e)}
    
    return results
