# EduGuide LS Deployment

This guide prepares the current FastAPI prototype for public testing. It keeps AI keys on the server, serves the frontend from FastAPI, and uses the local SQLite database for prototype persistence.

## Local Production Check

Run the app without hot reload:

```powershell
cd "C:\Users\lepha\Documents\New project"
.\.venv\Scripts\Activate.ps1
python -m uvicorn server:app --host 127.0.0.1 --port 8765
```

Then check:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/api/db/diagnostics
```

The health response should show `ok`, `database_ready`, and `storage_ready` as `true`.

## Local Docker Check

If Docker Desktop is installed:

```powershell
cd "C:\Users\lepha\Documents\New project"
docker build -t eduguide-ls .
docker run --rm -p 8765:8765 --env-file .env eduguide-ls
```

Open:

```text
http://127.0.0.1:8765/
```

## Environment Variables

Set these on the server or hosting platform:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_secret_key
GEMINI_MODEL=gemini-3.6-flash
ADMIN_NAME=your_admin_name
ADMIN_EMAIL=your_admin_email
ADMIN_PASSWORD=your_admin_password
ADMIN_DISTRICT=your_admin_district
ADMIN_PHONE=your_admin_phone
```

Optional OpenAI fallback:

```env
OPENAI_API_KEY=your_secret_key
OPENAI_MODEL=gpt-5.2
```

Never commit `.env`. The key must stay server-side because the browser calls `/api/ai/guidance`, not Gemini directly.

## Render Public Test

The repository includes `render.yaml` for a Docker-based Render deployment.

1. Push the project to a private GitHub repository.
2. Confirm `.env`, `data/eduguide.db`, and `data/uploads/` are not committed.
3. In Render, create a new Blueprint or Docker web service from the repository.
4. Add `GEMINI_API_KEY` and the `ADMIN_*` variables as secret environment variables.
5. Keep `AI_PROVIDER=gemini` and `GEMINI_MODEL=gemini-3.6-flash`.
6. Deploy, then test `/health`, `/`, and `/api/db/diagnostics`.

Useful Render references:

- [Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Docker on Render](https://render.com/docs/docker)
- [Environment Variables and Secrets](https://render.com/docs/configure-environment-variables)
- [Web Services and PORT](https://render.com/docs/web-services)

## Public Testing Checklist

- Student login and registration work.
- Public registration creates student accounts only; System Admin is created from private server environment variables.
- Admin login works, can search users, review new accounts, grant admin roles, suspend/reactivate accounts, and inspect activity.
- Student grades include Food & Nutrition, Religious Knowledge, and Computer Skills.
- View Matches groups eligible programmes by institution.
- Document upload stores files and extracts readable text or OCR suggestions.
- AI guidance responds without exposing the Gemini key in browser code.
- Scholarship/NMDS readiness clearly says it is an estimate only.
- Admin data management can add, edit, approve, reject, and track programme gaps.
- Mobile layout loads with CSS and usable buttons.
- Phone browser can install the app shell from the manifest. API routes still need the live server.

## Prototype Limits Before Real Launch

The current local SQLite database and uploaded files are good for prototype testing. A hosted free container may reset local files after redeploys or restarts, depending on the host.

For a real public beta, move these parts to Supabase:

- Auth and role storage
- Normalized programme tables
- Uploaded document storage
- Recommendation and AI run history

The project already has starter Supabase files:

- `supabase/schema.sql`
- `supabase/seed.normalized.sql`

Use those when we migrate from local prototype storage to hosted persistent storage.
