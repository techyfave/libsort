import io
import json
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from .email_backend import ResendEmailBackend
from .email_utils import send_html_email


@override_settings(RESEND_API_KEY='re_test_only', EMAIL_TIMEOUT=30)
class ResendEmailBackendTests(SimpleTestCase):
    @override_settings(
        EMAIL_BACKEND='core.email_backend.ResendEmailBackend',
        DEFAULT_FROM_EMAIL='Library <reminders@example.com>',
    )
    @patch('core.email_backend.urlopen')
    def test_template_utility_reaches_resend(self, open_url):
        open_url.return_value.__enter__.return_value = io.BytesIO(b'{"id":"email-123"}')
        self.assertEqual(send_html_email(
            'Return your book', 'student@example.net', 'emails/reminder.html',
            {'student_name': 'Test Student', 'book_title': 'Test Book'},
        ), 1)
        payload = json.loads(open_url.call_args.args[0].data)
        self.assertIn('Test Book', payload['html'])
        self.assertEqual(payload['from'], 'Library <reminders@example.com>')

    def message(self):
        message = EmailMultiAlternatives(
            'Library reminder', 'Return your book',
            'Library <reminders@example.com>', ['student@example.net'],
        )
        message.attach_alternative('<p>Return your book</p>', 'text/html')
        return message

    @patch('core.email_backend.urlopen')
    def test_sends_html_and_text_with_verified_sender(self, open_url):
        open_url.return_value.__enter__.return_value = io.BytesIO(b'{"id":"email-123"}')
        self.assertEqual(ResendEmailBackend().send_messages([self.message()]), 1)
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.resend.com/emails')
        self.assertEqual(request.get_header('Authorization'), 'Bearer re_test_only')
        self.assertEqual(open_url.call_args.kwargs['timeout'], 30)
        self.assertEqual(json.loads(request.data), {
            'from': 'Library <reminders@example.com>',
            'to': ['student@example.net'], 'subject': 'Library reminder',
            'text': 'Return your book', 'html': '<p>Return your book</p>',
        })

    @override_settings(RESEND_API_KEY='')
    @patch('core.email_backend.urlopen')
    def test_missing_key_does_not_send(self, open_url):
        with self.assertRaises(ImproperlyConfigured):
            ResendEmailBackend().send_messages([self.message()])
        open_url.assert_not_called()

    @patch('core.email_backend.urlopen')
    def test_rejections_and_timeouts_are_not_successes(self, open_url):
        for error in (HTTPError('https://api.resend.com/emails', 403, 'Forbidden', {}, None),
                      URLError('unreachable'), TimeoutError('timeout')):
            with self.subTest(error=type(error).__name__):
                open_url.side_effect = error
                with self.assertRaises(type(error)):
                    ResendEmailBackend().send_messages([self.message()])
                self.assertEqual(ResendEmailBackend(fail_silently=True).send_messages([self.message()]), 0)

    @patch('core.email_backend.urlopen')
    def test_response_without_id_is_not_success(self, open_url):
        open_url.return_value.__enter__.return_value = io.BytesIO(b'{}')
        with self.assertRaisesMessage(ValueError, 'email ID'):
            ResendEmailBackend().send_messages([self.message()])

    @patch('core.email_backend.urlopen')
    def test_no_recipients_does_not_send(self, open_url):
        message = self.message()
        message.to = []
        self.assertEqual(ResendEmailBackend().send_messages([message]), 0)
        open_url.assert_not_called()
