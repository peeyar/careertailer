-- ============================================================
-- CareerTailor Phase 2: Async Job Queue Schema
-- Run this in Supabase SQL Editor
-- ============================================================

create table public.analysis_jobs (
  id            uuid not null default extensions.uuid_generate_v4(),
  user_id       uuid not null,                        -- references auth.users
  job_url       text not null,
  status        text not null default 'pending',      -- pending | processing | done | failed
  result        jsonb null,                           -- AnalysisResult stored as JSON when done
  error_message text null,                            -- error detail if failed
  created_at    timestamp with time zone default timezone('utc', now()),
  updated_at    timestamp with time zone default timezone('utc', now()),

  constraint analysis_jobs_pkey primary key (id),
  constraint analysis_jobs_status_check
    check (status in ('pending', 'processing', 'done', 'failed'))
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Fast lookup by user (history queries)
create index on public.analysis_jobs (user_id, created_at desc);

-- Fast polling by job ID + user (status checks)
create index on public.analysis_jobs (id, user_id);

-- ── Auto-update updated_at ────────────────────────────────────────────────────

create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create trigger analysis_jobs_updated_at
  before update on public.analysis_jobs
  for each row execute function update_updated_at();

-- ── Row Level Security ────────────────────────────────────────────────────────

alter table public.analysis_jobs enable row level security;

-- Users can only see their own jobs
create policy "Users can read own jobs"
  on public.analysis_jobs for select
  using (auth.uid() = user_id);

-- Users can create jobs for themselves only
create policy "Users can create own jobs"
  on public.analysis_jobs for insert
  with check (auth.uid() = user_id);

-- Only the backend service role can update job status
-- (the background worker uses the service role key)
create policy "Service role can update jobs"
  on public.analysis_jobs for update
  using (true);

-- ── Auto-purge old jobs (keep last 30 days) ───────────────────────────────────
-- Requires pg_cron extension (already enabled in your project)

select cron.schedule(
  'purge-old-jobs',
  '0 2 * * *',   -- runs at 2am UTC daily
  $$
    delete from public.analysis_jobs
    where created_at < now() - interval '30 days';
  $$
);
