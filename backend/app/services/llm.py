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

    async def generate_resume(
        self,
        resume_text: str,
        job_text: str,
        analysis: AnalysisResult,
    ) -> tuple[str, list[str]]:
        missing_kw = ", ".join(analysis.missing_keywords) if analysis.missing_keywords else "None identified"
        prompt = f"""You are an expert resume writer and career coach.

CANDIDATE'S FULL RESUME:
{resume_text[:12000]}

TARGET JOB DESCRIPTION:
{job_text[:6000]}

KEYWORDS TO WEAVE IN NATURALLY (only where they genuinely fit real experience):
{missing_kw}

INSTRUCTIONS:
1. Rewrite the resume tailored to the target job above.
2. Preserve ALL factual experience — never invent roles, companies, dates, or achievements.
3. Naturally weave in the listed keywords where they genuinely apply.
4. You may reorder top-level sections only (e.g. move SKILLS before EXPERIENCE if more relevant).
   Within EXPERIENCE, always keep jobs in strict reverse chronological order — most recent first, never reordered.
   EDUCATION must always appear last, regardless of relevance.
5. Use exactly these section headers in ALL CAPS on their own lines:
   SUMMARY
   EXPERIENCE
   SKILLS
   EDUCATION
6. Under EXPERIENCE, format each job entry header on its own line as:
   **Company Name** | **Job Title** | Date Range
   Then list bullet points starting with a hyphen (-) on the lines below.
7. Keep writing concise, achievement-oriented, and ATS-friendly.
8. Never add commentary, markdown fences, or any text outside the JSON response.
9. Return a JSON object with exactly two fields:
   - "resume_text": the full tailored resume as a plain text string (same format as above)
   - "changes_summary": list of up to 8 short strings describing specific changes made,
     e.g. "Added 'Kubernetes' to DevOps bullet under Company X",
          "Moved SKILLS section above EXPERIENCE",
          "Rewrote summary to emphasize data engineering background"
     Only list real changes. If nothing changed in a section, omit it."""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            parsed = json.loads(response.text)
            resume_text_out    = parsed.get("resume_text", "").strip()
            changes_summary    = parsed.get("changes_summary", [])
            if not isinstance(changes_summary, list):
                changes_summary = []
            return resume_text_out, changes_summary
        except Exception as e:
            print(f"❌ Resume generation failed: {str(e)}")
            return "", []

    async def generate_cover_letter(
        self,
        resume_text: str,
        job_text: str,
        analysis: AnalysisResult,
    ) -> str:
        matching_kw = ", ".join(analysis.matching_keywords[:5]) if analysis.matching_keywords else "None identified"
        prompt = f"""You are a concise career coach. Write a short, punchy cover letter — no fluff, no big paragraphs.

CANDIDATE'S RESUME:
{resume_text[:8000]}

TARGET JOB DESCRIPTION:
{job_text[:4000]}

CANDIDATE'S TOP MATCHING STRENGTHS:
{matching_kw}

FORMAT — use exactly this structure:
Dear Hiring Team,

I'm excited to apply for the [exact job title] at [company name]. [One specific hook sentence — why this candidate fits, referencing a concrete achievement.]

• [One sentence: specific achievement from resume that maps to a key job requirement]
• [One sentence: another specific achievement from resume that maps to a key job requirement]
• [One sentence: third achievement OR how candidate addresses a gap — only if genuine]

I'd love to bring this experience to [company name].

Sincerely,
[Your Name]

RULES:
- Under 120 words total (not counting headers/sign-off)
- Never invent roles, companies, dates, or achievements
- No filler phrases like "I am writing to express my interest"
- Return strict JSON: {{"cover_letter": "...full plain text..."}}"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            parsed = json.loads(response.text)
            return parsed.get("cover_letter", "").strip()
        except Exception as e:
            print(f"❌ Cover letter generation failed: {str(e)}")
            return ""
