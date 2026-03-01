import hashlib
import os
from typing import List
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ── Constants ────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "text-embedding-004"   # 768-dim output, matches pgvector table
CHUNK_SIZE      = 500    # characters per chunk (sweet spot for resume sections)
CHUNK_OVERLAP   = 50     # overlap so context isn't lost at boundaries


class EmbeddingService:
    """
    Handles chunking resume text and generating embeddings via Gemini.
    Embeddings are 768-dimensional floats, matching the pgvector column.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        self.client = genai.Client(api_key=api_key)

    # ── Public API ────────────────────────────────────────────────────────────

    def chunk_text(self, text: str) -> List[str]:
        """
        Splits resume text into overlapping chunks.
        Simple character-based splitting — good enough for resumes
        which don't have huge pages of continuous prose.
        """
        chunks = []
        start = 0
        text = text.strip()

        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += CHUNK_SIZE - CHUNK_OVERLAP  # slide with overlap

        print(f"📄 Chunker: {len(text)} chars → {len(chunks)} chunks")
        return chunks

    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """
        Embeds a list of text chunks using Gemini text-embedding-004.
        Returns a list of 768-dim float vectors.

        Uses RETRIEVAL_DOCUMENT task type — optimised for storing documents
        that will later be retrieved via similarity search.
        """
        embeddings = []

        for i, chunk in enumerate(chunks):
            response = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=chunk,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT"
                )
            )
            # google-genai SDK: response.embeddings is a list of ContentEmbedding
            embeddings.append(response.embeddings[0].values)
            print(f"  🔢 Embedded chunk {i+1}/{len(chunks)}")

        return embeddings

    async def embed_query(self, query: str) -> List[float]:
        """
        Embeds a single query string for similarity search.
        Uses RETRIEVAL_QUERY task type — pair to RETRIEVAL_DOCUMENT above.
        """
        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY"
            )
        )
        return response.embeddings[0].values

    @staticmethod
    def hash_file(file_bytes: bytes) -> str:
        """SHA-256 hash of raw file bytes — used for dedup/cache."""
        return hashlib.sha256(file_bytes).hexdigest()
