"""Qdrant client singleton and collection CRUD."""

import logging
import os
import uuid
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from memory.embeddings import EMBEDDING_DIM

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://qdrant:6333')

_client: QdrantClient | None = None

# Collection names
CONVERSATIONS = 'conversations'
MEMORIES = 'memories'
HISTORY_SNAPSHOTS = 'history_snapshots'
ALARMS = 'alarms'


def get_client() -> QdrantClient:
    """Get or create Qdrant client singleton."""
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, timeout=10)
        logger.info('Connected to Qdrant at %s', QDRANT_URL)
    return _client


def ensure_collections() -> None:
    """Create collections if they don't exist."""
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}

    vector_collections = {
        CONVERSATIONS: EMBEDDING_DIM,
        MEMORIES: EMBEDDING_DIM,
    }
    for name, dim in vector_collections.items():
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            logger.info('Created collection: %s', name)

    # history_snapshots and alarms don't need real vectors — use dim=1 dummy
    for name in (HISTORY_SNAPSHOTS, ALARMS):
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=1, distance=Distance.COSINE),
            )
            logger.info('Created collection: %s', name)


# ── conversations ──


def upsert_conversation(
    vector: list[float],
    chat_id: int,
    user_text: str,
    assistant_text: str,
) -> str:
    point_id = str(uuid.uuid4())
    get_client().upsert(
        collection_name=CONVERSATIONS,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    'chat_id': chat_id,
                    'user_text': user_text,
                    'assistant_text': assistant_text,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                },
            )
        ],
    )
    return point_id


def search_conversations(
    vector: list[float], chat_id: int, limit: int = 3
) -> list[dict]:
    results = get_client().query_points(
        collection_name=CONVERSATIONS,
        query=vector,
        query_filter=Filter(
            must=[FieldCondition(key='chat_id', match=MatchValue(value=chat_id))]
        ),
        limit=limit,
    )
    return [
        {**p.payload, 'score': p.score}
        for p in results.points
    ]


# ── memories ──


def upsert_memory(
    vector: list[float],
    content: str,
    category: str,
    confidence: float,
) -> str:
    point_id = str(uuid.uuid4())
    get_client().upsert(
        collection_name=MEMORIES,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    'content': content,
                    'category': category,
                    'confidence': confidence,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                },
            )
        ],
    )
    return point_id


def search_memories(vector: list[float], limit: int = 5) -> list[dict]:
    results = get_client().query_points(
        collection_name=MEMORIES,
        query=vector,
        limit=limit,
    )
    return [
        {**p.payload, 'score': p.score}
        for p in results.points
    ]


# ── history_snapshots ──


def save_history_snapshot(chat_id: int, messages_json: str) -> None:
    """Upsert a single snapshot per chat_id (deterministic ID)."""
    # Use a deterministic point ID based on chat_id so upsert overwrites
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'history-{chat_id}'))
    get_client().upsert(
        collection_name=HISTORY_SNAPSHOTS,
        points=[
            PointStruct(
                id=point_id,
                vector=[0.0],  # dummy
                payload={
                    'chat_id': chat_id,
                    'messages_json': messages_json,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                },
            )
        ],
    )


def load_history_snapshot(chat_id: int) -> str | None:
    """Load history snapshot for a chat. Returns JSON string or None."""
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'history-{chat_id}'))
    results = get_client().retrieve(
        collection_name=HISTORY_SNAPSHOTS,
        ids=[point_id],
    )
    if results:
        return results[0].payload.get('messages_json')
    return None


def load_all_history_snapshots() -> list[dict]:
    """Load all history snapshots (for restore on startup)."""
    results = get_client().scroll(
        collection_name=HISTORY_SNAPSHOTS,
        limit=1000,
    )
    return [
        {'chat_id': p.payload['chat_id'], 'messages_json': p.payload['messages_json']}
        for p in results[0]
    ]


# ── alarms ──


def save_alarm(
    alarm_id: str,
    chat_id: int,
    message: str,
    fire_at: str,
    repeat: str | None = None,
) -> None:
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'alarm-{alarm_id}'))
    get_client().upsert(
        collection_name=ALARMS,
        points=[
            PointStruct(
                id=point_id,
                vector=[0.0],  # dummy
                payload={
                    'alarm_id': alarm_id,
                    'chat_id': chat_id,
                    'message': message,
                    'fire_at': fire_at,
                    'repeat': repeat,
                    'active': True,
                },
            )
        ],
    )


def deactivate_alarm(alarm_id: str) -> None:
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'alarm-{alarm_id}'))
    get_client().set_payload(
        collection_name=ALARMS,
        payload={'active': False},
        points=[point_id],
    )


def load_active_alarms() -> list[dict]:
    """Load all active alarms (for restore on startup)."""
    results = get_client().scroll(
        collection_name=ALARMS,
        scroll_filter=Filter(
            must=[FieldCondition(key='active', match=MatchValue(value=True))]
        ),
        limit=1000,
    )
    return [p.payload for p in results[0]]
