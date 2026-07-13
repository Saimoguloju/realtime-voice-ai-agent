#
# RAG knowledge base: OpenAI embeddings + cosine similarity over local markdown docs.
#

"""Retrieval-augmented knowledge base for the voice agent.

Loads markdown documents from ``knowledge/``, splits them into chunks, embeds
them with OpenAI ``text-embedding-3-small``, and answers queries by cosine
similarity. Embeddings are cached on disk (keyed by content hash) so documents
are only re-embedded when they change.
"""

import hashlib
import json
import os
from pathlib import Path

import numpy as np
from loguru import logger
from openai import AsyncOpenAI

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
CACHE_PATH = KNOWLEDGE_DIR / ".embeddings_cache.json"
EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 800  # characters


def _load_chunks() -> list[str]:
    """Split every markdown file in the knowledge dir into paragraph-aligned chunks."""
    chunks: list[str] = []
    for doc in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = doc.read_text(encoding="utf-8")
        current = ""
        for para in text.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) > CHUNK_SIZE and current:
                chunks.append(current.strip())
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para
        if current.strip():
            chunks.append(current.strip())
    return chunks


class KnowledgeBase:
    """In-memory vector index over the local markdown knowledge base."""

    def __init__(self):
        self._chunks: list[str] = []
        self._vectors: np.ndarray | None = None
        self._client: AsyncOpenAI | None = None

    async def _ensure_index(self) -> bool:
        """Build (or load from cache) the embedding index. Returns False if unavailable."""
        if self._vectors is not None:
            return True
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("Knowledge base disabled: OPENAI_API_KEY not set")
            return False

        self._chunks = _load_chunks()
        if not self._chunks:
            logger.warning(f"Knowledge base empty: no markdown files in {KNOWLEDGE_DIR}")
            return False

        cache: dict[str, list[float]] = {}
        if CACHE_PATH.exists():
            try:
                cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                cache = {}

        if self._client is None:
            self._client = AsyncOpenAI()

        vectors: list[list[float]] = []
        to_embed: list[tuple[int, str, str]] = []  # (index, hash, chunk)
        for i, chunk in enumerate(self._chunks):
            digest = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            if digest in cache:
                vectors.append(cache[digest])
            else:
                vectors.append([])  # placeholder, filled below
                to_embed.append((i, digest, chunk))

        if to_embed:
            logger.info(f"Embedding {len(to_embed)} knowledge chunks...")
            response = await self._client.embeddings.create(
                model=EMBEDDING_MODEL, input=[c for _, _, c in to_embed]
            )
            for (i, digest, _), item in zip(to_embed, response.data):
                vectors[i] = item.embedding
                cache[digest] = item.embedding
            CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")

        matrix = np.array(vectors, dtype=np.float32)
        self._vectors = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
        logger.info(f"Knowledge base ready: {len(self._chunks)} chunks indexed")
        return True

    async def search(self, query: str, top_k: int = 3) -> list[str]:
        """Return the ``top_k`` most relevant chunks for ``query`` (empty if unavailable)."""
        if not await self._ensure_index():
            return []
        assert self._client is not None and self._vectors is not None

        response = await self._client.embeddings.create(model=EMBEDDING_MODEL, input=[query])
        q = np.array(response.data[0].embedding, dtype=np.float32)
        q = q / np.linalg.norm(q)

        scores = self._vectors @ q
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [self._chunks[i] for i in top_indices]


# Module-level singleton shared by all sessions in this process.
knowledge_base = KnowledgeBase()
