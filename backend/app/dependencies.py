from functools import lru_cache
from fastapi import Depends
from app.services.scraper import JobScraper
from app.services.llm import CareerAI
from app.services.embedding_factory import get_embedding_service
from app.orchestrator import CareerOrchestrator
from app.core.interfaces import IJobScraper, ICareerAI, IEmbeddingService


# ── Singletons ────────────────────────────────────────────────────────────────
# lru_cache ensures we create each service only once per process lifetime,
# not on every incoming request.

@lru_cache()
def get_scraper_service() -> IJobScraper:
    return JobScraper()

@lru_cache()
def get_ai_service() -> ICareerAI:
    return CareerAI()

@lru_cache()
def get_embedding_service_singleton() -> IEmbeddingService:
    # Reads EMBEDDING_PROVIDER from .env — swap provider with one line change
    return get_embedding_service()


# ── Orchestrator Factory ──────────────────────────────────────────────────────

def get_orchestrator(
    scraper:   IJobScraper       = Depends(get_scraper_service),
    ai:        ICareerAI         = Depends(get_ai_service),
    embedding: IEmbeddingService = Depends(get_embedding_service_singleton),
) -> CareerOrchestrator:
    """
    Assembles the Orchestrator with all three dependencies.
    FastAPI calls this automatically via Depends() in main.py.
    """
    return CareerOrchestrator(scraper, ai, embedding)
