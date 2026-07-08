create extension if not exists pgcrypto;

-- EduGuide LS normalized catalogue schema.
-- The catalogue is split into:
-- 1. canonical education data,
-- 2. source/evidence data,
-- 3. admin review/import workflow,
-- 4. student recommendation workflow.

create table if not exists public.profiles (
  id uuid primary key,
  role text not null default 'student' check (role in ('student', 'reviewer', 'admin')),
  full_name text,
  district text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.institutions (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  short_name text,
  institution_type text,
  district text,
  website_url text,
  verification_status text not null default 'pending' check (verification_status in ('pending', 'verified', 'needs_review', 'rejected')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.institution_aliases (
  id uuid primary key default gen_random_uuid(),
  institution_id uuid not null references public.institutions(id) on delete cascade,
  alias text not null,
  alias_type text not null default 'short_name',
  unique (institution_id, alias)
);

create table if not exists public.faculties (
  id uuid primary key default gen_random_uuid(),
  institution_id uuid not null references public.institutions(id) on delete cascade,
  name text not null,
  external_key text,
  created_at timestamptz not null default now(),
  unique (institution_id, name)
);

create table if not exists public.subjects (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  subject_group text
);

create table if not exists public.source_documents (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  source_type text not null,
  url text unique,
  local_path text unique,
  owner_institution_id uuid references public.institutions(id) on delete set null,
  trust_level text not null default 'unverified' check (trust_level in ('verified_core', 'official_local', 'third_party', 'manual_confirmation', 'unverified')),
  publication_date date,
  academic_year text,
  extraction_method text,
  last_checked_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  check (url is not null or local_path is not null)
);

create table if not exists public.programmes (
  id uuid primary key default gen_random_uuid(),
  external_key text not null unique,
  institution_id uuid not null references public.institutions(id) on delete cascade,
  faculty_id uuid references public.faculties(id) on delete set null,
  code text,
  name text not null,
  category text,
  qualification_level text,
  duration_text text,
  delivery_mode text,
  overview text,
  review_status text not null default 'needs_admin_review' check (review_status in ('draft', 'needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  confidence_score numeric(5,2),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (institution_id, name)
);

create table if not exists public.programme_sources (
  id uuid primary key default gen_random_uuid(),
  programme_id uuid not null references public.programmes(id) on delete cascade,
  source_document_id uuid not null references public.source_documents(id) on delete cascade,
  relation_type text not null default 'primary' check (relation_type in ('primary', 'supporting', 'fee_supporting', 'manual_confirmation')),
  extraction_method text,
  evidence_text text,
  confidence_score numeric(5,2),
  created_at timestamptz not null default now(),
  unique (programme_id, source_document_id, relation_type)
);

create table if not exists public.programme_requirement_sets (
  id uuid primary key default gen_random_uuid(),
  programme_id uuid not null references public.programmes(id) on delete cascade,
  route_name text not null default 'General entry',
  requirement_summary text not null,
  min_subject_count int,
  aggregate_max numeric(5,2),
  source_document_id uuid references public.source_documents(id) on delete set null,
  review_status text not null default 'needs_admin_review' check (review_status in ('needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (programme_id, route_name)
);

create table if not exists public.programme_requirement_subjects (
  id uuid primary key default gen_random_uuid(),
  requirement_set_id uuid not null references public.programme_requirement_sets(id) on delete cascade,
  subject_id uuid references public.subjects(id) on delete set null,
  subject_name text not null,
  min_grade text,
  grade_system text default 'LGCSE/COSC',
  is_required boolean not null default true,
  alternative_group text,
  notes text
);

create table if not exists public.programme_modules (
  id uuid primary key default gen_random_uuid(),
  programme_id uuid not null references public.programmes(id) on delete cascade,
  year_no int,
  semester_no int,
  module_code text,
  module_name text not null,
  credits numeric(8,2),
  repeat_fee_amount numeric(12,2),
  currency text default 'LSL',
  source_document_id uuid references public.source_documents(id) on delete set null,
  raw_payload jsonb not null default '{}'::jsonb
);

create table if not exists public.fee_schedules (
  id uuid primary key default gen_random_uuid(),
  external_key text not null unique,
  institution_id uuid not null references public.institutions(id) on delete cascade,
  source_document_id uuid references public.source_documents(id) on delete set null,
  title text not null,
  academic_year text,
  currency text not null default 'LSL',
  review_status text not null default 'needs_admin_review' check (review_status in ('needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  notes text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.fee_items (
  id uuid primary key default gen_random_uuid(),
  external_key text not null unique,
  fee_schedule_id uuid not null references public.fee_schedules(id) on delete cascade,
  programme_id uuid references public.programmes(id) on delete set null,
  faculty_id uuid references public.faculties(id) on delete set null,
  programme_group text,
  item_name text not null,
  item_type text not null default 'fee' check (item_type in ('application', 'acceptance', 'tuition', 'levy', 'boarding', 'catering', 'exam', 'book', 'registration', 'other', 'professional_body', 'fee')),
  amount numeric(12,2),
  amount_max numeric(12,2),
  percent_of_tuition numeric(6,2),
  basis text,
  student_category text,
  attendance_mode text,
  refund_status text,
  annual_estimate_amount numeric(12,2),
  source_document_id uuid references public.source_documents(id) on delete set null,
  notes text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.careers (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  description text,
  labour_sector text,
  source_document_id uuid references public.source_documents(id) on delete set null,
  review_status text not null default 'needs_admin_review' check (review_status in ('needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  created_at timestamptz not null default now()
);

create table if not exists public.skills (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  skill_category text,
  description text,
  review_status text not null default 'needs_admin_review' check (review_status in ('needs_admin_review', 'flagged', 'approved', 'rejected', 'archived'))
);

create table if not exists public.programme_careers (
  programme_id uuid not null references public.programmes(id) on delete cascade,
  career_id uuid not null references public.careers(id) on delete cascade,
  relevance_score int not null default 80 check (relevance_score between 0 and 100),
  mapping_method text not null default 'manual_or_source',
  review_status text not null default 'needs_admin_review' check (review_status in ('needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  primary key (programme_id, career_id)
);

create table if not exists public.programme_skills (
  programme_id uuid not null references public.programmes(id) on delete cascade,
  skill_id uuid not null references public.skills(id) on delete cascade,
  relevance_score int not null default 80 check (relevance_score between 0 and 100),
  mapping_method text not null default 'manual_or_ai_suggested',
  review_status text not null default 'needs_admin_review' check (review_status in ('needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  primary key (programme_id, skill_id)
);

create table if not exists public.scholarships (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  provider text not null,
  description text,
  eligibility_summary text,
  source_document_id uuid references public.source_documents(id) on delete set null,
  source_url text,
  review_status text not null default 'needs_admin_review' check (review_status in ('draft', 'needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  status text not null default 'needs_admin_review' check (status in ('draft', 'needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  created_at timestamptz not null default now(),
  unique (provider, name)
);

create table if not exists public.scholarship_criteria (
  id uuid primary key default gen_random_uuid(),
  scholarship_id uuid not null references public.scholarships(id) on delete cascade,
  criterion_key text not null,
  criterion_label text not null,
  criterion_type text not null default 'score_component',
  weight numeric(6,2),
  rule_summary text,
  raw_payload jsonb not null default '{}'::jsonb,
  unique (scholarship_id, criterion_key)
);

create table if not exists public.labour_market_notes (
  id uuid primary key default gen_random_uuid(),
  sector text not null,
  note text not null,
  geography text default 'Lesotho',
  source_document_id uuid references public.source_documents(id) on delete set null,
  source_url text,
  review_status text not null default 'needs_admin_review' check (review_status in ('draft', 'needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  status text not null default 'needs_admin_review' check (status in ('draft', 'needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  created_at timestamptz not null default now()
);

create table if not exists public.institution_policies (
  id uuid primary key default gen_random_uuid(),
  external_key text not null unique,
  institution_id uuid not null references public.institutions(id) on delete cascade,
  source_document_id uuid references public.source_documents(id) on delete set null,
  policy_type text not null,
  title text not null,
  policy_text text not null,
  review_status text not null default 'needs_admin_review' check (review_status in ('needs_admin_review', 'flagged', 'approved', 'rejected', 'archived')),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (institution_id, policy_type, title)
);

create table if not exists public.import_batches (
  id uuid primary key default gen_random_uuid(),
  batch_key text not null unique,
  source_label text not null,
  import_method text not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.import_candidates (
  id uuid primary key default gen_random_uuid(),
  import_batch_id uuid references public.import_batches(id) on delete set null,
  source_document_id uuid references public.source_documents(id) on delete set null,
  entity_type text not null,
  external_key text,
  payload jsonb not null,
  evidence_text text,
  confidence_score numeric(5,2) default 0,
  review_status text not null default 'pending' check (review_status in ('pending', 'approved', 'rejected', 'error')),
  reviewed_by uuid references public.profiles(id) on delete set null,
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.review_events (
  id uuid primary key default gen_random_uuid(),
  reviewer_id uuid references public.profiles(id) on delete set null,
  entity_table text not null,
  entity_id uuid,
  action text not null check (action in ('created', 'updated', 'approved', 'rejected', 'archived', 'flagged')),
  notes text,
  previous_payload jsonb,
  new_payload jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.data_gaps (
  id uuid primary key default gen_random_uuid(),
  external_key text not null unique,
  institution_id uuid references public.institutions(id) on delete cascade,
  programme_id uuid references public.programmes(id) on delete cascade,
  source_document_id uuid references public.source_documents(id) on delete set null,
  gap_type text not null,
  title text not null,
  description text not null,
  priority text not null default 'medium' check (priority in ('low', 'medium', 'high')),
  status text not null default 'open' check (status in ('open', 'in_progress', 'resolved', 'ignored')),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists public.student_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete cascade,
  full_name text,
  district text,
  school_leaving_year int,
  stream text,
  household_income_band text,
  interests text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.student_profile_subjects (
  student_profile_id uuid not null references public.student_profiles(id) on delete cascade,
  subject_id uuid not null references public.subjects(id) on delete cascade,
  grade text not null,
  grade_points numeric(5,2),
  primary key (student_profile_id, subject_id)
);

create table if not exists public.student_documents (
  id uuid primary key default gen_random_uuid(),
  student_profile_id uuid not null references public.student_profiles(id) on delete cascade,
  document_type text not null,
  storage_path text not null,
  original_file_name text,
  extraction_status text not null default 'pending' check (extraction_status in ('pending', 'processing', 'completed', 'failed')),
  extracted_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.recommendation_runs (
  id uuid primary key default gen_random_uuid(),
  student_profile_id uuid references public.student_profiles(id) on delete cascade,
  run_type text not null default 'rule_based_v1',
  input_snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.recommendation_results (
  id uuid primary key default gen_random_uuid(),
  recommendation_run_id uuid references public.recommendation_runs(id) on delete cascade,
  student_profile_id uuid references public.student_profiles(id) on delete cascade,
  programme_id uuid references public.programmes(id) on delete cascade,
  academic_score numeric(5,2) not null default 0,
  interest_score numeric(5,2) not null default 0,
  affordability_score numeric(5,2) not null default 0,
  scholarship_score numeric(5,2) not null default 0,
  labour_market_score numeric(5,2) not null default 0,
  overall_score numeric(5,2) not null default 0,
  explanation text,
  score_breakdown jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_programmes_institution on public.programmes(institution_id);
create index if not exists idx_programmes_review_status on public.programmes(review_status);
create index if not exists idx_programmes_category on public.programmes(category);
create index if not exists idx_programme_sources_programme on public.programme_sources(programme_id);
create index if not exists idx_requirement_sets_programme on public.programme_requirement_sets(programme_id);
create index if not exists idx_fee_schedules_institution on public.fee_schedules(institution_id);
create index if not exists idx_fee_items_schedule on public.fee_items(fee_schedule_id);
create index if not exists idx_data_gaps_status on public.data_gaps(status);
create index if not exists idx_import_candidates_review_status on public.import_candidates(review_status);
create index if not exists idx_recommendation_results_profile on public.recommendation_results(student_profile_id);

create unique index if not exists idx_requirement_subjects_unique
  on public.programme_requirement_subjects(requirement_set_id, subject_name, coalesce(alternative_group, ''));

create unique index if not exists idx_programme_modules_unique
  on public.programme_modules(programme_id, coalesce(module_code, ''), module_name, coalesce(year_no, 0), coalesce(semester_no, 0));

create unique index if not exists idx_fee_schedules_unique
  on public.fee_schedules(institution_id, title, coalesce(academic_year, ''));

create or replace view public.admin_programme_catalogue as
select
  p.id,
  p.external_key,
  i.name as institution_name,
  i.short_name as institution_short_name,
  f.name as faculty_name,
  p.name as programme_name,
  p.category,
  p.qualification_level,
  p.duration_text,
  p.delivery_mode,
  p.review_status,
  count(distinct ps.source_document_id) as source_count,
  count(distinct prs.id) as requirement_set_count,
  count(distinct fi.id) as fee_item_count,
  count(distinct dg.id) filter (where dg.status = 'open') as open_gap_count
from public.programmes p
join public.institutions i on i.id = p.institution_id
left join public.faculties f on f.id = p.faculty_id
left join public.programme_sources ps on ps.programme_id = p.id
left join public.programme_requirement_sets prs on prs.programme_id = p.id
left join public.fee_items fi on fi.programme_id = p.id
left join public.data_gaps dg on dg.programme_id = p.id
group by p.id, i.name, i.short_name, f.name;

create or replace view public.programme_fee_summary as
select
  i.name as institution_name,
  p.name as programme_name,
  fs.academic_year,
  fi.programme_group,
  fi.item_name,
  fi.item_type,
  fi.amount,
  fi.percent_of_tuition,
  fi.basis,
  fi.student_category,
  fi.attendance_mode
from public.fee_items fi
join public.fee_schedules fs on fs.id = fi.fee_schedule_id
join public.institutions i on i.id = fs.institution_id
left join public.programmes p on p.id = fi.programme_id;

alter table public.profiles enable row level security;
alter table public.student_profiles enable row level security;
alter table public.student_profile_subjects enable row level security;
alter table public.student_documents enable row level security;
alter table public.recommendation_runs enable row level security;
alter table public.recommendation_results enable row level security;

create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);

create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

create policy "student_profiles_owner_all"
  on public.student_profiles for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "student_profile_subjects_owner_all"
  on public.student_profile_subjects for all
  using (
    exists (
      select 1
      from public.student_profiles sp
      where sp.id = student_profile_id
        and sp.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.student_profiles sp
      where sp.id = student_profile_id
        and sp.user_id = auth.uid()
    )
  );

create policy "student_documents_owner_all"
  on public.student_documents for all
  using (
    exists (
      select 1
      from public.student_profiles sp
      where sp.id = student_profile_id
        and sp.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.student_profiles sp
      where sp.id = student_profile_id
        and sp.user_id = auth.uid()
    )
  );

create policy "recommendation_runs_owner_select"
  on public.recommendation_runs for select
  using (
    exists (
      select 1
      from public.student_profiles sp
      where sp.id = student_profile_id
        and sp.user_id = auth.uid()
    )
  );

create policy "recommendation_results_owner_select"
  on public.recommendation_results for select
  using (
    exists (
      select 1
      from public.student_profiles sp
      where sp.id = student_profile_id
        and sp.user_id = auth.uid()
    )
  );
