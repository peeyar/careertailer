import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app.core.interfaces import ICareerAI, AnalysisResult

load_dotenv()


class CareerAI(ICareerAI):
    """
    Gemini Implementation of the AI Service.
    Uses Google GenAI SDK (google-genai 1.60+).

    The analyze_match method accepts either:
      - Retrieved RAG chunks (preferred) — precise, grounded in real experience
      - Full raw resume text (fallback) — used when no chunks have been ingested
    The orchestrator decides which to pass; this class doesn't need to know.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        self.client     = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"

    async def analyze_match(self, resume_text: str, job_text: str) -> AnalysisResult:

        prompt = f"""
        You are an expert ATS (Applicant Tracking System) and Technical Recruiter.

        Analyze the fit between the candidate's experience and the job description.

        CANDIDATE EXPERIENCE:
        The following are the most relevant sections from the candidate's resume,
        retrieved specifically because they relate to this job. Use these as the
        primary source of truth for the candidate's skills and background.

        {resume_text[:12000]}

        JOB DESCRIPTION:
        {job_text[:6000]}

        Your task:
        1. Identify hard skills, tools, and technologies required by the job.
        2. Check which of those appear in the candidate's experience above.
        3. List what's missing and what matches.
        4. Score the overall fit from 0-100.

        Output strict JSON matching this schema exactly — no extra fields:
        {{
            "match_score": (integer 0-100),
            "missing_keywords": [list of critical hard skills/tools missing from the candidate experience],
            "matching_keywords": [list of hard skills/tools present in both],
            "summary_reasoning": "3 sentence max: overall fit, biggest gap, strongest match."
        }}
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )

            parsed_data = json.loads(response.text)
            return AnalysisResult(**parsed_data)

        except Exception as e:
            print(f"❌ AI Error: {str(e)}")
            return AnalysisResult(
                match_score=0,
                missing_keywords=[],
                matching_keywords=[],
                summary_reasoning=f"Analysis failed: {str(e)}",
            )
