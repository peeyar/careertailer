from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field

# --- 1. Data Models (The Shape of Data) ---

class AnalysisResult(BaseModel):
    """
    Standardized output for any Resume Analysis.
    Ensures Frontend always receives exactly this structure.
    """
    match_score: int = Field(..., description="0-100 score of fit")
    missing_keywords: List[str] = Field(default_factory=list, description="Critical skills missing from resume")
    matching_keywords: List[str] = Field(default_factory=list, description="Skills found in both resume and job")
    summary_reasoning: str = Field(..., description="AI explanation of the score")

# --- 2. Service Contracts (The Rules) ---

class IJobScraper(ABC):
    """Interface for any Job Scraping Service."""
    
    @abstractmethod
    async def scrape(self, url: str) -> str:
        """
        Contract: Takes a URL, returns the raw text description.
        Must handle its own errors internally.
        """
        pass

class ICareerAI(ABC):
    """Interface for any AI Analysis Service."""
    
    @abstractmethod
    async def analyze_match(self, resume_text: str, job_text: str) -> AnalysisResult:
        """
        Contract: Compares Resume vs Job.
        Must return a strict AnalysisResult object.
        """
        pass