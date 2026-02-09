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
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        # If no keys, we operate in "Offline Mode" (client is None)
        if not url or not key:
            print("⚠️ Supabase credentials missing. Persistence will be disabled.")
            self.client = None
        else:
            try:
                self.client: Client = create_client(url, key)
            except Exception as e:
                print(f"❌ Supabase Connection Failed: {e}")
                self.client = None

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