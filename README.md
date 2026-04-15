# CareerTailor

AI-powered resume tailoring tool that uses RAG to match your resume against job descriptions and generate tailored resumes.

![Architecture](https://img.shields.io/badge/Architecture-RAG%20Pipeline-blue)
![Backend](https://img.shields.io/badge/Backend-FastAPI%20%2B%20LangGraph-green)
![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-purple)
![Database](https://img.shields.io/badge/Database-Supabase%20%2B%20pgvector-orange)

## What It Does

1. **Ingest your master resume** into a personal vector store
2. **Paste any job URL** — the system scrapes the job description
3. **Get a match analysis** — score (0-100), missing keywords, matching keywords, reasoning
4. **Download a tailored resume** — DOCX/PDF customized for that specific job
5. **Generate a cover letter** — on-demand, cached for instant retrieval

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend                                  │
│              React + Vite + Tailwind (port 5173)                │
│                   Supabase JS + Realtime                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Axios + JWT
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend                                   │
│                  FastAPI + LangGraph (port 8000)                │
│                                                                  │
│  ┌──────────┐   ┌───────────┐   ┌─────────┐   ┌────────┐       │
│  │ Scraper  │ → │ Retriever │ → │ Analyst │ → │ Writer │       │
│  └──────────┘   └───────────┘   └─────────┘   └────────┘       │
│                                                                  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Supabase                                    │
│   Postgres + pgvector │ Realtime │ Storage │ Auth (JWKS)        │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Gemini Models                                 │
│         Analysis + Resume Writing + Cover Letter                 │
│                    + Embeddings                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

### Frontend
- **React 18** + TypeScript
- **Vite** for build tooling
- **Tailwind CSS** for styling
- **Supabase JS** for auth + realtime subscriptions
- **Axios** for API calls

### Backend
- **FastAPI** for REST API
- **LangGraph** for pipeline orchestration
- **Supabase Python** for database operations
- **httpx + BeautifulSoup** for web scraping (Playwright fallback for JS-heavy sites)
- **python-docx** for DOCX generation
- **LibreOffice/fpdf2** for PDF conversion

### Database & Storage
- **Supabase Postgres** with **pgvector** extension
- **Supabase Storage** for generated resume files
- **Supabase Auth** with JWKS JWT verification
- **Supabase Realtime** for job status updates

### AI/ML
- **Gemini 2.5 Flash** — analysis, resume generation, cover letter
- **Gemini Embedding 001** — 768-dim embeddings for RAG
- Optional: OpenAI, Voyage AI, Cohere embedding providers

### Testing & Evaluation
- **pytest** + pytest-asyncio
- **DeepEval** with **GEval** for LLM-as-Judge evaluation
- **Gemini 2.5 Pro** as the judge model (temperature=0)

## Project Structure

```
careertailor/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI routes + background worker
│   │   ├── orchestrator.py      # LangGraph pipeline
│   │   ├── core/
│   │   │   ├── auth.py          # Supabase JWT verification
│   │   │   └── interfaces.py    # AnalysisResult + service interfaces
│   │   ├── services/
│   │   │   ├── llm.py           # Gemini generation
│   │   │   ├── scraper.py       # Two-tier web scraping
│   │   │   ├── parser.py        # PDF/DOCX text extraction
│   │   │   ├── db.py            # Supabase operations
│   │   │   ├── job_queue.py     # Async job lifecycle
│   │   │   ├── resume_writer.py # DOCX/PDF generation
│   │   │   └── embedding_*.py   # Embedding providers
│   │   └── db/scripts/          # SQL migrations
│   └── tests/
│       ├── test_orchestrator.py # Unit tests with mocks
│       ├── test_llm_logic.py    # LLM-as-Judge evals
│       └── deepeval_setup.py    # Judge model config
│
└── careertailor-ui/
    └── src/
        ├── App.tsx              # Main app + state machine
        ├── AuthPage.tsx         # Login/signup
        ├── components/          # UI components
        └── lib/supabase.ts      # Supabase client
```

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Supabase account
- Google AI API key (Gemini)

### Backend

```bash
cd backend
cp .env.example .env  # Fill in your keys

# Install dependencies
poetry install

# Run database migrations in Supabase SQL editor
# (see backend/app/db/scripts/)

# Start the server
poetry run uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd careertailor-ui
cp .env.example .env  # Fill in your keys

npm install
npm run dev  # Starts on port 5173
```

### Environment Variables

**Backend (.env)**
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key
GEMINI_API_KEY=your_gemini_key
EMBEDDING_PROVIDER=gemini  # or openai, voyage, cohere
```

**Frontend (.env)**
```
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_anon_key
VITE_API_BASE=http://localhost:8000
```

## Key Features

### RAG Pipeline
- Chunks resume into overlapping segments (500 tokens, 50 overlap)
- Embeds chunks with Gemini (768 dimensions)
- Retrieves top-8 relevant chunks for analysis
- Uses full resume text for tailored resume generation

### Two-Tier Scraping
- **Tier 1:** httpx + BeautifulSoup with realistic headers
- **Tier 2:** Playwright (Chromium) fallback for Workday, Greenhouse, LinkedIn, Lever

### Async Job Queue
- Jobs return immediately with `job_id`
- Background processing with status updates
- Realtime subscription for instant UI updates
- Polling fallback for reliability

### LLM-as-Judge Testing
- Uses DeepEval's GEval framework
- Gemini 2.5 Pro as judge (temperature=0)
- Evaluates output quality + score thresholds
- Runs on every test suite execution

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest` | Upload and vectorize master resume |
| GET | `/api/ingest/status` | Check if user has ingested resume |
| POST | `/api/analyze` | Start job analysis (async, rate-limited 5/day) |
| GET | `/api/jobs/{job_id}` | Poll job status/result |
| GET | `/api/history` | Get last 10 jobs |
| GET | `/api/resume/{job_id}` | Download tailored DOCX |
| GET | `/api/resume/{job_id}/pdf` | Download tailored PDF |
| POST | `/api/cover-letter/{job_id}` | Generate cover letter (cached) |

## Database Schema

### resume_chunks
Stores vectorized resume chunks per user with pgvector embeddings.

### analysis_jobs
Async job queue with status lifecycle: `pending → processing → done/failed`

### job_scrapes
Cached job descriptions by URL to avoid re-scraping.

### resume_styles
Extracted font/size metadata from original resume for formatting consistency.

## Testing

```bash
cd backend

# Run unit tests
poetry run pytest tests/test_orchestrator.py -v

# Run LLM-as-Judge evaluations
poetry run pytest tests/test_llm_logic.py -v
```

## Rate Limits

- **5 job analyses per day** per user (SlowAPI)
- Returns 429 with message: "Daily limit reached. You can analyze 5 jobs per day."

## Contributing

Issues and PRs welcome. Please ensure tests pass before submitting.

## License

MIT

## Author

**Rajesh Kartha**
- Newsletter: [rajeshkartha.substack.com](https://rajeshkartha.substack.com)
- LinkedIn: [Rajesh Kartha](https://linkedin.com/in/rajeshkartha)
