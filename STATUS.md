# CareerTailor — Project Status
*Last updated: 2026-03-01*

---

## Architecture Overview

```
React + Vite + Tailwind (port 5173)
        ↓ Axios + Supabase JS
FastAPI + LangGraph (port 8000)
        ↓
Supabase Postgres + pgvector + Realtime
        ↓
Gemini 2.5 Flash (analysis, resume writing, cover letter)
```

**LangGraph Pipeline:**
```
scraper → retriever (RAG) → analyst → writer
```

---

## Completed

### Phase 1 — Auth
- [x] Supabase email/password auth (login + signup)
- [x] ES256 JWT verification via JWKS (`verify_token`)
- [x] Axios interceptor auto-attaches JWT to every request (registered once via ref)
- [x] Auth gate in `App.tsx` — unauthenticated users see `AuthPage`

### Phase 2 — Master Resume Ingestion
- [x] PDF / DOCX / TXT parsing (`ResumeParser`)
- [x] Text chunking + embedding via pluggable provider (Gemini 768d default)
- [x] pgvector storage in `resume_chunks` table with IVFFlat index
- [x] SHA-256 file hash deduplication — re-uploads skipped instantly
- [x] Resume style extraction (`style_extractor.py`) — font, size, spacing stored per user
- [x] `GET /api/ingest/status` — frontend checks on login to show/hide upload zone

### Phase 3 — Job Analysis (LangGraph)
- [x] Job URL scraping (`httpx` first, Playwright fallback)
- [x] Closed job detection (9 signal phrases checked before AI call)
- [x] RAG retrieval — top-8 similarity chunks for analyst, all chunks for writer
- [x] Gemini 2.5 Flash analysis → `match_score`, `missing_keywords`, `matching_keywords`, `summary_reasoning`
- [x] Async job queue (`analysis_jobs` table) — returns `job_id` instantly
- [x] Supabase Realtime subscription (primary) + 3s polling fallback

### Phase 4 — UX + History
- [x] History sidebar — last 10 analyses, click to reload result
- [x] Score badge color coding (green ≥ 70, yellow ≥ 40, red < 40)
- [x] Rate limiting — 5 analyses per user per day (JWT-keyed)
- [x] Live job status display (queued → processing → done/failed)
- [x] "Master resume active" badge — no re-upload needed after ingestion
- [x] "Use different resume" override option in Step 2

### Phase 5 — Resume Generation + Download
- [x] `generate_resume` method on `CareerAI` — Gemini rewrites resume, returns plain text + changes summary
- [x] `ResumeWriter.create_docx()` — converts plain text to formatted `.docx` (Calibri, bold headers, bullets)
- [x] Resume style applied to generated `.docx` (font, spacing from original upload)
- [x] `writer` LangGraph node — non-fatal, logs failure without breaking the job
- [x] `GET /api/resume/{job_id}` — JWT-protected blob download endpoint
- [x] Frontend download button — axios blob pattern, triggers browser save
- [x] "What Was Tailored" summary — up to 8 bullet changes shown in results

### Phase 6 — Cover Letter (On-Demand)
- [x] `generate_cover_letter` method on `CareerAI` — short punchy format, under 120 words
- [x] `POST /api/cover-letter/{job_id}` — generates on-demand, not during analysis
- [x] Cover letter cached in `result` JSONB via `patch_cover_letter` — subsequent requests instant
- [x] `CoverLetterCard` component — displays cover letter with one-click copy
- [x] "Generate Cover Letter" button shown after analysis completes (optional, not blocking)
- [x] Error state shown if generation fails (Apply button still usable)

---

## Pending

### Bug Fixes
- [x] **`HistoryResult` type missing `cover_letter`** — added `cover_letter?: string` to `HistorySidebar.tsx` interface.
- [x] **Cover letter on upload path** — when chunks are empty (upload-path job), cover letter now falls back to `matching_keywords` + `summary_reasoning` from the stored analysis result as resume context.

### Next Up — Phase 7: Polish + Production Readiness
- [ ] **Mobile responsive layout** — sidebar collapses on small screens, main content scrolls correctly
- [ ] **Empty state for new users** — guide through Step 1 → Step 2 flow more explicitly
- [ ] **Loading skeleton** for history sidebar (instead of plain "Loading history..." text)
- [ ] **Commit untracked files** — `resume_writer.py`, `style_extractor.py`, `CoverLetterCard.tsx` not yet committed

### Phase 8 — Deployment
- [ ] Dockerize backend (FastAPI + Playwright)
- [ ] Deploy backend to Railway / Render / Fly.io
- [ ] Deploy frontend to Vercel / Netlify
- [ ] Set `VITE_API_BASE` env var — replace hardcoded `http://127.0.0.1:8000`
- [ ] Set production Supabase CORS origins
- [ ] Set up `.env.production` for both frontend and backend

### Parking Lot (Future Ideas)
- [ ] LinkedIn job URL auto-scrape improvements (LinkedIn blocks bots aggressively)
- [ ] Multi-resume support — store multiple master resumes per user, pick at analysis time
- [ ] Job tracking dashboard — status column (applied, interviewing, rejected, offer)
- [ ] Email notification when async job completes
- [ ] Cover letter DOCX download (currently copy-paste only)
- [ ] Analytics — track which keywords are most commonly missing across users

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/main.py` | All FastAPI endpoints |
| `backend/app/orchestrator.py` | LangGraph pipeline |
| `backend/app/services/llm.py` | Gemini AI methods |
| `backend/app/services/db.py` | All Supabase operations |
| `backend/app/services/job_queue.py` | Job lifecycle management |
| `backend/app/services/resume_writer.py` | DOCX generation |
| `backend/app/services/style_extractor.py` | Resume style parsing |
| `careertailer-ui/src/App.tsx` | Main frontend — all state + handlers |
| `careertailer-ui/src/components/HistorySidebar.tsx` | History panel |
| `careertailer-ui/src/components/CoverLetterCard.tsx` | Cover letter display |
| `careertailer-ui/src/lib/supabase.ts` | Singleton Supabase client |
