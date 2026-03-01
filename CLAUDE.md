# CareerTailor

AI-powered resume tailoring tool. Analyzes job descriptions against a user's master resume using RAG (pgvector), then generates tailored resumes.

## Monorepo Structure

```
careertailor/
├── backend/          # FastAPI + LangGraph + Supabase
├── careertailer-ui/  # React + Vite + Tailwind
├── BACKEND_README.md # Full backend architecture + phase status
└── FRONTEND_README.md # Full frontend architecture + phase status
```

Read BACKEND_README.md and FRONTEND_README.md before making any architectural decisions. They contain completed/pending/parked feature lists and key design decisions already made.

## Running the Project

```bash
# Backend
cd backend
poetry run uvicorn app.main:app --reload --port 8000

# Frontend
cd careertailer-ui
npm run dev        # runs on port 5173
```

## Key Rules

- Never commit .env files
- Backend writes always use SUPABASE_SERVICE_KEY (bypasses RLS)
- Backend reads use application-level .eq("user_id", user_id) filters — not RLS
- The JWT token from verify_token() must be passed to Supabase client for analysis_jobs INSERT
- use_rag=False when user uploads a custom resume — RAG must be skipped entirely
- Switching embedding providers requires re-running SQL schema + re-ingesting all resumes
