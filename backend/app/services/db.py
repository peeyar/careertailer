import os
from supabase import create_client, Client
from app.core.interfaces import AnalysisResult
from dotenv import load_dotenv
from pathlib import Path

# Load env vars safely relative to this file
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class DatabaseService:
    """
    Handles all interactions with Supabase (Postgres).
    """
    def __init__(self):
       # Must match the exact names in your .env file
        supabase_url: str = os.getenv("SUPABASE_URL")
        supabase_key: str = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("⚠️ WARNING: Supabase keys not found in environment!")
            self.client = None
        else:
            self.client: Client = create_client(supabase_url, supabase_key)
            print("✅ Supabase client initialized successfully")

    async def save_scrape(self, url: str, text: str):
        """Saves a raw job description to the 'job_scrapes' table."""
        if not self.client: return
        
        try:
            # Upsert: If URL exists, update it.
            self.client.table("job_scrapes").upsert({
                "url": url,
                "raw_text": text
            }, on_conflict="url").execute()
            print("💾 DB: Job scrape saved.")
        except Exception as e:
            print(f"❌ DB Error (Save Scrape): {e}")

    async def save_analysis(self, job_url: str, result: AnalysisResult):
        """Saves the final analysis to 'analysis_sessions'."""
        if not self.client: return
        
        try:
            self.client.table("analysis_sessions").insert({
                "job_url": job_url,
                "match_score": result.match_score,
                "missing_keywords": result.missing_keywords,
                "matching_keywords": result.matching_keywords,
                "ai_summary": result.summary_reasoning
            }).execute()
            print("💾 DB: Analysis session saved.")
        except Exception as e:
            print(f"❌ DB Error (Save Analysis): {e}")
    
    async def get_history(self):
        """Fetches the 10 most recent analysis sessions."""
        if not self.client: 
            return []
        
        try:
            # Select all columns, order by newest first, limit to 10
            response = self.client.table("analysis_sessions").select("*").order("created_at", desc=True).limit(10).execute()
            return response.data
        except Exception as e:
            print(f"❌ DB Error (Get History): {e}")
            return []        