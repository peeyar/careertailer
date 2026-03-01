import os
from typing import List
from supabase import create_client, Client
from app.core.interfaces import AnalysisResult
from dotenv import load_dotenv
from pathlib import Path

# Load env vars safely relative to this file
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class DatabaseService:
    """
    Handles all interactions with Supabase (Postgres + pgvector).
    Uses service role key for all writes to bypass RLS.
    RLS is enforced at application level via user_id filters on reads.
    """

    def __init__(self):
        supabase_url     = os.getenv("SUPABASE_URL")
        supabase_key     = os.getenv("SUPABASE_KEY")
        supabase_svc_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            print("⚠️  WARNING: Supabase keys not found in environment!")
            self.client = None
            self.service_client = None
        else:
            self.client: Client         = create_client(supabase_url, supabase_key)
            self.service_client: Client = create_client(supabase_url, supabase_svc_key or supabase_key)
            print("✅ Supabase client initialized successfully")

    # ── Existing Methods (unchanged) ──────────────────────────────────────────

    async def save_scrape(self, url: str, text: str):
        """Saves a raw job description to the 'job_scrapes' table."""
        if not self.service_client:
            return
        try:
            self.service_client.table("job_scrapes").upsert(
                {"url": url, "raw_text": text}, on_conflict="url"
            ).execute()
            print("💾 DB: Job scrape saved.")
        except Exception as e:
            print(f"❌ DB Error (Save Scrape): {e}")

    async def save_analysis(self, job_url: str, result: AnalysisResult):
        """Saves the final analysis to 'analysis_sessions'."""
        if not self.service_client:
            return
        try:
            self.service_client.table("analysis_sessions").insert({
                "job_url":           job_url,
                "match_score":       result.match_score,
                "missing_keywords":  result.missing_keywords,
                "matching_keywords": result.matching_keywords,
                "ai_summary":        result.summary_reasoning,
            }).execute()
            print("💾 DB: Analysis session saved.")
        except Exception as e:
            print(f"❌ DB Error (Save Analysis): {e}")

    async def get_history(self):
        """Fetches the 10 most recent analysis sessions."""
        if not self.client:
            return []
        try:
            response = (
                self.client.table("analysis_sessions")
                .select("*")
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )
            return response.data
        except Exception as e:
            print(f"❌ DB Error (Get History): {e}")
            return []

    # ── Phase 3: RAG / pgvector Methods ──────────────────────────────────────

    async def check_resume_exists(self, user_id: str, source_hash: str) -> bool:
        """
        Returns True if we already have embeddings for this exact file.
        Prevents re-embedding the same resume on every upload (saves Gemini quota).
        """
        if not self.client:
            return False
        try:
            response = (
                self.client.table("resume_chunks")
                .select("id")
                .eq("user_id", user_id)
                .eq("source_hash", source_hash)
                .limit(1)
                .execute()
            )
            return len(response.data) > 0
        except Exception as e:
            print(f"❌ DB Error (Check Resume): {e}")
            return False

    async def has_resume_chunks(self, user_id: str) -> bool:
        """
        Returns True if the user has ANY chunks stored — regardless of file hash.
        Used by /api/ingest/status and /api/analyze to decide if RAG is available.
        """
        if not self.client:
            return False
        try:
            response = (
                self.client.table("resume_chunks")
                .select("id")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            return len(response.data) > 0
        except Exception as e:
            print(f"❌ DB Error (Has Chunks): {e}")
            return False

    async def delete_resume_chunks(self, user_id: str):
        """
        Deletes all existing chunks for a user before storing new ones.
        Called when a user uploads a NEW master resume (replaces the old one).
        """
        if not self.client:
            return
        try:
            self.service_client.table("resume_chunks").delete().eq("user_id", user_id).execute()
            print(f"🗑️  DB: Old chunks deleted for user {user_id}")
        except Exception as e:
            print(f"❌ DB Error (Delete Chunks): {e}")

    async def save_resume_chunks(
        self,
        user_id: str,
        source_hash: str,
        chunks: List[str],
        embeddings: List[List[float]],
    ):
        """
        Upserts resume chunks + their embeddings into the resume_chunks table.
        Deletes old chunks first so the user always has a fresh master resume.
        """
        if not self.client:
            return

        # Delete old chunks for this user first
        await self.delete_resume_chunks(user_id)

        rows = [
            {
                "user_id":     user_id,
                "chunk_index": i,
                "chunk_text":  chunk,
                "embedding":   embedding,   # Supabase client serialises list → vector
                "source_hash": source_hash,
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        try:
            self.service_client.table("resume_chunks").insert(rows).execute()
            print(f"💾 DB: {len(rows)} resume chunks saved for user {user_id}")
        except Exception as e:
            print(f"❌ DB Error (Save Chunks): {e}")
            raise  # Re-raise so the endpoint returns a 500

    async def search_similar_chunks(
        self,
        user_id: str,
        query_embedding: List[float],
        match_threshold: float = 0.5,
        match_count: int = 5,
    ) -> List[dict]:
        """
        Runs a pgvector cosine similarity search via the Supabase RPC function.
        Returns the top-k most relevant chunks from the user's master resume.
        Used by the AI agent to ground generation in real resume content.
        """
        if not self.client:
            return []
        try:
            response = self.client.rpc(
                "match_resume_chunks",
                {
                    "query_embedding":  query_embedding,
                    "match_user_id":    user_id,
                    "match_threshold":  match_threshold,
                    "match_count":      match_count,
                },
            ).execute()
            return response.data or []
        except Exception as e:
            print(f"❌ DB Error (Similarity Search): {e}")
            return []