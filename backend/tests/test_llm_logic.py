import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import GEval # We use this for everything now

# Import your actual app logic
from app.services.llm import CareerAI
from tests.deepeval_setup import GeminiJudge

# Initialize the Judge
judge = GeminiJudge()

@pytest.mark.asyncio
async def test_perfect_match_logic():
    """
    Scenario: A Python dev applying for a Python job.
    Expectation: High match score (> 80).
    """
    # 1. Setup Data
    resume_text = "Senior Python Developer with 8 years of experience in FastAPI, Django, and PostgreSQL. Expert in AWS."
    job_text = "We need a Senior Python Developer. Must know FastAPI, Database management, and Cloud deployment."
    
    # 2. Run your System (The 'Actual' Output)
    career_ai = CareerAI()
    analysis = await career_ai.analyze_match(resume_text, job_text)
    
    # Convert Pydantic model to string
    actual_output = analysis.model_dump_json()

    # 3. Define the Test Case
    test_case = LLMTestCase(
        input=f"Resume: {resume_text}\nJob: {job_text}",
        actual_output=actual_output,
        expected_output="Match Score should be above 80. The candidate has all required skills."
    )

    # 4. Define Metrics (Using GEval for custom correctness)
    
    # Custom Metric: Factual Correctness
    correctness_metric = GEval(
        name="Correctness",
        criteria="Determine if the actual output matches the expected output factually. The score must be high.",
        # We tell the Judge to look at the Input, Actual Result, and Expected Result
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
        model=judge,
        threshold=0.7
    )
    
    # Custom Metric: Score Validation
    score_metric = GEval(
        name="High Score Check",
        criteria="Check if the 'match_score' in the JSON is greater than 80.",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        model=judge,
        threshold=0.8
    )

    # 5. Run Assertions
    assert_test(test_case, [correctness_metric, score_metric])