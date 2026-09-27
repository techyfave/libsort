import io
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Book, BorrowRecord, Floor, Reminder, Section, Shelf, Student


@override_settings(
    EMAIL_DELIVERY_MODE='direct',
    EMAIL_BACKEND='core.email_backend.ResendEmailBackend',
    RESEND_API_KEY='re_test_only',
    DEFAULT_FROM_EMAIL='Library <reminders@example.com>',
)
class ReminderDeliveryTests(TestCase):
    def setUp(self):
        floor = Floor.objects.create(name='Ground')
        section = Section.objects.create(name='Books', floor=floor)
        shelf = Shelf.objects.create(code='G01', section=section)
        book = Book.objects.create(accession='B01', title='Test Book', shelf=shelf)
        student = Student.objects.create(student_id='S01', name='Reader', contact='reader@example.net')
        self.loan = BorrowRecord.objects.create(
            book=book, student=student, borrowed_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
        )
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create(username='staff', is_staff=True))
        self.url = f'/api/loans/{self.loan.id}/remind/'

    @patch('core.views.send_reminder_email.delay')
    @patch('core.email_backend.urlopen')
    def test_direct_delivery_reaches_resend_without_queue(self, open_url, enqueue):
        open_url.return_value.__enter__.return_value = io.BytesIO(b'{"id":"email-123"}')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['delivery'], 'email_sent')
        self.assertEqual(Reminder.objects.get().delivery, 'email_sent')
        enqueue.assert_not_called()
        open_url.assert_called_once()

    @patch('core.views.send_reminder_email.delay')
    @patch('core.email_backend.urlopen', side_effect=TimeoutError('timeout'))
    def test_direct_failure_returns_json_without_recording_success(self, open_url, enqueue):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['delivery'], 'email_failed')
        self.assertFalse(Reminder.objects.exists())
        enqueue.assert_not_called()

    @override_settings(EMAIL_DELIVERY_MODE='celery')
    @patch('core.views.send_reminder_email.delay')
    def test_explicit_celery_mode_queues(self, enqueue):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Reminder.objects.get().delivery, 'email_queued')
        enqueue.assert_called_once_with(self.loan.id)

    @override_settings(EMAIL_DELIVERY_MODE='celery')
    @patch('core.views.send_reminder_email.delay', side_effect=RuntimeError('Redis unavailable'))
    def test_queue_failure_returns_json_without_recording_success(self, enqueue):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Reminder.objects.exists())

    @patch('core.views.send_reminder_email')
    def test_missing_contact_only_logs(self, send):
        student = self.loan.student
        student.contact = ''
        student.save()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Reminder.objects.get().delivery, 'demo_logged')
        send.assert_not_called()
