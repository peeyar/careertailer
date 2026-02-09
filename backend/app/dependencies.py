from functools import lru_cache
from fastapi import Depends
from app.services.scraper import JobScraper
from app.services.llm import CareerAI
from app.orchestrator import CareerOrchestrator
from app.core.interfaces import IJobScraper, ICareerAI

# Singleton Pattern: We only want ONE instance of these services
# lru_cache ensures we don't recreate them on every request

@lru_cache()
def get_scraper_service() -> IJobScraper:
    return JobScraper()

@lru_cache()
def get_ai_service() -> ICareerAI:
    return CareerAI()

def get_orchestrator(
    scraper: IJobScraper = Depends(get_scraper_service),
    ai: ICareerAI = Depends(get_ai_service)
) -> CareerOrchestrator:
    """
    Factory that assembles the Orchestrator with its dependencies.
    FastAPI calls this automatically.
    """
    return CareerOrchestrator(scraper, ai)