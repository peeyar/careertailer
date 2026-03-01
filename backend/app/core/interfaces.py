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


class IEmbeddingService(ABC):
    """
    Provider-agnostic contract for text embedding.

    Any embedding provider (Gemini, OpenAI, Voyage, etc.) must implement
    these methods. The rest of the app only ever imports this interface —
    never a concrete provider class.

    Switching providers = change EMBEDDING_PROVIDER in .env. That's it.

    ⚠️  When switching providers, vector dimensions may change.
    You must re-run the SQL schema with the new vector(N) size and
    re-ingest all master resumes. Existing embeddings will be incompatible.
    """

    @abstractmethod
    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """
        Embed a list of text chunks for storage (RETRIEVAL_DOCUMENT mode).
        Returns a list of float vectors, one per chunk.
        """
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """
        Embed a single query string for similarity search (RETRIEVAL_QUERY mode).
        Returns a single float vector.
        """
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """
        Number of dimensions this provider outputs.
        Must match the vector(N) column in the pgvector schema.
        """
        pass

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Shared chunking logic — identical for all providers.
        Lives on the interface so it's never duplicated across implementations.
        """
        chunks = []
        start = 0
        text = text.strip()
        while start < len(text):
            chunk = text[start: start + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
        print(f"📄 Chunker: {len(text)} chars → {len(chunks)} chunks")
        return chunks