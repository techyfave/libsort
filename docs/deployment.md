# Render + Vercel demo deployment

The phone opens the Vercel HTTPS URL. Vercel forwards `/api/*` to Render. Session cookies stay on the Vercel site (host-only, HttpOnly, Secure, SameSite=Lax), avoiding third-party-cookie restrictions on phones. Django trusts only the frontend origins you explicitly configure. Do not change frontend requests to call Render directly.

## 1. Push the repository

Commit application code, migrations, lockfiles, scripts and deployment docs to GitHub. Do not commit `.env`, SQLite, local credentials, generated static files or node_modules. Original PDF reference material is not required for deployment.

## 2. Render backend

Use the existing manually configured **Web Service** connected to this GitHub repository. Configure it with:

- Runtime: `Python`
- Build Command: `bash scripts/render-build.sh`
- Start Command: `bash scripts/render-start.sh`
- Health Check Path: `/api/health/`
- Instance Type: `Free`

Connect the service to the existing free PostgreSQL database and set its internal connection URL as `DATABASE_URL`.

Set these Web Service environment variables:

- `DJANGO_DEBUG`: `0`.
- `DJANGO_SECRET_KEY`: a long random value generated and stored in Render.
- `DATABASE_URL`: the existing Render PostgreSQL internal connection URL.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: `https://libsort.vercel.app`. Comma-separate any additional known origins; never trust every Vercel tenant.
- `SEED_DEMO_DATA`: `1` for the initial demo-data deployment, then `0` if later deployments should leave edited records alone.
- `DJANGO_SUPERUSER_USERNAME`: a new admin username, e.g. `libsort_admin`.
- `DJANGO_SUPERUSER_EMAIL`: your email address.
- `DJANGO_SUPERUSER_PASSWORD`: a new strong password entered privately in Render.

Keep the Start Command as `bash scripts/render-start.sh`. It runs migrations and `python backend/manage.py bootstrap_deployment` before starting Gunicorn, so no paid shell or pre-deploy command is needed. The bootstrap creates an active superuser. If the configured username already exists, including the old demo staff username, supplying `DJANGO_SUPERUSER_PASSWORD` promotes or recovers that account, applies the supplied credentials, and clears its failed-login lockout. Remove the old `DEMO_STAFF_USERNAME` and `DEMO_STAFF_PASSWORD` environment variables; they are no longer used.

After a successful deploy, sign in at `https://libsort.onrender.com/admin/` using the new admin. You can also use that account in the frontend Staff sign in. In admin, use Users to create staff, enable their Staff status, and grant only the model permissions they need. Existing staff accounts remain intact and can be managed there.

Startup trims accidental surrounding spaces and matching shell quotes from the three admin values, verifies the saved password hash, and logs the normalized username and password length without printing the password. Use that line to confirm what must be typed at sign-in.

Remove `DJANGO_SUPERUSER_PASSWORD` after confirming login (or remove all three bootstrap variables). Set `SEED_DEMO_DATA=0` after the initial deployment if you want to manage records without seeding. Render generates `DJANGO_SECRET_KEY` and supplies `DATABASE_URL`; its hostname is automatically allowed. Build collects admin static files.

Confirm `https://libsort.onrender.com/api/health/` returns `{"status":"ok"}`.

## 3. Vercel frontend

Import the same GitHub repository. Set **Root Directory** to `frontend`, Framework to **Vite**, and Node.js to **22.x**. Keep the repository's build/output configuration.

The repository's `frontend/vercel.ts` forwards `/api/*` to `https://libsort.onrender.com`. No Vercel `BACKEND_URL` variable is required for this deployment. If the Render hostname changes, update `backendOrigin` in that file and redeploy.

Keep the stable Vercel production origin in Render's `DJANGO_CSRF_TRUSTED_ORIGINS`. Save/redeploy Render. Use the stable production URL for the client; a new preview hostname needs its own trusted-origin entry.

## 4. Phone acceptance check

1. Open the Vercel URL in Safari or Chrome, including on mobile data.
2. Confirm catalogue results and shelf map load.
3. Sign in using the admin credentials. Refresh and confirm the session persists.
4. Check out an available Book, return it, and verify wrong then correct shelves.
5. Open a book QR and shelf QR on a second screen or print them; allow camera access and scan both on the phone. Check the manual-code fallback too.
6. Confirm the overdue screen works, reminders queue successfully and arrive through Resend, and sign-out prevents staff actions.

If login returns CSRF errors, check the exact Vercel origin on Render and confirm `/api/session/` is reaching Django. If data does not load, check `/api/health/` on both the Vercel and Render URLs and inspect the Render logs. Do not disable CSRF or add wildcard hostnames as a workaround.

## Demo hosting limits

Render's free web service sleeps after 15 minutes of inactivity and can take about a minute to wake. Open the app before the client meeting. Free PostgreSQL expires after 30 days and has no managed backups; upgrade or export before expiration if the demo must last longer. These are provider limits, not application timers. The documented Web Service configuration does not require a paid Render instance.

## Verification and maintenance

Run `python backend/manage.py test core` and `npm run build` in `frontend` before pushing changes. With production environment variables, run `python backend/manage.py check --deploy`. Production deliberately refuses SQLite or a short/default secret. API responses are private/no-store, and database-backed Axes locks a username after five failed login attempts for 15 minutes, including Django admin login. Reset an accidental lock via `python backend/manage.py axes_reset_username USERNAME` using a secure service shell.

Migrations run during startup to support Render's free service (which has no pre-deploy command/shell). This is suitable for a single demo service; adopt a separate migration phase for multi-instance production. PostgreSQL concurrency and physical-camera behavior still need confirmation on the deployed services. Track client feedback separately from the demo dataset.

References: [Render Django deployment](https://render.com/docs/deploy-django), [Render free-tier limits](https://render.com/docs/free), [Vercel external rewrites](https://vercel.com/docs/routing/rewrites), [Vercel TypeScript configuration](https://vercel.com/docs/project-configuration/vercel-ts).

## Resend email reminders

Follow [email setup](email_setup.md) to verify your custom sending domain. On the web service, set `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`, and `EMAIL_DELIVERY_MODE=direct`. Restart/redeploy the web service. This mode does not require Redis or a background worker.

For optional background delivery, set `EMAIL_DELIVERY_MODE=celery` and a reachable `CELERY_BROKER_URL` on both the web service and a separate worker. Use the Render Key Value internal URL, not localhost. Start the worker with `celery --workdir backend -A config worker --loglevel=info`; it also needs the same database and email configuration. Task results are not stored.
