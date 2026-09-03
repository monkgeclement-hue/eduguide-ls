# Developer Guide - EduGuide LS

EduGuide LS is a Lesotho higher-education guidance web app. It combines a browser-first student experience with a FastAPI backend for authentication, persistence, document upload, AI guidance, and admin reporting.

## Current Stack

Frontend:

- HTML, CSS, and vanilla JavaScript
- Installable PWA support through `manifest.webmanifest` and `sw.js`
- Static catalogue assets from `data/catalog.js`, `data/admin-catalog.js`, and `data/source-manifest.json`

Backend:

- Python FastAPI in `server.py`
- Uvicorn ASGI server
- SQLite for local fallback
- Supabase/Postgres for production persistence
- Supabase Storage or local `data/uploads/` for documents
- Gemini API by default, with optional OpenAI fallback
- Brevo HTTPS email API by default, with SMTP fallback

Deployment:

- Docker and Render via `Dockerfile`, `.dockerignore`, and `render.yaml`
- Secrets are supplied through Render environment variables

## Run Locally

```powershell
cd "C:\Users\lepha\Documents\New project"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

For static-only UI testing, this still works:

```powershell
py -m http.server 8765 --bind 127.0.0.1
```

Static mode cannot run login, uploads, email OTP, AI guidance, or server persistence.

## Environment

Use `.env.example` as the local template. Production values belong in Render only.

Required for production:

- `AI_PROVIDER=gemini`
- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-3.6-flash`
- `DATA_BACKEND=auto`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET=eduguide-documents`
- `ADMIN_NAME`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `ADMIN_DISTRICT`
- `ADMIN_PHONE`
- `EMAIL_DEBUG_CODES=false`
- `BREVO_API_KEY`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME=EduGuide LS`

SMTP variables are still supported as a fallback:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`

## Data Model

Primary shipped catalogue:

- `data/admin-catalog.js` - reviewed catalogue used by the app
- `data/catalog.js` - public starter/fallback catalogue
- `data/source-manifest.json` - source registry
- `data/programmes.seed.json` - starter programme records

Current shipped catalogue summary:

- 233 programmes
- 11 institutions
- 25 sources
- 6 fee schedules
- 90 open data gaps

Supabase setup:

- `supabase/schema.sql` creates the normalized catalogue schema
- `supabase/runtime.sql` creates runtime persistence tables
- `supabase/seed.sql` adds starter reference/source data
- `supabase/seed.normalized.sql` loads catalogue records

## Backend API

The authoritative route list is in `API_DOCUMENTATION.md`.

Important route groups:

- Public app shell and static data: `/`, `/index.html`, `/app.js`, `/styles.css`, `/sw.js`, `/manifest.webmanifest`, `/data/{file_name}`, `/icons/{file_name}`
- Public health: `/health`
- Authentication and OTP: `/api/auth/*`
- Documents: `/api/documents/*`
- AI chat and guidance: `/api/ai/*`
- Runtime analytics events: `/api/events`
- Admin users, intelligence, audit, test email, and diagnostics: `/api/admin/*`, `/api/db/diagnostics`

There is no public JSON `/api/programmes` endpoint in the current build. Catalogue browsing happens from static approved catalogue assets in the browser.

## Frontend Areas

Main files:

- `index.html` - app shell and view markup
- `styles.css` - layout, responsive design, and UI polish
- `app.js` - routing, matching, AI chat UI, admin dashboard, school/course profiles, document UX, and API calls
- `sw.js` - PWA cache contract

Useful `app.js` areas:

- Matching and eligibility scoring: search for `calculateProgrammeMatch`
- AI payload and chat flow: search for `getAiProfilePayload` and `requestAiGuidance`
- AI Interview Mode: search for `aiInterviewState`
- School and course profiles: search for `renderSelectedSchoolProfile` and `renderExplorerCourseProfile`
- Admin Intelligence: search for `renderAdminIntelligence`
- Document upload: search for `addDocuments` and `uploadDocumentsToServer`

## Validation

Run these before committing:

```powershell
node --check app.js
py -3 -c "import ast, pathlib; ast.parse(pathlib.Path('server.py').read_text(encoding='utf-8')); print('server.py AST ok')"
git diff --check
powershell -ExecutionPolicy Bypass -File .\smoke-test.ps1 -BaseUrl "https://eduguide-ls.onrender.com"
```

The smoke test checks:

- minimal public health
- admin bootstrap
- protected diagnostics and user routes
- static assets
- service worker cache versioning
- public catalogue boundary
- upload endpoint protection
- security headers

## Safe Change Rules

- Keep API keys server-side only.
- Public registration must create student accounts only.
- Keep admin-only diagnostics protected.
- Keep document downloads behind the document API.
- Bump `sw.js` cache name when changing cached frontend assets.
- Re-run `supabase/runtime.sql` when runtime table definitions change.
- Re-run the smoke test after deployment.

## Deployment Checklist

1. Commit code changes.
2. Push to GitHub.
3. Deploy the latest commit on Render.
4. Open `https://eduguide-ls.onrender.com/health`.
5. Log in as admin.
6. Press **Check Hosting**.
7. Press **Test Email**.
8. Confirm public signup receives an OTP.
9. Confirm a student login still sees previous profile/chat/document history after redeploy.

## Troubleshooting

If login or OTP fails:

- Check Render environment variables.
- Confirm `EMAIL_DEBUG_CODES=false` in production.
- Confirm `BREVO_API_KEY` and `SMTP_FROM_EMAIL` are set.
- Use Admin dashboard **Test Email**.

If data disappears after redeploy:

- Check `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Open Admin dashboard **Check Hosting** and confirm the database reads as Supabase.
- Confirm `supabase/runtime.sql` was run successfully.

If AI fails:

- Confirm `GEMINI_API_KEY` is valid.
- Confirm `GEMINI_MODEL=gemini-3.6-flash`.
- Check the Admin dashboard readiness panel.

If users see old JavaScript or CSS:

- Bump `CACHE_NAME` in `sw.js`.
- Redeploy.
- Refresh the installed app or browser tab.
