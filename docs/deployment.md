# Render + Vercel demo deployment

The phone opens the Vercel HTTPS URL. Vercel forwards `/api/*` to Render. Session cookies stay on the Vercel site (host-only, HttpOnly, Secure, SameSite=Lax), avoiding third-party-cookie restrictions on phones. Django trusts only the frontend origins you explicitly configure. Do not change frontend requests to call Render directly.

## 1. Push the repository

Commit application code, migrations, lockfiles, `render.yaml`, scripts and deployment docs to GitHub. Do not commit `.env`, SQLite, local credentials, generated static files or node_modules. Original PDF reference material is not required for deployment.

## 2. Render backend

In Render, create a **Blueprint** from the GitHub repository using root `render.yaml`. It defines a free Python web service and a free PostgreSQL database.

Supply:

- `DJANGO_CSRF_TRUSTED_ORIGINS`: the exact frontend HTTPS origin, e.g. `https://libsort-yourname.vercel.app`. You can initially leave the value blank until Vercel assigns the final URL, then update Render before logging in. Comma-separate additional known origins; never trust every Vercel tenant.
- `DEMO_STAFF_PASSWORD`: a new strong secret chosen in Render. Do not use the local development password from the conversation.

Render generates `DJANGO_SECRET_KEY` and supplies `DATABASE_URL`. Its own hostname is automatically allowed. The build installs locked dependencies and collects admin static files. Startup migrates PostgreSQL, seeds the synthetic demo idempotently, creates `demo_staff` once, then starts Gunicorn. The staff account can use the demo UI but cannot edit admin models. Remove `DEMO_STAFF_PASSWORD` and `DEMO_STAFF_USERNAME` after successful creation. Existing account credentials are never reset on redeployment. Set `SEED_DEMO_DATA=0` after the initial deployment if you want to manage demo records without seeding.

Confirm `https://YOUR-API.onrender.com/api/health/` returns `{"status":"ok"}` and copy the Render origin. For a full admin account use `python backend/manage.py createsuperuser` in a supported service shell or through a secure administrative connection; never expose an account-creation endpoint.

## 3. Vercel frontend

Import the same GitHub repository. Set **Root Directory** to `frontend`, Framework to **Vite**, and Node.js to **22.x**. Keep the repository's build/output configuration.

Set the environment variable **`BACKEND_URL`** to the Render HTTPS origin, e.g. `https://libsort-api-xxxx.onrender.com`, with no `/api` suffix. Set it for Production (and Preview only if needed). `frontend/vercel.ts` reads it when deployment configuration is evaluated and creates the proxy rewrite. Deploy.

Copy the stable Vercel production origin into Render's `DJANGO_CSRF_TRUSTED_ORIGINS`. Save/redeploy Render. Use the stable production URL for the client; a new preview hostname needs its own trusted-origin entry. If the Render hostname changes, update `BACKEND_URL` in Vercel and redeploy.

## 4. Phone acceptance check

1. Open the Vercel URL in Safari or Chrome, including on mobile data.
2. Confirm catalogue results and shelf map load.
3. Sign in using the deployment staff credentials. Refresh and confirm the session persists.
4. Check out an available Book, return it, and verify wrong then correct shelves.
5. Open a book QR and shelf QR on a second screen or print them; allow camera access and scan both on the phone. Check the manual-code fallback too.
6. Confirm the overdue screen works, reminders explicitly say they are demo logs, and sign-out prevents staff actions.

If login returns CSRF errors, check the exact Vercel origin on Render and confirm `/api/session/` is reaching Django. If data does not load, check `BACKEND_URL`, `/api/health/`, and Render logs. Do not disable CSRF or add wildcard hostnames as a workaround.

## Demo hosting limits

Render's free web service sleeps after 15 minutes of inactivity and can take about a minute to wake. Open the app before the client meeting. Free PostgreSQL expires after 30 days and has no managed backups; upgrade or export before expiration if the demo must last longer. These are provider limits, not application timers. No paid resources are required by the checked-in Blueprint, but review provider billing and eligibility before creating resources.

## Verification and maintenance

Run `python backend/manage.py test core` and `npm run build` in `frontend` before pushing changes. With production environment variables, run `python backend/manage.py check --deploy`. Production deliberately refuses SQLite or a short/default secret. API responses are private/no-store, and database-backed Axes locks a username after five failed login attempts for 15 minutes, including Django admin login. Reset an accidental lock via `python backend/manage.py axes_reset_username USERNAME` using a secure service shell.

Migrations run during startup to support Render's free service (which has no pre-deploy command/shell). This is suitable for a single demo service; adopt a separate migration phase for multi-instance production. PostgreSQL concurrency and physical-camera behavior still need confirmation on the deployed services. Track client feedback separately from the demo dataset.

References: [Render Django deployment](https://render.com/docs/deploy-django), [Render free-tier limits](https://render.com/docs/free), [Vercel external rewrites](https://vercel.com/docs/routing/rewrites), [Vercel TypeScript configuration](https://vercel.com/docs/project-configuration/vercel-ts).
