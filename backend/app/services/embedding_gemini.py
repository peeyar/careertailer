import os
from typing import List
from google import genai
from google.genai import types
from app.core.interfaces import IEmbeddingService

# chunk_text() is inherited from IEmbeddingService — no need to reimplement it here.
# gemini-embedding-001 supports output_dimensionality so we pin to 768
# to keep pgvector storage lean. Change OUTPUT_DIMS here if you want
# higher precision — but you'll need to re-run the SQL schema too.
_MODEL       = "gemini-embedding-001"
_OUTPUT_DIMS = 768


class GeminiEmbeddingService(IEmbeddingService):
    """
    Gemini implementation of IEmbeddingService.
    Uses google-genai SDK (v1.60+).
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        self.client = genai.Client(api_key=api_key)

    @property
    def dimensions(self) -> int:
        return _OUTPUT_DIMS

    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        embeddings = []
        for i, chunk in enumerate(chunks):
            response = self.client.models.embed_content(
                model=_MODEL,
                contents=chunk,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=_OUTPUT_DIMS,
                ),
            )
            embeddings.append(response.embeddings[0].values)
            print(f"  🔢 [Gemini] Embedded chunk {i + 1}/{len(chunks)}")
        return embeddings

    async def embed_query(self, query: str) -> List[float]:
        response = self.client.models.embed_content(
            model=_MODEL,
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=_OUTPUT_DIMS,
            ),
        )
        return response.embeddings[0].values
