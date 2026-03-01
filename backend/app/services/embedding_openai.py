import os
from typing import List
from app.core.interfaces import IEmbeddingService

# text-embedding-3-small: 1536 dims, cheap, great for RAG
# text-embedding-3-large: 3072 dims, higher accuracy, costs more
_MODEL       = "text-embedding-3-small"
_OUTPUT_DIMS = 1536


class OpenAIEmbeddingService(IEmbeddingService):
    """
    OpenAI implementation of IEmbeddingService.
    Requires: pip install openai
    .env:      OPENAI_API_KEY=sk-...
    """

    def __init__(self):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.client = AsyncOpenAI(api_key=api_key)

    @property
    def dimensions(self) -> int:
        return _OUTPUT_DIMS

    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        # OpenAI supports batch embedding — much faster than one-by-one
        response = await self.client.embeddings.create(
            model=_MODEL,
            input=chunks,
        )
        embeddings = [item.embedding for item in response.data]
        print(f"  🔢 [OpenAI] Embedded {len(chunks)} chunks in one batch call")
        return embeddings

    async def embed_query(self, query: str) -> List[float]:
        response = await self.client.embeddings.create(
            model=_MODEL,
            input=[query],
        )
        return response.data[0].embedding
