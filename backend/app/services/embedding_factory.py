import os
import hashlib
from app.core.interfaces import IEmbeddingService


def get_embedding_service() -> IEmbeddingService:
    """
    Factory function — reads EMBEDDING_PROVIDER from .env and returns
    the correct concrete implementation.

    To switch providers, change ONE line in your .env:
        EMBEDDING_PROVIDER=gemini   → GeminiEmbeddingService
        EMBEDDING_PROVIDER=openai   → OpenAIEmbeddingService
        EMBEDDING_PROVIDER=voyage   → VoyageEmbeddingService  (recommended with Claude)

    Default: gemini (preserves existing behaviour)

    ⚠️  IMPORTANT: If you switch providers, the vector dimensions may change.
    You must re-run the SQL schema with the new vector(N) size and
    re-ingest all master resumes. Existing embeddings will be incompatible.
    """
    provider = os.getenv("EMBEDDING_PROVIDER", "gemini").lower().strip()

    if provider == "gemini":
        from app.services.embedding_gemini import GeminiEmbeddingService
        print(f"🔌 EmbeddingFactory: Using Gemini (768 dims)")
        return GeminiEmbeddingService()

    elif provider == "openai":
        from app.services.embedding_openai import OpenAIEmbeddingService
        print(f"🔌 EmbeddingFactory: Using OpenAI text-embedding-3-small (1536 dims)")
        return OpenAIEmbeddingService()

    elif provider == "voyage":
        from app.services.embedding_voyage import VoyageEmbeddingService
        print(f"🔌 EmbeddingFactory: Using Voyage AI voyage-3 (1024 dims)")
        return VoyageEmbeddingService()

    elif provider == "cohere":
        from app.services.embedding_cohere import CohereEmbeddingService
        print(f"🔌 EmbeddingFactory: Using Cohere embed-v4.0 (1024 dims)")
        return CohereEmbeddingService()

    else:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER: '{provider}'. "
            f"Valid options: gemini, openai, voyage, cohere"
        )


def hash_file(file_bytes: bytes) -> str:
    """SHA-256 hash of raw file bytes — used for dedup/cache. Provider-agnostic."""
    return hashlib.sha256(file_bytes).hexdigest()
