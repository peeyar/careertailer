# Backend

FastAPI + LangGraph + Supabase (Postgres + pgvector) + Gemini 2.5 Flash  
Python 3.14, Poetry, Uvicorn

## Commands

```bash
poetry run uvicorn app.main:app --reload --port 8000
poetry add <package>
poetry run python -c "from app.main import app; print('ok')"  # sanity check
```

## Structure

```
app/
├── core/
│   ├── interfaces.py     # IJobScraper, ICareerAI, IEmbeddingService, AnalysisResult
│   └── auth.py           # ES256 JWT via JWKS — verify_token() returns (user_id, token)
├── services/
│   ├── db.py             # All Supabase reads/writes — service_client for writes
│   ├── scraper.py        # httpx first → Playwright fallback
│   ├── parser.py         # PDF/DOCX/TXT → text
│   ├── llm.py            # Gemini 2.5 Flash — CareerAI class, see pattern below
│   ├── resume_writer.py  # Phase 5 — ResumeWriter class, docx generation
│   ├── job_queue.py      # analysis_jobs lifecycle
│   ├── embedding_factory.py  # reads EMBEDDING_PROVIDER env var
│   └── embedding_*.py    # gemini (768d), openai (1536d), voyage (1024d), cohere (1024d)
├── orchestrator.py       # LangGraph: scraper → retriever → analyst → writer (Phase 5)
├── dependencies.py       # FastAPI DI for orchestrator
└── main.py               # All endpoints + middleware
```

## LangGraph Pipeline

```
scraper → retriever → analyst → writer (Phase 5)
```
- `use_rag=False` in GraphState → retriever node skipped, uploaded resume_text used directly
- Never let any node failure break the pipeline — always catch exceptions per node
- `writer` node only runs if `analyst` produced a valid result

### Two-context pattern (retriever node)
The retriever fetches **two separate contexts** in one pass:
- `retrieved_chunks` — top-8 similarity matches → used by **analyst** (focused, high-signal)
- `full_resume_text` — ALL chunks joined in chunk_index order → used by **writer** (complete resume)

This ensures the analyst scores against the most relevant sections while the writer sees the entire resume and can reorder/reword everything. On the upload path (`use_rag=False`), both are empty and `resume_text` (the uploaded file) is used for both.

## llm.py Pattern

`CareerAI` uses `google-genai` SDK, `gemini-2.5-flash`, `response_mime_type="application/json"`, `temperature=0.0`.  
Always returns `AnalysisResult` — never raises, returns error result on failure.  
Prompt structure: system role → CANDIDATE EXPERIENCE (12000 chars) → JOB DESCRIPTION (6000 chars) → output schema.

**Do not change `analyze_match`.** Phase 5 adds a new method `generate_resume` to `CareerAI` following the same pattern.

## Phase 5 — Resume Generation Spec

### Goal
After analysis completes, generate a tailored `.docx` resume the user can download.
Uses the master resume as base, injects missing keywords naturally, reorders sections.

### New method on CareerAI: `generate_resume`

```python
async def generate_resume(
    self,
    resume_text: str,        # full_resume_text (all chunks joined) OR uploaded file text
    job_text: str,           # scraped job description
    analysis: AnalysisResult # output from analyze_match
) -> str:                    # returns tailored resume as plain text (writer converts to docx)
```

Prompt must instruct Gemini to:
1. Rewrite the resume tailored to the job — keep all real experience, never invent anything
2. Naturally weave in `analysis.missing_keywords` where they genuinely fit
3. Move the most relevant experience sections to the top
4. Return plain text with clear section headers (SUMMARY, EXPERIENCE, SKILLS, EDUCATION)
5. Keep the same factual content — only reorder, reword, and add keywords contextually

### New service: `resume_writer.py`

Use `python-docx` library (install: `poetry add python-docx`).  
Convert the plain text from Gemini into a formatted `.docx`:
- Bold section headers
- Bullet points for experience items (lines starting with - or bullet)
- Clean font: Calibri 11pt body, 14pt headers
- Save to `/tmp/{job_id}.docx`, return the file path

### New LangGraph node: `_write_resume_node`

Added to `orchestrator.py` after `_analyze_match_node`.  
Reads `analysis` and `retrieved_chunks` (or `resume_text`) from state.  
Calls `CareerAI.generate_resume()` then `ResumeWriter.create_docx()`.  
Stores `docx_path` in GraphState.  
Non-fatal — if it fails, log the error but do not fail the job.

### GraphState additions

```python
docx_path: Optional[str]   # path to generated .docx, None if generation failed
```

### New endpoint

```
GET /api/resume/{job_id}
```
- JWT protected
- Reads `docx_path` from `analysis_jobs.result` jsonb column
- Returns FileResponse with media_type for .docx
- Returns 404 if job not done or docx_path is None
- Returns 425 if job is still processing

### job_queue changes

Add `docx_path` to the result payload in `update_status` when status=done.

### SQL — no changes needed

`docx_path` stored inside existing `result` jsonb column. No migration.

## Endpoints (current + Phase 5)

```
GET  /                        public health check
POST /api/ingest              JWT — ingest master resume to pgvector
GET  /api/ingest/status       JWT — has user ingested a master resume?
POST /api/analyze             JWT + rate limit (5/day) — queues job, returns job_id instantly
GET  /api/jobs/{job_id}       JWT — poll job status + result
GET  /api/history             JWT — last 10 jobs for user
GET  /api/resume/{job_id}     JWT — download tailored .docx (Phase 5)
```

## Supabase Tables

- `resume_chunks` — vector(768), IVFFlat index, match_resume_chunks() RPC
- `analysis_jobs` — pending|processing|done|failed, Realtime enabled
- `job_scrapes` — url + raw_text
- `analysis_sessions` — legacy analysis storage

## .env Required

```
SUPABASE_URL
SUPABASE_KEY          # publishable/anon key
SUPABASE_SERVICE_KEY  # service role — backend writes only, never expose to frontend
GEMINI_API_KEY
EMBEDDING_PROVIDER    # gemini | openai | voyage | cohere
```

## Key Rules

- Backend writes always use service_client (bypasses RLS)
- Backend reads use .eq("user_id", user_id) application-level filter
- verify_token() returns (user_id, token) — both needed, token for analysis_jobs INSERT
- Never raise from a LangGraph node — catch and return error state
- Never invent resume content — Gemini must only reword/reorder real experience