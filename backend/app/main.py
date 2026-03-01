from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse
from app.dependencies import get_orchestrator
from app.orchestrator import CareerOrchestrator
from app.services.parser import ResumeParser
from app.services.db import DatabaseService
from app.services.job_queue import JobQueueService
from app.services.embedding_factory import get_embedding_service, hash_file
from app.core.interfaces import AnalysisResult
from app.core.auth import verify_token
from jose import jwt as jose_jwt
from typing import Optional


# ── Rate Limiter ──────────────────────────────────────────────────────────────

def _rate_limit_key(request: Request) -> str:
    """
    Read user identity directly from JWT for rate limiting.
    Decodes without verification — only needs 'sub' as a bucket key.
    Falls back to IP if token is missing or malformed.
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = jose_jwt.get_unverified_claims(token)
            return payload.get("sub", get_remote_address(request))
    except Exception:
        pass
    return get_remote_address(request)


limiter = Limiter(key_func=get_remote_address)

# ── App Init ──────────────────────────────────────────────────────────────────
app = FastAPI(title="CareerTailor Enterprise API")

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"detail": "Daily limit reached. You can analyze 5 jobs per day."},
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)

# ── Shared Services ───────────────────────────────────────────────────────────
db            = DatabaseService()
job_queue     = JobQueueService()
embedding_svc = get_embedding_service()


# ── Health Check (public) ─────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "CareerTailor Enterprise API is online 🚀"}


# ── History (protected) ───────────────────────────────────────────────────────
@app.get("/api/history")
async def get_analysis_history(auth: tuple = Depends(verify_token)):
    user_id, token = auth
    try:
        jobs = await job_queue.get_user_jobs(user_id, token)
        return {"status": "success", "data": jobs}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Job Status Polling (protected) ────────────────────────────────────────────
@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, auth: tuple = Depends(verify_token)):
    user_id, token = auth
    job = await job_queue.get_job(job_id, user_id, token)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── Master Resume Ingestion (protected) ───────────────────────────────────────
@app.post("/api/ingest")
async def ingest_master_resume(
    resume: UploadFile = File(...),
    auth:   tuple      = Depends(verify_token),
):
    user_id, token = auth

    filename = resume.filename.lower()
    if not filename.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(status_code=400, detail="Invalid file type.")

    try:
        content = await resume.read()
        if filename.endswith(".pdf"):
            resume_text = ResumeParser.parse_pdf(content)
        elif filename.endswith(".docx"):
            resume_text = ResumeParser.parse_docx(content)
        else:
            resume_text = content.decode("utf-8")

        if len(resume_text) < 50:
            raise HTTPException(status_code=400, detail="Resume text too short.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse failed: {str(e)}")

    file_hash = hash_file(content)
    if await db.check_resume_exists(user_id, file_hash):
        print(f"⚡ Ingest: Already embedded for user {user_id}. Skipping.")
        return {"status": "skipped", "message": "Resume already ingested.", "chunks": 0}

    chunks = embedding_svc.chunk_text(resume_text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No text chunks extracted.")

    try:
        embeddings = await embedding_svc.embed_chunks(chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

    try:
        await db.save_resume_chunks(user_id, file_hash, chunks, embeddings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB save failed: {str(e)}")

    return {"status": "success", "message": "Master resume ingested.", "chunks": len(chunks)}


# ── Ingest Status (protected) ────────────────────────────────────────────────
@app.get("/api/ingest/status")
async def get_ingest_status(auth: tuple = Depends(verify_token)):
    """
    Returns whether the user has a master resume ingested.
    Frontend uses this on load to show/hide the upload zone in Step 2.
    """
    user_id, token = auth
    has_chunks = await db.has_resume_chunks(user_id)
    return {"has_master_resume": has_chunks}


# ── Background Worker ─────────────────────────────────────────────────────────
async def _run_analysis_job(
    job_id:       str,
    job_url:      str,
    resume_text:  str,
    user_id:      str,
    use_rag:      bool,
    orchestrator: CareerOrchestrator,
):
    """Runs in the background after POST /api/analyze returns job_id."""
    await job_queue.update_status(job_id, "processing")
    try:
        result = await orchestrator.run(job_url, resume_text, user_id=user_id, use_rag=use_rag)
        await job_queue.update_status(job_id, "done", result=result)
    except Exception as e:
        print(f"❌ Background job {job_id} failed: {str(e)}")
        await job_queue.update_status(job_id, "failed", error=str(e))


# ── Analyze (protected + rate limited + async) ────────────────────────────────
@app.post("/api/analyze")
@limiter.limit("5/day", key_func=_rate_limit_key)
async def analyze_match(
    request:          Request,
    background_tasks: BackgroundTasks,
    job_url:          str                  = Form(...),
    auth:             tuple                = Depends(verify_token),
    orchestrator:     CareerOrchestrator   = Depends(get_orchestrator),
    resume:           Optional[UploadFile] = File(None),
):
    """
    Returns job_id instantly. Analysis runs in the background.

    Resume upload is optional:
    - If user has a master resume ingested → RAG chunks are used, no upload needed
    - If user uploads a file → parsed and used as resume_text fallback
    - If neither → 400 error
    """
    user_id, token = auth
    resume_text = ""

    if resume and resume.filename:
        # User uploaded a file — parse it
        filename = resume.filename.lower()
        if not filename.endswith((".pdf", ".docx", ".txt")):
            raise HTTPException(status_code=400, detail="Invalid file type.")
        try:
            file_content = await resume.read()
            if filename.endswith(".pdf"):
                resume_text = ResumeParser.parse_pdf(file_content)
            elif filename.endswith(".docx"):
                resume_text = ResumeParser.parse_docx(file_content)
            else:
                resume_text = file_content.decode("utf-8")
            if len(resume_text) < 50:
                raise HTTPException(status_code=400, detail="Resume too short.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Parse failed: {str(e)}")
    else:
        # No file — check if user has RAG chunks
        has_chunks = await db.has_resume_chunks(user_id)
        if not has_chunks:
            raise HTTPException(
                status_code=400,
                detail="No resume uploaded and no master resume found. Please upload a resume or ingest your master resume first."
            )
        print(f"📂 Analyze: No file uploaded — RAG chunks will be used for user {user_id}")

    # use_rag=False when user uploaded a file — respect their explicit choice
    use_rag = not bool(resume and resume.filename)

    # Create job row with user token so RLS auth.uid() resolves correctly
    job_id = await job_queue.create_job(user_id, job_url, token)

    background_tasks.add_task(
        _run_analysis_job,
        job_id=job_id,
        job_url=job_url,
        resume_text=resume_text,
        user_id=user_id,
        use_rag=use_rag,
        orchestrator=orchestrator,
    )

    print(f"🚀 Job {job_id} queued for user {user_id} — returning immediately")
    return {"job_id": job_id, "status": "pending"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)