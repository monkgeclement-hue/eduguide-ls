# Reliability and privacy fixes — 14 September 2026

## Deploy

Push is intended for the existing `main` branch. In Render choose **Manual Deploy → Deploy latest commit**. No SQL migration, new secret, or package installation step is required outside the normal build. Existing Supabase credentials and runtime tables are reused. Auto-deployment remains disabled in `render.yaml`.

The hosted app now reports HTTP 503 if database or document storage is unavailable. On Render, missing Supabase credentials no longer silently select container-local SQLite. Local development still supports SQLite. Keep `FORWARDED_ALLOW_IPS` restricted to known proxy addresses; never use `*` to trust arbitrary clients. Account limits operate independently of the IP address, including on shared school networks.

Existing browser sessions need to sign in again once after this release. Tokens are now kept in tab-session storage; profile recovery remains available through local storage. Sign-out clears EduGuide's locally cached profiles/chat and pending edits. The service-worker version is updated with the CSS and JavaScript assets.

## Changes

- JSON-state updates use a SQLite transaction or Supabase conditional update with retries. Snapshot merging preserves unrelated user/assignment/proposal edits; incompatible edits return 409. No in-process lock is relied on for cross-worker consistency. This fixes lost updates without requiring a risky live schema conversion; normalized per-user tables remain a future scalability improvement.
- Login and other rate limits use shared durable state with separate account and IP scopes. Raw forwarded headers are not accepted by application code. Expired limit records are cleaned up.
- Bootstrap does not overwrite an existing account's password on every login. Environment bootstrap credentials create the initial owner only; use the existing password-reset flow to change its password.
- The icon library is vendored with its license. Script CSP is restricted to the app's own origin, with no inline executable handlers. API responses use `Cache-Control: no-store`.
- Student profiles offer data export and password-confirmed deletion. Document deletion removes the object before its metadata so failed storage operations can be retried. Account deletion covers active account data, document files/metadata, chat, counsellor records, linked AI history, verification codes, and user events. Staff deletion is blocked. Historical unlinked recommendation records are cleaned up after 30 days; hosting backups remain operator-managed.
- A public privacy notice explains local caches, AI processing, deletion limitations, and student choices.
- Document extraction runs outside the async event loop, with at most two extraction tasks per worker. Oversized DOCX expansion and PDFs over 30 pages are rejected. Accounts have a 25-document upload check. A durable background queue and process-level parser isolation remain future operational improvements.
- Records without captured requirements stay exploratory rather than being declared qualified. Suggested careers/skills are labelled as such. Funding's headline percentage now counts detected checklist items; it is not a sponsorship probability or proof that a sponsor will accept the documents.
- Fashion skill suggestions and their generator were corrected. Enrichment no longer automatically approves source-linked records or overwrites an existing duration with an inference.
- CI runs all Python suites plus executable JavaScript matching tests.

## Validation and limits

Tests use isolated local databases. Supabase compare-and-swap retry behavior is covered through a simulated API response sequence; no production student records were modified to test it. Browser checks cover student sign-in, dashboard/profile rendering, the deletion confirmation and cancel path, and console errors. Deletion is exercised through isolated HTTP tests, not against a real account.

The 83 approved bundled records missing requirement summaries still require current institution evidence. The UI now handles missing evidence conservatively; no fabricated requirements or review dates were added. Full catalogue verification, validated scholarship prediction, a user pilot, normalized database migration, and production load testing are not claimed by this release.
