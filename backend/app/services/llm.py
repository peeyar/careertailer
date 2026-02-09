import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Import the Contract and Model
from app.core.interfaces import ICareerAI, AnalysisResult

load_dotenv()

class CareerAI(ICareerAI):
    """
    Gemini Implementation of the AI Service.
    Uses Google GenAI SDK.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"  # Cost-effective, fast model

    async def analyze_match(self, resume_text: str, job_text: str) -> AnalysisResult:
        
        # 1. Construct the Prompt
        prompt = f"""
        You are an expert ATS (Applicant Tracking System) and Technical Recruiter.
        
        Analyze the fit between the candidate's resume and the job description.
        
        RESUME TEXT:
        {resume_text[:10000]} 

        JOB DESCRIPTION:
        {job_text[:10000]}

        Output strict JSON matching this schema:
        {{
            "match_score": (integer 0-100),
            "missing_keywords": [list of critical hard skills missing from resume],
            "matching_keywords": [list of hard skills present in both],
            "summary_reasoning": "Brief professional summary of the gap analysis (max 3 sentences)."
        }}
        """

        try:
            # 2. Call Gemini
            # We use 'response_mime_type' to enforce JSON output
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )

            # 3. Parse JSON
            raw_json = response.text
            parsed_data = json.loads(raw_json)

            # 4. Validate & Return Pydantic Object
            # This ensures the data strictly matches our Enterprise Schema
            return AnalysisResult(**parsed_data)

        except Exception as e:
            print(f"❌ AI Error: {str(e)}")
            # Return a "Failed" object rather than crashing the whole app
            # allowing the Orchestrator to decide what to do.
            return AnalysisResult(
                match_score=0,
                missing_keywords=[],
                matching_keywords=[],
                summary_reasoning=f"Analysis failed: {str(e)}"
            )