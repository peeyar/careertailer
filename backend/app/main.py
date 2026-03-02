from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os
from dataclasses import asdict
from starlette.responses import JSONResponse, FileResponse, Response
from app.dependencies import get_orchestrator
from app.orchestrator import CareerOrchestrator
from app.services.parser import ResumeParser
from app.services.db import DatabaseService
from app.services.job_queue import JobQueueService
from app.services.embedding_factory import get_embedding_service, hash_file
from app.services import style_extractor
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
        print(f"⚡ Ingest: Already embedded for user {user_id}. Skipping embedding, saving style.")
        file_type = "pdf" if filename.endswith(".pdf") else "docx" if filename.endswith(".docx") else "txt"
        style = style_extractor.extract(content, file_type)
        await db.save_resume_style(user_id, asdict(style))
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

    # Extract and persist resume style for later use in docx generation
    file_type = "pdf" if filename.endswith(".pdf") else "docx" if filename.endswith(".docx") else "txt"
    style = style_extractor.extract(content, file_type)
    await db.save_resume_style(user_id, asdict(style))

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
    job_id:        str,
    job_url:       str,
    resume_text:   str,
    user_id:       str,
    use_rag:       bool,
    orchestrator:  CareerOrchestrator,
    resume_style:  Optional[dict] = None,
):
    """Runs in the background after POST /api/analyze returns job_id."""
    await job_queue.update_status(job_id, "processing")
    try:
        result, docx_path, changes_summary = await orchestrator.run(
            job_url, resume_text, user_id=user_id, use_rag=use_rag, job_id=job_id, resume_style=resume_style
        )
        await job_queue.update_status(job_id, "done", result=result, docx_path=docx_path, changes_summary=changes_summary)
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
    resume_text  = ""
    resume_style = None

    if resume and resume.filename:
        # User uploaded a file — parse it and extract style
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
            file_type    = "pdf" if filename.endswith(".pdf") else "docx" if filename.endswith(".docx") else "txt"
            resume_style = asdict(style_extractor.extract(file_content, file_type))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Parse failed: {str(e)}")
    else:
        # No file — check if user has RAG chunks; style fetched in retriever node
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
        resume_style=resume_style,
    )

    print(f"🚀 Job {job_id} queued for user {user_id} — returning immediately")
    return {"job_id": job_id, "status": "pending"}


# ── Resume Download (protected) ───────────────────────────────────────────────
@app.get("/api/resume/{job_id}")
async def download_resume(job_id: str, auth: tuple = Depends(verify_token)):
    user_id, token = auth
    job = await job_queue.get_job(job_id, user_id, token)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    status = job.get("status")
    if status in ("pending", "processing"):
        raise HTTPException(status_code=425, detail="Resume is still being generated.")
    if status == "failed":
        raise HTTPException(status_code=404, detail="Job failed — no resume available.")
    storage_path = (job.get("result") or {}).get("docx_path")
    if not storage_path:
        raise HTTPException(status_code=404, detail="Resume document not found.")
    docx_bytes = await db.download_resume(storage_path)
    if not docx_bytes:
        raise HTTPException(status_code=404, detail="Resume document not found.")
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=tailored_resume_{job_id[:8]}.docx"},
    )


# ── Cover Letter Generation (protected, on-demand) ────────────────────────────
@app.post("/api/cover-letter/{job_id}")
async def generate_cover_letter(
    job_id:      str,
    auth:        tuple              = Depends(verify_token),
    orchestrator: CareerOrchestrator = Depends(get_orchestrator),
):
    user_id, token = auth
    job = await job_queue.get_job(job_id, user_id, token)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("status") != "done":
        raise HTTPException(status_code=425, detail="Analysis not complete yet.")

    result_data = job.get("result") or {}

    # Return cached cover letter if already generated
    if result_data.get("cover_letter"):
        return {"cover_letter": result_data["cover_letter"]}

    # Fetch job text from scrapes table
    job_text = await db.get_job_scrape(job["job_url"])
    if not job_text:
        raise HTTPException(status_code=404, detail="Job description not found — cannot generate cover letter.")

    # Fetch full resume text from chunks.
    # Upload-path jobs have no stored chunks — fall back to analysis data as minimal context.
    resume_chunks = await db.get_all_resume_chunks(user_id)
    if resume_chunks:
        resume_text = "\n\n".join(resume_chunks)
    else:
        matching = ", ".join(result_data.get("matching_keywords", []))
        resume_text = (
            f"Key skills and experience: {matching}\n\n"
            f"{result_data.get('summary_reasoning', '')}"
        )

    # Reconstruct AnalysisResult from stored result JSONB
    try:
        analysis = AnalysisResult(
            match_score=result_data.get("match_score", 0),
            missing_keywords=result_data.get("missing_keywords", []),
            matching_keywords=result_data.get("matching_keywords", []),
            summary_reasoning=result_data.get("summary_reasoning", ""),
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Could not reconstruct analysis data.")

    cover_letter = await orchestrator.ai.generate_cover_letter(
        resume_text=resume_text,
        job_text=job_text,
        analysis=analysis,
    )
    if not cover_letter:
        raise HTTPException(status_code=500, detail="Cover letter generation failed.")

    # Cache in the job result so subsequent requests are instant
    await job_queue.patch_cover_letter(job_id, cover_letter)

    return {"cover_letter": cover_letter}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)