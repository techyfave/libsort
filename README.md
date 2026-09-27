# LibSort

A library catalogue and staff workspace for finding books, recording loans, and verifying shelf placement. Each **Book is one physical lending unit** with a unique accession number and stable QR identity. Several Book records can share a title or ISBN; there is no BookCopy model.

## Deploy for a client demo

Use the [Render + Vercel deployment guide](docs/deployment.md). The repository includes scripts for a manually configured Render Web Service, Gunicorn startup and WhiteNoise, Vercel API proxy configuration, secure production settings, database-backed login protection, and GitHub deployment checks. The local demo password is not a deployment credential.

## Run locally

Requires Python 3.11+ and Node.js 22. Django serves the API on port 8000; Vite serves the interface on port 5173 and proxies API/admin requests to Django. Email reminders use Resend directly by default; Celery with Redis is optional.

### Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
.venv\Scripts\python backend/manage.py migrate
.venv\Scripts\python backend/manage.py seed_demo_data
.venv\Scripts\python backend/manage.py createsuperuser
```

### Environment variables for email

Create or update the `.env` file in the project root:

```
RESEND_API_KEY=re_your_api_key
DEFAULT_FROM_EMAIL=LibSort Library <reminders@yourdomain.com>
EMAIL_DELIVERY_MODE=direct
```

Verify your sending domain in Resend and create a sending API key. See [email setup](docs/email_setup.md) for DNS verification and deployment instructions. Keep the key on the backend and worker only.

### Run the services

**Terminal 1 - Django API:**
```powershell
.venv\Scripts\python backend/manage.py runserver 127.0.0.1:8000
```

**Optional Celery worker (requires EMAIL_DELIVERY_MODE=celery and CELERY_BROKER_URL):**
```powershell
.venv\Scripts\celery --workdir backend -A config worker --loglevel=info --pool=solo
```

**Terminal 3 - Frontend:**
```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. Search and the shelf map are public. Use the superuser account for Staff sign in. Manage books, students, floors, sections and shelves at http://127.0.0.1:8000/admin/. Email reminders are sent through Resend when staff click "Remind" buttons in the Circulation tab.

**Note:** Redis is only needed for Celery mode. Start Redis before Django and Celery in that mode. The API and worker must use the same broker; an in-memory broker cannot pass tasks between these processes.

If Python's `ensurepip` is unavailable, create the virtual environment and install with `uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt`. `requirements.txt` declares supported ranges; `requirements.lock.txt` records the tested installation.

## Working flow

1. Search by title, author, accession, ISBN or category. Filter by availability or browse shelves.
2. Staff select an available book and check it out to a student with a due date.
3. Record its return under Circulation. It becomes `awaiting_shelving`.
4. Under Scan & verify, enter its accession and shelf code, or scan both QR labels.
5. A mismatch is logged and keeps the book awaiting shelving. A correct match makes it available.

QR payloads are `BOOK:<uuid>` and `SHELF:<uuid>`. They identify records rather than locations, so changing a shelf code does not invalidate labels. Open printable SVG QR labels from book details or staff shelf-map cards. Manual inputs support barcode keyboard scanners. Camera scanning requires browser permission and a secure context (localhost or HTTPS).

Loans have a database constraint allowing only one active loan per Book. Checkout and return use transactions; a row lock protects book changes on PostgreSQL. SQLite is for a single-user development/demo environment; concurrent write load should be evaluated on PostgreSQL before deployment. Admin makes loan and audit records read-only to keep mutations in the lending workflow. Deleting referenced locations is protected.

Overdue means an unreturned loan with a due date before today's date in Africa/Lagos. It is computed when read and cannot go stale waiting for a scheduler. Due-today loans are not overdue. Reminder buttons create an audit record and send an email through Resend, or queue it when Celery mode is enabled.

## Data and scope

`seed_demo_data` creates 3 floors, 3 sections, 36 shelves, 108 book units, five students and illustrative loan/return states. Catalogue titles and authors are synthetic demonstration metadata, not claims about published editions; ISBNs are intentionally blank. Repeated titles demonstrate multiple independently lendable Books. Seed reruns preserve existing records rather than resetting them. The supplied nursing PDFs remain reference material and are not automatically imported.

The shelf map is a hierarchical floor/section/shelf browser, not a measured building plan. No RFID, sensors, external classification lookup or floorplan navigation is included. Email delivery to students is implemented via Resend HTTPS API, with optional Celery background tasks. Public catalogue results are capped at 200 for this first demo; pagination is needed before growing beyond that. Google Fonts are optional; system fonts remain usable offline.

## Verify

```powershell
.venv\Scripts\python backend/manage.py check
.venv\Scripts\python backend/manage.py test core
cd frontend
npm run build
```

See [docs/evaluation.md](docs/evaluation.md) for functional, usability and performance evaluation. Automated tests cover the lifecycle, access control, CSRF, stable QR identity, invalid requests, date boundaries and repeatable seeding.

## Configuration

Default local database: `backend/db.sqlite3` (ignored by Git). Production requires PostgreSQL via `DATABASE_URL`, or the `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` variables. Set `DJANGO_DEBUG=0`, a random `DJANGO_SECRET_KEY` of at least 50 characters, and the exact frontend origin in `DJANGO_CSRF_TRUSTED_ORIGINS`. Render's hostname is detected automatically; additional domains go in `DJANGO_ALLOWED_HOSTS`. Production serving and security are configured in the deployment files; the local run commands above remain development servers.

Design references: [Django database constraints](https://docs.djangoproject.com/en/5.2/ref/models/constraints/) and [Vite documentation](https://vite.dev/guide/).
