# Supabase Database

EduGuide LS now uses a normalized catalogue schema.

Run order:

1. `schema.sql`
2. `runtime.sql`
3. `seed.sql`
4. `seed.normalized.sql`

Hosted runtime persistence:

- Run `runtime.sql` in the Supabase SQL editor.
- In Render, set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET=eduguide-documents`.
- Keep all Supabase credentials server-side only. Do not expose service-role or anon keys in browser files, screenshots, or Git.
- The FastAPI server stores live accounts, sessions, admin review state, uploaded document metadata, AI chat memory, and AI run history in the `runtime_*` tables.
- Uploaded files are stored in the private `eduguide-documents` Storage bucket.
- For the full production checklist, including SMTP email verification, see `../PRODUCTION_SETUP.md`.

Admin dashboard persistence:

- The browser keeps a local resilience copy of the review snapshot, but authenticated FastAPI endpoints are the only production write path.
- The server applies EduGuide role checks, rate limits, audit events, and historical-evidence safeguards before saving the review snapshot to Supabase.
- The browser does not load a Supabase client or database key.

`seed.sql` keeps small reference data and shared source links. `seed.normalized.sql` is generated from the real source-derived JSON files and loads the current Lesotho catalogue.

Regenerate the normalized seed after changing `data/real/*.json`:

```powershell
& 'C:\Users\lepha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build-normalized-seed.py
```

Core table groups:

- Catalogue: `institutions`, `faculties`, `programmes`, `programme_requirement_sets`, `programme_requirement_subjects`
- Evidence: `source_documents`, `programme_sources`
- Fees: `fee_schedules`, `fee_items`
- Guidance: `careers`, `skills`, `programme_careers`, `programme_skills`
- Funding: `scholarships`, `scholarship_criteria`
- Review workflow: `import_batches`, `import_candidates`, `review_events`, `data_gaps`
- Student workflow: `student_profiles`, `student_profile_subjects`, `student_documents`, `recommendation_runs`, `recommendation_results`

Current normalized seed coverage:

- 17 institutions
- 262 programmes
- 36 faculties
- 37 source documents
- 6 fee schedules
- CAS handbook policies
- NMDS scholarship score criteria
