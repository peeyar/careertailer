import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.orchestrator import CareerOrchestrator
from app.core.interfaces import IJobScraper, ICareerAI, AnalysisResult

# --- 1. Define Mocks (The Stunt Doubles) ---

class MockScraper(IJobScraper):
    """Pretends to scrape a website instantly."""
    async def scrape(self, url: str) -> str:
        if "bad-url" in url:
            raise Exception("404 Page Not Found")
        return "This is a Mock Job Description requiring Python and AWS."

class MockAI(ICareerAI):
    """Pretends to be Gemini instantly."""
    async def analyze_match(self, resume_text: str, job_text: str) -> AnalysisResult:
        return AnalysisResult(
            match_score=85,
            missing_keywords=["Kubernetes"],
            matching_keywords=["Python", "AWS"],
            summary_reasoning="Mock analysis successful."
        )

class MockAIFailure(ICareerAI):
    """Pretends Gemini is down."""
    async def analyze_match(self, resume_text: str, job_text: str) -> AnalysisResult:
        raise Exception("API Quota Exceeded")

# --- 2. The Tests ---

@pytest.mark.asyncio
async def test_orchestrator_success_flow():
    """
    Scenario: Happy Path.
    Scraper works -> AI works -> Data saved to DB -> Returns Result.
    """
    with patch("app.orchestrator.DatabaseService") as MockDBClass:
        # Arrange: Setup the Mock Instance to handle 'await'
        mock_db_instance = MockDBClass.return_value
        mock_db_instance.save_scrape = AsyncMock()   # <--- FIX: Make it awaitable
        mock_db_instance.save_analysis = AsyncMock() # <--- FIX: Make it awaitable

        orchestrator = CareerOrchestrator(MockScraper(), MockAI())
        
        # Act
        result = await orchestrator.run("http://good-url.com", "Resume text")
        
        # Assert
        assert result.match_score == 85
        assert "Python" in result.matching_keywords
        
        # Verify DB was called
        mock_db_instance.save_scrape.assert_called_once()
        mock_db_instance.save_analysis.assert_called_once()
        print("\n✅ Happy Path (with DB Save) Passed!")

@pytest.mark.asyncio
async def test_orchestrator_scraper_failure():
    """
    Scenario: Website is down.
    Scraper fails -> Orchestrator catches it -> Throws error.
    """
    with patch("app.orchestrator.DatabaseService") as MockDBClass:
        # Arrange
        mock_db_instance = MockDBClass.return_value
        mock_db_instance.save_scrape = AsyncMock() # Need this because scraper node calls it

        orchestrator = CareerOrchestrator(MockScraper(), MockAI())
        
        # Act & Assert
        with pytest.raises(Exception) as excinfo:
            await orchestrator.run("http://bad-url.com", "Resume text")
        
        # The error usually happens inside the node, wrapping the original error
        assert "Scraping Error" in str(excinfo.value)
        print("\n✅ Scraper Failure Handling Passed!")

@pytest.mark.asyncio
async def test_orchestrator_ai_failure():
    """
    Scenario: AI Service is down.
    Scraper works -> AI fails -> Orchestrator handles gracefully.
    """
    with patch("app.orchestrator.DatabaseService") as MockDBClass:
        # Arrange
        mock_db_instance = MockDBClass.return_value
        mock_db_instance.save_scrape = AsyncMock()   # Scraper succeeds, so this is called
        mock_db_instance.save_analysis = AsyncMock() # AI fails

        orchestrator = CareerOrchestrator(MockScraper(), MockAIFailure())
        
        # Act & Assert
        with pytest.raises(Exception) as excinfo:
            await orchestrator.run("http://good-url.com", "Resume text")
            
        assert "AI Error" in str(excinfo.value)
        print("\n✅ AI Failure Handling Passed!")