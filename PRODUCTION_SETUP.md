# EduGuide LS Production Setup

This checklist moves the live Render app from prototype persistence to production-ready Supabase storage plus SMTP email verification.

## 1. Supabase

Create a Supabase project, then open the Supabase SQL editor and run these files in order:

1. `supabase/schema.sql`
2. `supabase/runtime.sql`
3. `supabase/seed.sql`
4. `supabase/seed.normalized.sql`

`runtime.sql` creates the server runtime tables and the private `eduguide-documents` storage bucket used for uploaded result slips and transcripts.

In Supabase, copy:

- Project URL
- Service role key

The service role key must stay server-side only. Never place it in `index.html`, `app.js`, `data/supabase-config.js`, screenshots, or Git.

## 2. Render Environment

In Render, open the `eduguide-ls` web service, go to **Environment**, and set:

```env
DATA_BACKEND=auto
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_STORAGE_BUCKET=eduguide-documents
```

Keep the existing Gemini and admin variables:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.6-flash
ADMIN_NAME=your_admin_name
ADMIN_EMAIL=your_admin_email
ADMIN_PASSWORD=your_admin_password
ADMIN_DISTRICT=your_admin_district
ADMIN_PHONE=your_admin_phone
```

Rotate any API key that has appeared in screenshots or chat before public launch.

## 3. Email OTP

Recommended for Render: use Brevo's HTTPS transactional API because it avoids SMTP connection timeouts.

```env
EMAIL_DEBUG_CODES=false
BREVO_API_KEY=your_brevo_api_key
SMTP_FROM_EMAIL=your_verified_sender_email
SMTP_FROM_NAME=EduGuide LS
```

Fallback: use any email provider that gives SMTP credentials. The sender email should be verified with that provider.

For the common TLS setup:

```env
EMAIL_DEBUG_CODES=false
SMTP_HOST=your_smtp_host
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
SMTP_FROM_EMAIL=your_verified_sender_email
SMTP_FROM_NAME=EduGuide LS
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

For SSL SMTP, use port `465`, set `SMTP_USE_SSL=true`, and set `SMTP_USE_TLS=false`.

## 4. Deploy And Verify

After saving Render environment variables, run **Manual Deploy**.

Open:

```text
https://eduguide-ls.onrender.com/health
```

Expected production values:

```json
{
  "data_backend": "supabase",
  "supabase_configured": true,
  "database_ready": true,
  "storage_ready": true,
  "email_configured": true,
  "email_debug_codes": false,
  "ai_configured": true
}
```

Then log in as the system admin, open the Admin dashboard, press **Check Hosting**, then press **Test Email**. A successful test means public registration codes can be delivered.

## 5. Launch Gate

Do not begin public testing until these are true:

- `/health` shows Supabase, database, storage, email, and AI ready.
- Admin login works with the private owner account.
- Public registration creates only student accounts.
- A new student can receive the email one-time code and sign in.
- Document upload works after redeploy.
- AI chat history still exists after redeploy.
