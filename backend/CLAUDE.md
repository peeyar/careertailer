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
│   ├── llm.py            # Gemini 2.5 Flash analysis
│   ├── job_queue.py      # analysis_jobs lifecycle
│   ├── embedding_factory.py  # reads EMBEDDING_PROVIDER env var
│   └── embedding_*.py    # gemini (768d), openai (1536d), voyage (1024d), cohere (1024d)
├── orchestrator.py       # LangGraph: scraper → retriever → analyst
├── dependencies.py       # FastAPI DI for orchestrator
└── main.py               # All endpoints + middleware
```

## LangGraph Pipeline

scraper → retriever → analyst  
`use_rag=False` in GraphState → retriever node is skipped, uploaded resume_text used directly  
Never let RAG failure break the pipeline — retriever always catches exceptions

## Endpoints

```
GET  /                        public health check
POST /api/ingest              JWT — ingest master resume to pgvector
GET  /api/ingest/status       JWT — has user ingested a master resume?
POST /api/analyze             JWT + rate limit (5/day) — queues job, returns job_id instantly
GET  /api/jobs/{job_id}       JWT — poll job status + result
GET  /api/history             JWT — last 10 jobs for user
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

## What's Next

Phase 5 — `.docx` resume generation  
See BACKEND_README.md for full pending list and parking lot items
