import os
from typing import List
from app.core.interfaces import IEmbeddingService

# voyage-3-lite: 512 dims, fastest, cheapest
# voyage-3:      1024 dims, best quality/cost balance ← recommended
# voyage-3-large: 1024 dims, highest accuracy
_MODEL       = "voyage-3"
_OUTPUT_DIMS = 1024


class VoyageEmbeddingService(IEmbeddingService):
    """
    Voyage AI implementation of IEmbeddingService.
    Voyage is Anthropic's recommended embedding partner — pairs best with Claude.

    Requires: pip install voyageai
    .env:      VOYAGE_API_KEY=pa-...  (get at dash.voyageai.com)

    NOTE: If you switch to Claude for LLM generation, use this for embeddings.
    The voyage-3 model is specifically tuned for retrieval tasks.
    """

    def __init__(self):
        try:
            import voyageai
        except ImportError:
            raise ImportError(
                "voyageai package not installed. Run: pip install voyageai"
            )

        api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            raise ValueError("VOYAGE_API_KEY not found in environment variables")

        self.client = voyageai.AsyncClient(api_key=api_key)

    @property
    def dimensions(self) -> int:
        return _OUTPUT_DIMS

    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        # Voyage supports batch embedding natively
        result = await self.client.embed(
            chunks,
            model=_MODEL,
            input_type="document",   # equivalent to RETRIEVAL_DOCUMENT
        )
        print(f"  🔢 [Voyage] Embedded {len(chunks)} chunks in one batch call")
        return result.embeddings

    async def embed_query(self, query: str) -> List[float]:
        result = await self.client.embed(
            [query],
            model=_MODEL,
            input_type="query",      # equivalent to RETRIEVAL_QUERY
        )
        return result.embeddings[0]
