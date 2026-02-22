"""BGE-M3 embedding model — lazy loaded, CPU-only singleton."""

import asyncio
import logging
import os
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
EMBEDDING_DIM = 1024


@lru_cache(maxsize=1)
def _load_model():
    """Load sentence-transformers model (called once, ~15s on CPU)."""
    from sentence_transformers import SentenceTransformer

    logger.info('Loading embedding model %s ...', EMBEDDING_MODEL)
    model = SentenceTransformer(EMBEDDING_MODEL, device='cpu')
    logger.info('Embedding model loaded.')
    return model


def _embed_sync(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return [e.tolist() for e in embeddings]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts asynchronously (runs in executor to avoid blocking)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_sync, texts)


async def embed_text(text: str) -> list[float]:
    """Embed a single text."""
    results = await embed_texts([text])
    return results[0]
