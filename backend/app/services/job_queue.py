import os
from typing import Optional
from supabase import Client, create_client
from app.core.interfaces import AnalysisResult
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

STATUS_PENDING    = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE       = "done"
STATUS_FAILED     = "failed"

SUPABASE_URL         = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY    = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def _anon_client() -> Client:
    """Anon client — for user-scoped reads with RLS (uses JWT from frontend)."""
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _service_client() -> Client:
    """
    Service role client — bypasses RLS entirely.
    Used for backend writes (update_status) and reads that happen
    outside user request context (background workers).
    NEVER expose this key to the frontend.
    """
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


class JobQueueService:
    """
    Manages async analysis jobs in the Supabase 'analysis_jobs' table.

    Key design:
    - create_job: uses user JWT so auth.uid() resolves for the INSERT RLS policy
    - update_status: uses service key — runs in background worker outside request context
    - get_job / get_user_jobs: uses service key — simpler and avoids set_session issues
      Security is enforced by the application-level .eq("user_id", user_id) filter
    """

    async def create_job(self, user_id: str, job_url: str, user_token: str) -> str:
        """Creates a new pending job. Uses user token so RLS INSERT policy passes."""
        client = _anon_client()
        client.auth.set_session(access_token=user_token, refresh_token="dummy")
        response = client.table("analysis_jobs").insert({
            "user_id": user_id,
            "job_url": job_url,
            "status":  STATUS_PENDING,
        }).execute()

        job_id = response.data[0]["id"]
        print(f"📋 Queue: Job {job_id} created for user {user_id}")
        return job_id

    async def update_status(
        self,
        job_id:          str,
        status:          str,
        result:          Optional[AnalysisResult] = None,
        error:           Optional[str] = None,
        docx_path:       Optional[str] = None,
        changes_summary: Optional[list] = None,
    ):
        """Updates job status. Uses service key — runs in background worker."""
        client = _service_client()
        payload: dict = {"status": status}

        if result:
            payload["result"] = {
                "match_score":       result.match_score,
                "missing_keywords":  result.missing_keywords,
                "matching_keywords": result.matching_keywords,
                "summary_reasoning": result.summary_reasoning,
                "docx_path":         docx_path,
                "changes_summary":   changes_summary or [],
            }
        if error:
            payload["error_message"] = error

        client.table("analysis_jobs").update(payload).eq("id", job_id).execute()
        print(f"📋 Queue: Job {job_id} → {status}")

    async def get_job(self, job_id: str, user_id: str, user_token: str = None) -> Optional[dict]:
        """
        Fetches a job by ID. Uses service key for reliable reads.
        Security enforced by application-level user_id filter — not RLS.
        """
        client = _service_client()
        response = (
            client.table("analysis_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", user_id)   # app-level security filter
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_user_jobs(self, user_id: str, user_token: str = None, limit: int = 10) -> list:
        """Fetches recent jobs for a user. Uses service key for reliable reads."""
        client = _service_client()
        response = (
            client.table("analysis_jobs")
            .select("id, job_url, status, result, created_at")
            .eq("user_id", user_id)   # app-level security filter
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    async def patch_cover_letter(self, job_id: str, cover_letter: str):
        """Merges cover_letter into the existing result JSONB for a completed job."""
        client = _service_client()
        response = (
            client.table("analysis_jobs")
            .select("result")
            .eq("id", job_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return
        existing = response.data[0].get("result") or {}
        existing["cover_letter"] = cover_letter
        client.table("analysis_jobs").update({"result": existing}).eq("id", job_id).execute()
        print(f"✉️  Queue: Cover letter cached for job {job_id}")