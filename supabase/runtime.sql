create extension if not exists pgcrypto;

-- Runtime persistence used by the current FastAPI app.
-- These tables keep prototype accounts, sessions, admin review state,
-- uploaded document metadata, and AI run history alive across redeploys.
-- The app accesses them only from the server with SUPABASE_SERVICE_ROLE_KEY.

create table if not exists public.runtime_app_state (
  state_key text primary key,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.runtime_auth_sessions (
  token text primary key,
  user_id text not null,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table if not exists public.runtime_uploaded_documents (
  id text primary key,
  user_id text not null,
  original_name text not null,
  stored_name text not null,
  content_type text,
  size_bytes bigint not null,
  storage_path text not null,
  status text not null default 'Uploaded - OCR pending',
  extraction_status text not null default 'pending',
  extraction_text text,
  extracted_grades jsonb not null default '[]'::jsonb,
  extraction_error text,
  extracted_at timestamptz,
  uploaded_at timestamptz not null default now()
);

create table if not exists public.runtime_recommendation_runs (
  id uuid primary key default gen_random_uuid(),
  mode text not null default 'guidance',
  question text,
  profile_name text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_runtime_auth_sessions_user on public.runtime_auth_sessions(user_id);
create index if not exists idx_runtime_uploaded_documents_user on public.runtime_uploaded_documents(user_id, uploaded_at desc);
create index if not exists idx_runtime_uploaded_documents_extraction on public.runtime_uploaded_documents(extraction_status);
create index if not exists idx_runtime_recommendation_runs_created on public.runtime_recommendation_runs(created_at desc);

insert into storage.buckets (id, name, public, file_size_limit)
values ('eduguide-documents', 'eduguide-documents', false, 10485760)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit;

alter table public.runtime_app_state enable row level security;
alter table public.runtime_auth_sessions enable row level security;
alter table public.runtime_uploaded_documents enable row level security;
alter table public.runtime_recommendation_runs enable row level security;
