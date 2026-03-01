# CareerTailor — Backend README

**Stack:** FastAPI · LangGraph · Supabase (Postgres + pgvector) · Gemini 2.5 Flash  
**Runtime:** Python 3.14 · Poetry · Uvicorn  
**Last updated:** Phase 2 + Phase 3 complete

---

## Project Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── interfaces.py          # Abstract contracts: IJobScraper, ICareerAI, IEmbeddingService, AnalysisResult
│   │   └── auth.py                # JWT verification via Supabase JWKS endpoint (ES256)
│   ├── services/
│   │   ├── db.py                  # Supabase client — all DB reads/writes
│   │   ├── scraper.py             # Playwright-based job scraper with smart selectors
│   │   ├── parser.py              # PDF/DOCX/TXT resume text extraction
│   │   ├── llm.py                 # Gemini 2.5 Flash — analysis + structured output
│   │   ├── job_queue.py           # Async job lifecycle (create/update/get)
│   │   ├── embedding_factory.py   # Reads EMBEDDING_PROVIDER env var, returns correct impl
│   │   ├── embedding_gemini.py    # Gemini embedding-001, 768 dims
│   │   ├── embedding_openai.py    # text-embedding-3-small, 1536 dims
│   │   ├── embedding_voyage.py    # voyage-3, 1024 dims
│   │   └── embedding_cohere.py    # embed-v4.0, 1024 dims
│   ├── orchestrator.py            # LangGraph pipeline: scraper → retriever → analyst
│   ├── dependencies.py            # FastAPI dependency injection for orchestrator
│   └── main.py                    # FastAPI app — all endpoints, middleware, rate limiter
├── pyproject.toml
└── .env
```

---

## Environment Variables

```bash
# Supabase
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_KEY=your-publishable-anon-key        # used by frontend-scoped operations
SUPABASE_SERVICE_KEY=your-service-role-key    # used for all backend writes (bypasses RLS)

# AI Providers
GEMINI_API_KEY=your-gemini-key

# Embedding Provider (gemini | openai | voyage | cohere)
EMBEDDING_PROVIDER=gemini
```

---

## API Endpoints

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/` | Public | Health check |
| POST | `/api/ingest` | JWT | Ingest master resume into pgvector knowledge base |
| GET | `/api/ingest/status` | JWT | Check if user has a master resume ingested |
| POST | `/api/analyze` | JWT + Rate limit | Queue a job analysis (returns job_id instantly) |
| GET | `/api/jobs/{job_id}` | JWT | Poll job status + result |
| GET | `/api/history` | JWT | Get 10 most recent jobs for the user |

---

## Authentication

Uses Supabase JWT Signing Keys (ES256 — asymmetric, no shared secret).

**Flow:**
1. Frontend gets JWT from Supabase Auth after login
2. Every request sends `Authorization: Bearer <token>`
3. `auth.py` fetches the JWKS public key from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`
4. JWKS is cached in memory at startup — no DB call per request
5. `verify_token()` dependency returns `(user_id, raw_token)` tuple
6. `user_id` scopes all DB queries; `raw_token` is passed to Supabase client for RLS on INSERT

**Key design decision:** All backend reads/writes use the service role key directly — RLS is enforced at application level via `.eq("user_id", user_id)` filters on every query. The `raw_token` is only needed for `analysis_jobs` INSERT (where RLS requires `auth.uid() = user_id`).

---

## LangGraph Pipeline

```
POST /api/analyze
    │
    ▼
BackgroundTask → _run_analysis_job()
    │
    ├── Node 1: Scraper
    │     Playwright scrapes job URL
    │     Smart selectors for Workday, Greenhouse, LinkedIn, etc.
    │     Falls back to full page text clean if no selector matches
    │
    ├── Node 2: Retriever  ← skipped if use_rag=False (custom resume uploaded)
    │     Embeds job_text as query vector
    │     Cosine similarity search against user's resume_chunks (pgvector)
    │     Returns top 8 chunks (threshold=0.4)
    │     Falls back gracefully — never breaks the pipeline
    │
    └── Node 3: Analyst
          If RAG chunks found    → uses chunks as resume context
          If custom file uploaded → uses parsed file text directly
          If neither             → uses raw resume_text fallback
          Calls Gemini 2.5 Flash → returns AnalysisResult
