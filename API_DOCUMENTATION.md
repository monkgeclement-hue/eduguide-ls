# EduGuide LS API Documentation

## Overview

EduGuide LS uses a FastAPI backend for authentication, production persistence, email verification, document uploads, AI guidance, admin reporting, and protected state changes.

**Base URL**: `http://localhost:8765` in development, `https://eduguide-ls.onrender.com` in production.

The programme catalogue is served as versioned static data from `/data/admin-catalog.js` and `/data/catalog.js`. There is no public JSON `/api/programmes` endpoint in this build; the browser reads approved catalogue records from the static catalogue assets and sends student-specific context to protected APIs when needed.

## Authentication

Protected routes use the session token returned by `/api/auth/login` or registration verification. Browser requests include that token through the app's auth header helper.

Public resources:

- `GET /`
- `GET /index.html`
- `GET /styles.css`
- `GET /app.js`
- `GET /manifest.webmanifest`
- `GET /sw.js`
- `GET /icons/{file_name}`
- `GET /data/{file_name}`
- `GET /health`

Student resources require a signed-in user. Admin routes require an administrator account.

## Public Health

### GET /health

Returns minimal public readiness flags.

```json
{
  "ok": true,
  "database_ready": true,
  "storage_ready": true
}
```

Detailed readiness such as Supabase mode, email transport, AI provider, state counts, and startup errors is only available through the protected admin diagnostics route.

## Auth Routes

### GET /api/auth/bootstrap

Creates or refreshes the private system admin from environment variables when the server starts or an admin session needs bootstrap data.

### POST /api/auth/login

Logs in a verified user.

Request:

```json
{
  "email": "student@example.com",
  "password": "secret"
}
```

### POST /api/auth/register/request-code

Starts public student registration by emailing a one-time code.

### POST /api/auth/register/verify

Verifies the one-time registration code and creates the student account.

### POST /api/auth/register

Legacy registration route kept for compatibility with the current app flow.

### POST /api/auth/password-reset/request-code

Emails a password reset code to an existing user.

### POST /api/auth/password-reset/confirm

Verifies the password reset code and stores the new password hash.

### GET /api/auth/me

Returns the current signed-in user. Requires authentication.

### PUT /api/auth/me

Updates the current signed-in user's profile fields. Requires authentication.

### POST /api/auth/logout

Invalidates the current session token.

## Shared State

### GET /api/db/state

Reads protected server-backed UI state, currently the admin review state.

### PUT /api/db/state/{state_key}

Writes an allowed state key. The current allowed key is `review_state`.

### DELETE /api/db/state/{state_key}

Deletes an allowed state key. Admin-only.

## Admin Routes

### GET /api/db/diagnostics

Returns protected deployment diagnostics for the Admin dashboard, including backend mode, storage readiness, email readiness, AI readiness, runtime event counts, document counts, and auth user counts.

### GET /api/admin/users

Lists public-safe user records for admin review.

### GET /api/admin/intelligence

Returns Admin Intelligence metrics such as searches, blocked reasons, upload/OCR failures, AI questions, school profile views, and new user alerts.

### GET /api/admin/audit

Returns recent admin audit events.

### POST /api/admin/test-email

Sends a production email test to the admin email. This is the quickest way to confirm OTP delivery settings.

### PUT /api/admin/users/{user_id}/role

Changes a user's role.

### PUT /api/admin/users/{user_id}/status

Changes a user's account status.

### PUT /api/admin/users/{user_id}/review

Marks a student account as reviewed by admin.

## Document Routes

### POST /api/documents/upload

Uploads up to 5 documents per request for the signed-in user. Supported file types are PDF, DOCX, JPG, JPEG, and PNG. Each file is limited to 10 MB.

### GET /api/documents/user/{user_id}

Lists stored document metadata for a user. Users can read their own documents; admins can inspect user documents.

### POST /api/documents/{document_id}/extract

Re-runs text extraction or OCR for a stored document.

### GET /api/documents/{document_id}/download

Downloads a stored document through the protected document API.

### DELETE /api/documents/{document_id}

Deletes a stored document and its metadata.

## Runtime Events

### POST /api/events

Stores analytics and activity events such as searches, match views, blocked reasons, document failures, school profile views, and AI guidance questions.

## AI Routes

### GET /api/ai/chat

Returns recent server-side AI chat history for the signed-in user.

### DELETE /api/ai/chat

Clears the signed-in user's stored AI chat history.

### POST /api/ai/guidance

Generates EduGuide AI guidance from the student's profile, current matches, blocked matches, documents, and conversation context. The server limits payload size and prompt lengths, stores recent chat memory, and constrains recommendations to qualified or nearly qualified catalogue evidence.

## Security Notes

- API keys stay on the server through Render environment variables.
- Public signup creates student accounts only.
- Email OTP, password reset, AI chat, document upload, and login routes are rate-limited.
- The backend sends Content Security Policy, HSTS, and frame-protection headers.
- Supabase is used for production persistence when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are configured.
