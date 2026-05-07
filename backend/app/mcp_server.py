"""CareerTailor MCP Server.

Exposes CareerTailor's job-fit analysis as a single MCP tool over Streamable
HTTP. Designed to run as a long-lived process. Any MCP-compatible client
(JobScout v4, Claude Desktop, etc.) can call the analyze_job_fit tool through
the standard MCP protocol.

Phase 1: uses Supabase service role key for resume retrieval. user_id is
passed as a parameter — we don't infer it from a JWT.
"""
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from app.services.llm import CareerAI
from app.services.db import DatabaseService
from phoenix.otel import register
from opentelemetry import trace

load_dotenv()

# Phoenix observability — same project as JobScout v5 for unified traces.
# The shared project_name is what makes Phoenix join the JobScout-side and
# CareerTailor-side spans into a single distributed trace tree.
tracer_provider = register(
    project_name="jobscout-v5",
    endpoint="http://localhost:6006/v1/traces",
    auto_instrument=True,
)

tracer = trace.get_tracer("careertailer.mcp_server")

# Module-level singletons. Created once at server startup.
_career_ai: CareerAI | None = None
_db_service: DatabaseService | None = None


def get_career_ai() -> CareerAI:
    global _career_ai
    if _career_ai is None:
        _career_ai = CareerAI()
    return _career_ai


def get_db_service() -> DatabaseService:
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service


# ============================================================================
# MCP Server setup
# ============================================================================

mcp = FastMCP(
    name="careertailer",
    instructions=(
        "CareerTailor's job-fit analysis. Provides a tool that, given a job "
        "description and a user_id, retrieves the user's master resume from "
        "the database and returns a structured match analysis."
    ),
    host="0.0.0.0",
    port=int(os.environ.get("CAREERTAILER_MCP_PORT", 8765)),
)

# ============================================================================
# Tool: analyze_job_fit
# ============================================================================

class AnalyzeJobFitInput(BaseModel):
    """Input schema for analyze_job_fit."""
    user_id: str = Field(
        description="The Supabase user ID whose master resume to use for analysis."
    )
    job_description: str = Field(
        description=(
            "The full job description text. The MCP client provides this directly; "
            "the server does not scrape job postings."
        )
    )


class AnalyzeJobFitOutput(BaseModel):
    """Structured output. Mirrors AnalysisResult from app/core/interfaces."""
    match_score: int = Field(ge=0, le=100, description="0-100 match score")
    matching_keywords: list[str] = Field(
        description="Skills and keywords from the resume that match the job"
    )
    missing_keywords: list[str] = Field(
        description="Skills the job wants but the resume lacks"
    )
    summary_reasoning: str = Field(
        description="One- to three-sentence summary of the fit"
    )


@mcp.tool()
async def analyze_job_fit(input: AnalyzeJobFitInput) -> AnalyzeJobFitOutput:
    """Analyze how well a user's master resume matches a given job description.

    Returns a structured analysis with match score (0-100), matching keywords,
    missing keywords, and a short reasoning summary.

    The user_id is required because each user has their own ingested resume
    stored in the resume_chunks table.
    """
    with tracer.start_as_current_span("careertailer.analyze_job_fit") as span:
        span.set_attribute("user_id", input.user_id)
        span.set_attribute("job_description.length", len(input.job_description))

        db = get_db_service()
        ai = get_career_ai()

        resume_text = await db.get_full_resume_text(input.user_id)

        if not resume_text:
            raise ValueError(
                f"No master resume found for user_id={input.user_id}. "
                "User must ingest their resume before analyze_job_fit can run."
            )

        result = await ai.analyze_match(
            resume_text=resume_text,
            job_text=input.job_description,
        )

        span.set_attribute("match_score", result.match_score)

        return AnalyzeJobFitOutput(
            match_score=result.match_score,
            matching_keywords=result.matching_keywords,
            missing_keywords=result.missing_keywords,
            summary_reasoning=result.summary_reasoning,
        )


# ============================================================================
# Entry point — Streamable HTTP server
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("CAREERTAILER_MCP_PORT", 8765))
    print(f"Starting CareerTailor MCP server on port {port}...")
    print(f"Endpoint: http://localhost:{port}/mcp")



    mcp.run(transport="streamable-http")
