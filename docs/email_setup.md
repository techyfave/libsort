# Resend email notifications

LibSort sends HTML reminders, checkout confirmations and overdue notices through the Resend HTTPS API, with Celery handling background delivery and retries.

## Domain and credentials

1. Add your custom sending domain at https://resend.com/domains.
2. Add the exact DNS records Resend supplies at your DNS provider; wait for Verified status.
3. Create a sending API key scoped to the domain at https://resend.com/api-keys.
4. Choose a sender on that domain, such as `LibSort Library <reminders@yourdomain.com>`.

Set these in the repository-root `.env` locally and on both the deployed Django service and Celery worker:

```dotenv
RESEND_API_KEY=re_your_private_api_key
DEFAULT_FROM_EMAIL=LibSort Library <reminders@yourdomain.com>
CELERY_BROKER_URL=redis://localhost:6379/0
```

Replace the example sender and broker URL. `CELERY_RESULT_BACKEND` defaults to the broker URL. The app loads the root `.env`, not `backend/.env`. Old `GMAIL_USER` and `GMAIL_APP_PASSWORD` values are no longer used and can be removed. Keep the key out of frontend variables and version control.

## Run services

Install `requirements.lock.txt`, run migrations, and start Redis. From the repository root, run Django and Celery in separate terminals:

```powershell
.venv/Scripts/python backend/manage.py migrate
.venv/Scripts/python backend/manage.py runserver 127.0.0.1:8000
```

```powershell
.venv/Scripts/celery --workdir backend -A config worker --loglevel=info --pool=solo
```

On Linux, omit `--pool=solo`. Both processes need the same database and Redis broker. A `memory://` broker cannot pass tasks between separate processes. Restart both services after changing environment settings. The web service alone does not process queued emails.

## Verify

Run `.venv/Scripts/python backend/manage.py test core` for tests that do not send real mail.

For live verification, use a loan with a student contact address you control, click **Remind**, then check worker logs, Resend delivery events and the inbox. A queued response only confirms task submission. Provider acceptance does not guarantee inbox delivery.

## Troubleshooting

- Missing configuration: set both `RESEND_API_KEY` and `DEFAULT_FROM_EMAIL` on the worker.
- Rejected message: check API key permissions, sender domain verification and account limits.
- Tasks remain queued: check Redis connectivity and matching API/worker broker configuration.
- No email received: verify the student's contact and check spam folders and Resend bounce events.

Transport: `backend/core/email_backend.py`. Configuration: `backend/config/settings.py`. HTTPS calls time out after 30 seconds; no SMTP credentials or additional Resend SDK are required.

References: [Resend domain verification](https://resend.com/docs/dashboard/domains/introduction), [send-email API](https://resend.com/docs/api-reference/emails/send-email).