```

**`use_rag` flag logic (in `main.py`):**
```python
use_rag = not bool(resume and resume.filename)
# True  → no file uploaded, use master resume RAG chunks
# False → user uploaded a file, skip RAG and use that text directly
```

---

## RAG Architecture (Phase 3)

**Ingestion flow:**
1. Upload PDF/DOCX/TXT → parse to text
2. SHA-256 hash → skip if already embedded (dedup)
3. Chunk text (500 chars, 50 char overlap)
4. Embed chunks via configured provider
5. Delete old chunks for user → upsert new chunks to `resume_chunks` table

**Retrieval flow:**
1. Embed job description text (first 3000 chars) as query vector
2. Call `match_resume_chunks()` RPC (pgvector cosine similarity)
3. Return top 8 chunks above 0.4 threshold
4. Inject into LLM prompt as grounded context

**Provider switching:**
Change `EMBEDDING_PROVIDER` in `.env`. Restart server.  
⚠️ If the new provider has different dimensions, you must:
1. Update SQL schema `vector(N)` to match new dimensions
2. Re-ingest all master resumes — old embeddings are incompatible

| Provider | Model | Dimensions |
|----------|-------|-----------|
| `gemini` | gemini-embedding-001 | 768 |
| `openai` | text-embedding-3-small | 1536 |
| `voyage` | voyage-3 | 1024 |
| `cohere` | embed-v4.0 | 1024 |

---

## Supabase Schema

### `resume_chunks`
```sql
id           uuid  (PK)
user_id      uuid
chunk_index  int
chunk_text   text
embedding    vector(768)    -- dimensions must match EMBEDDING_PROVIDER
source_hash  text           -- SHA-256 of the uploaded file (dedup)
created_at   timestamptz
```
Index: IVFFlat on `embedding` with cosine distance (lists=100)  
RPC: `match_resume_chunks(query_embedding, match_threshold, match_count, user_id)`

### `analysis_jobs`
```sql
id            uuid  (PK, default uuid_generate_v4())
user_id       uuid
job_url       text
status        text           -- pending | processing | done | failed
result        jsonb          -- AnalysisResult when done
error_message text           -- set on failure
created_at    timestamptz
updated_at    timestamptz    -- auto-updated via trigger
```
RLS: Users can read/insert own jobs. Service role can update.  
Realtime: Enabled via `supabase_realtime` publication.

### `job_scrapes`
```sql
url       text  (PK)
raw_text  text
```

### `analysis_sessions`
```sql
job_url           text
match_score       int
keywords          text[]
ai_summary        text
created_at        timestamptz
```

---

## Async Job Queue

```
POST /api/analyze
    Returns: { job_id, status: "pending" }   ← immediate response

BackgroundTask runs pipeline asynchronously
    pending → processing → done | failed

GET /api/jobs/{job_id}
    Returns: { status, result, error_message }

Frontend subscribes via Supabase Realtime
    Receives UPDATE event the moment status changes to "done"
    Fallback: polls GET /api/jobs/{id} every 3s if Realtime misses it
```

---

## Rate Limiting

`slowapi` middleware — 5 analyses per day per user.  
Rate limit key extracted from JWT `sub` claim (without verification — bucket key only).  
Returns HTTP 429 with user-friendly message when limit exceeded.

---

## SQL Files (run in order)

```
phase3_sql/01_resume_chunks.sql    ← pgvector extension + resume_chunks table + RPC
phase2_sql/02_jobs_table.sql       ← analysis_jobs table + RLS + updated_at trigger
phase2_sql/03_enable_realtime.sql  ← adds analysis_jobs to supabase_realtime publication
```

---

## ✅ Completed

### Phase 3 — RAG
- [x] `resume_chunks` table with pgvector + IVFFlat index
- [x] `match_resume_chunks()` RPC for cosine similarity search
- [x] Provider-swappable embedding architecture (`IEmbeddingService` interface)
- [x] Gemini, OpenAI, Voyage, Cohere embedding implementations
- [x] `POST /api/ingest` — parse, hash, chunk, embed, upsert
- [x] `GET /api/ingest/status` — check if user has master resume
- [x] SHA-256 dedup — skip re-embedding identical files
- [x] RAG retrieval node in LangGraph pipeline
- [x] `use_rag` flag — custom file upload bypasses RAG and uses uploaded text directly
- [x] Graceful RAG fallback — pipeline never breaks if chunks unavailable

### Phase 2 — Auth + Async Queue
- [x] Supabase JWKS-based JWT verification (ES256, no shared secret)
- [x] JWKS cached in memory at startup
- [x] `verify_token()` dependency returns `(user_id, raw_token)`
- [x] All endpoints protected with JWT auth
- [x] `analysis_jobs` table with RLS + auto-updated_at trigger
- [x] Async job queue — POST returns job_id instantly
- [x] LangGraph runs in FastAPI `BackgroundTasks`
- [x] `GET /api/jobs/{job_id}` polling endpoint
- [x] Supabase Realtime enabled on `analysis_jobs`
- [x] `slowapi` rate limiting — 5 analyses/day per user (keyed on JWT sub)
- [x] Service role key for all backend writes — eliminates RLS conflicts
- [x] CORS tightened to localhost:5173 and localhost:3000

---

## 🔴 Pending

### Phase 4 — Scraper Refactor
- [ ] `httpx` first attempt for simple job sites (10x faster, no browser)
- [ ] Playwright as fallback for JS-heavy sites (Workday, Greenhouse)
- [ ] Retry logic with exponential backoff
- [ ] Better error messages when scraping fails (e.g. login-gated jobs)
- [ ] Detect and handle LinkedIn "sign in to view" walls

### Phase 5 — Resume Generation
- [ ] Generate tailored `.docx` resume from master resume + job analysis
- [ ] Keyword injection — weave missing keywords into existing bullet points naturally
- [ ] Section reordering — surface most relevant experience for the role
- [ ] Download endpoint `GET /api/resume/{job_id}` returns generated `.docx`
- [ ] Preserve original formatting from master resume template

---

## 🅿️ Parking Lot

### Multi-Resume Profiles
User can have up to 5 named resume profiles (e.g. "Senior SWE", "Engineering Manager").  
- Most recently used = default  
- Switch profiles from a dropdown before analysis  
- Upload a one-off resume for a single analysis without saving  
- Manage profiles in a dedicated settings page  
- On hitting 5-profile limit: prompt user which to replace  
- **Build after Phase 5** — real users will tell us if they need it