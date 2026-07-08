# Supabase Database

EduGuide LS now uses a normalized catalogue schema.

Run order:

1. `schema.sql`
2. `seed.sql`
3. `seed.normalized.sql`

Admin dashboard persistence:

- The browser prototype always saves admin review changes to `localStorage`.
- To sync admin actions to Supabase, edit `data/supabase-config.js` and set:
  - `url`
  - `anonKey`
- The current admin actions update `programmes.review_status`, update `data_gaps.status`, and insert rows into `review_events`.
- Use normal Supabase RLS/service-role planning before exposing this to public users. The current static prototype is suitable for local development and review workflows.

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

- 11 institutions
- 234 programmes
- 30 faculties
- 31 source documents
- 6 fee schedules
- CAS handbook policies
- NMDS scholarship score criteria
