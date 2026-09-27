"""Django email transport for LibSort notifications through Resend HTTPS."""
import json
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            if not message.recipients():
                continue
            try:
                if not settings.RESEND_API_KEY or not message.from_email:
                    raise ImproperlyConfigured(
                        'Set RESEND_API_KEY and DEFAULT_FROM_EMAIL to send email.'
                    )
                if message.attachments:
                    raise ValueError('Attachments are not supported by this notification backend.')
                payload = {
                    'from': message.from_email,
                    'subject': message.subject,
                    'html' if message.content_subtype == 'html' else 'text': message.body,
                }
                for field in ('to', 'cc', 'bcc', 'reply_to'):
                    value = getattr(message, field)
                    if value:
                        payload[field] = list(value)
                for content, mimetype in getattr(message, 'alternatives', []):
                    if mimetype != 'text/html':
                        raise ValueError('Only HTML alternatives are supported.')
                    payload['html'] = content
                if message.extra_headers:
                    payload['headers'] = message.extra_headers
                request = Request(
                    'https://api.resend.com/emails',
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        'Authorization': f'Bearer {settings.RESEND_API_KEY}',
                        'Content-Type': 'application/json',
                        'User-Agent': 'LibSort/1.0',
                    },
                    method='POST',
                )
                with urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
                    result = json.load(response)
                if not isinstance(result, dict) or not result.get('id'):
                    raise ValueError('Resend did not return an email ID.')
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
