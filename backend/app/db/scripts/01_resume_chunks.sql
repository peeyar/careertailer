-- ============================================================
-- CareerTailor Phase 3: RAG Schema
-- Run this in Supabase SQL Editor
-- ============================================================

-- Step 1: Enable pgvector extension (may already be enabled)
create extension if not exists vector with schema extensions;

-- Step 2: Create the resume_chunks table
create table public.resume_chunks (
  id            uuid not null default extensions.uuid_generate_v4(),
  user_id       text not null,                        -- ties chunks to a user (session-based for now)
  chunk_index   integer not null,                     -- order of chunk within the resume
  chunk_text    text not null,                        -- the raw text of this chunk
  embedding     vector(768) not null,                 -- Gemini text-embedding-004 outputs 768 dims
  source_hash   text not null,                        -- SHA-256 of original file (for cache/dedup)
  created_at    timestamp with time zone default timezone('utc', now()),

  constraint resume_chunks_pkey primary key (id)
);

-- Step 3: Index for fast similarity search (cosine distance)
create index on public.resume_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- Step 4: Index for fast user lookups
create index on public.resume_chunks (user_id);

-- Step 5: RLS - users only see their own chunks
alter table public.resume_chunks enable row level security;

-- NOTE: For now (no Auth yet) RLS is defined but permissive.
-- Tighten this in Phase 2 when Supabase Auth is added.
create policy "Allow all for now"
  on public.resume_chunks
  for all
  using (true)
  with check (true);

-- Step 6: pgvector similarity search function
-- Call this from Python: supabase.rpc("match_resume_chunks", {...})
create or replace function match_resume_chunks(
  query_embedding  vector(768),
  match_user_id    text,
  match_threshold  float default 0.5,
  match_count      int   default 5
)
returns table (
  id          uuid,
  chunk_text  text,
  similarity  float
)
language sql stable
as $$
  select
    id,
    chunk_text,
    1 - (embedding <=> query_embedding) as similarity
  from public.resume_chunks
  where user_id = match_user_id
    and 1 - (embedding <=> query_embedding) > match_threshold
  order by embedding <=> query_embedding
  limit match_count;
$$;
