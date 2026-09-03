# EduGuide LS

EduGuide LS is a Lesotho higher-education guidance web app. This milestone includes student guidance, programme matching, AI guidance, admin catalogue review, email verification, document upload, runtime analytics, and Supabase/Postgres production persistence.

## Run the Prototype

### Static mode

```powershell
cd "C:\Users\lepha\Documents\New project"
py -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/index.html
```

Static mode runs the dashboards and Matching Engine v1, but the AI advisor will show a server-not-running message.

### AI and database mode

Install the backend libraries:

```powershell
cd "C:\Users\lepha\Documents\New project"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a `.env` file from `.env.example`, then set your Gemini key:

```powershell
copy .env.example .env
notepad .env
```

Use Gemini by default:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-3.6-flash
DATA_BACKEND=auto
EMAIL_DEBUG_CODES=true
```

Run the FastAPI server:

```powershell
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765/index.html
```

## Installable Web App

EduGuide LS is configured as an installable web app through `manifest.webmanifest` and `sw.js`. On Android/Chrome, open the hosted link and use the **Install EduGuide LS** button when it appears, or use the browser menu's install option. On iPhone/Safari, use **Share -> Add to Home Screen**.

The installed app uses the same hosted backend for login, AI guidance, document upload, and database features.

Public signup verifies email with a one-time code before the account is created. For local testing, `EMAIL_DEBUG_CODES=true` shows the code in the signup message if email delivery is not configured. On the hosted app, keep debug codes off and set `BREVO_API_KEY` plus `SMTP_FROM_EMAIL` in Render. SMTP variables are still supported as a fallback.

This mode creates a local SQLite database at `data/eduguide.db` unless Supabase runtime persistence is configured. The app uses the active backend for:

- registered users, admin roles, account status, and activity history
- email verification codes for public registration
- admin review state for programmes and data gaps
- uploaded document metadata
- AI recommendation-run history and recent AI chat memory

Useful checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/api/db/diagnostics
```

For public testing and hosting steps, see `DEPLOYMENT.md`. For the Supabase + SMTP launch checklist, see `PRODUCTION_SETUP.md`. The project now includes a `Dockerfile`, `.dockerignore`, and `render.yaml` so the same FastAPI app can be deployed without exposing `.env` secrets.

In VS Code, use **Run and Debug** and choose **Run EduGuide LS** after installing `requirements.txt`. The `.vscode` task starts the FastAPI server before opening Chrome.

There are no demo login accounts. Public registration always creates a student account. The System Admin is created privately from server environment variables: ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_DISTRICT, and ADMIN_PHONE.

The browser UI can still load as static HTML, but local FastAPI mode is preferred. It includes:

- Student dashboard with profile inputs, grades, interests, and document upload/dropzone support
- Real document upload in FastAPI mode, with files stored locally under `data/uploads/`, text/OCR extraction, and machine-detected grade suggestions
- Matching Engine v2 using the real 233-record catalogue, inferred domains, eligibility checks, funding readiness, institution-grouped results, and data-confidence warnings
- AI advisor that explains qualified/almost matches through a server-side Gemini API proxy, remembers recent chat turns, uses blocked-pathway evidence, and keeps OpenAI available as an optional fallback
- Skills, careers, NMDS readiness, and labour-market notes
- Admin dashboard for review-queue style data approval, user search, role management, account status, and activity monitoring
- Data-source dashboard for verified Lesotho education sources

## Data Foundation

- `data/eduguide.db` is created automatically by `server.py` for local real-database persistence. It is ignored by git.
- `data/uploads/` is created automatically when users upload documents. Uploaded files are ignored by git and served only through the document download API.
- Document extraction uses local parsers for text PDFs, DOCX, and text files. Image/scanned OCR uses Gemini through the server-side `GEMINI_API_KEY`.
- `supabase/runtime.sql` creates the persistent runtime tables, AI chat memory table, and private storage bucket used by the hosted FastAPI app.
- `supabase/schema.sql` contains the normalized Postgres schema.
- `supabase/seed.sql` contains starter reference data and shared source records.
- `supabase/seed.normalized.sql` loads the real scraped/manual catalogue into normalized tables.
- `data/source-manifest.json` lists the verified sources we start from.
- `data/programmes.seed.json` contains starter programme records used by the UI.

## Scraper Starter

`scripts/scrape-sources.mjs` is a dependency-free Node script that fetches source pages and creates import-candidate JSON.

Run with the bundled Codex Node runtime if system Node/npm is unavailable:

```powershell
& 'C:\Users\lepha\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' scripts/scrape-sources.mjs
```

The script writes `data/import-candidates.generated.json`. Admins should review scraped candidates before publishing them into canonical tables.

For a richer institution-categorised programme dataset, run:

```powershell
& 'C:\Users\lepha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/scrape-real-programmes.py
```

That writes:

- `data/real/programmes.flat.json`
- `data/real/programmes.by-institution.json`
- `data/real/institutions/*.json`
- `data/real/summary.json`

To rebuild the normalized Supabase seed from the real JSON data, run:

```powershell
& 'C:\Users\lepha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/build-normalized-seed.py
```

That writes `supabase/seed.normalized.sql`.

## Next Implementation Step

Once `npm`, `pnpm`, or another package manager is available, migrate this static vertical slice into a `Next.js + TypeScript + Supabase` app using the same data model and UI structure.
