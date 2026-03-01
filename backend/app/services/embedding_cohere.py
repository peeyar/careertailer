import os
from typing import List
from app.core.interfaces import IEmbeddingService

# embed-v4.0: 1024 dims, best quality, supports int8 quantization
# embed-v3-small: 384 dims, fastest, cheapest
_MODEL       = "embed-v4.0"
_OUTPUT_DIMS = 1024


class CohereEmbeddingService(IEmbeddingService):
    """
    Cohere implementation of IEmbeddingService.
    Great multilingual support — good choice if your users submit
    resumes or job descriptions in non-English languages.

    Requires: pip install cohere
    .env:      COHERE_API_KEY=...  (get at dashboard.cohere.com)

    embed-v4.0 supports:
      - input_type="search_document"  → for storing chunks
      - input_type="search_query"     → for similarity search
    """

    def __init__(self):
        try:
            import cohere
        except ImportError:
            raise ImportError(
                "cohere package not installed. Run: pip install cohere"
            )

        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY not found in environment variables")

        self.client = cohere.AsyncClientV2(api_key=api_key)

    @property
    def dimensions(self) -> int:
        return _OUTPUT_DIMS

    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        # Cohere supports batch embedding natively — one API call for all chunks
        response = await self.client.embed(
            texts=chunks,
            model=_MODEL,
            input_type="search_document",
            embedding_types=["float"],
        )
        print(f"  🔢 [Cohere] Embedded {len(chunks)} chunks in one batch call")
        return response.embeddings.float

    async def embed_query(self, query: str) -> List[float]:
        response = await self.client.embed(
            texts=[query],
            model=_MODEL,
            input_type="search_query",
            embedding_types=["float"],
        )
        return response.embeddings.float[0]
