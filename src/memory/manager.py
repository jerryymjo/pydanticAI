"""Memory manager — orchestrates saving, searching, and context injection."""

import json
import logging

from pydantic_ai.messages import ModelMessage

from memory import qdrant_store as qs
from memory.embeddings import embed_text
from memory.extractor import maybe_extract_insights

logger = logging.getLogger(__name__)

# Turn counter per chat for insight extraction
_turn_counts: dict[int, int] = {}


async def on_turn_complete(
    chat_id: int,
    user_text: str,
    assistant_text: str,
    all_messages: list[ModelMessage],
) -> None:
    """Called after each agent turn — saves conversation + snapshot, maybe extracts insights."""
    try:
        # 1. Embed and store conversation turn
        combined = f'User: {user_text}\nAssistant: {assistant_text}'
        vector = await embed_text(combined)
        qs.upsert_conversation(vector, chat_id, user_text, assistant_text)

        # 2. Save history snapshot
        from pydantic_ai.messages import ModelMessagesTypeAdapter
        messages_json = ModelMessagesTypeAdapter.dump_json(all_messages).decode()
        qs.save_history_snapshot(chat_id, messages_json)

        # 3. Maybe extract insights (every 3 turns)
        _turn_counts[chat_id] = _turn_counts.get(chat_id, 0) + 1
        if _turn_counts[chat_id] % 3 == 0:
            await maybe_extract_insights(chat_id, user_text, assistant_text)

        logger.info('Memory saved for chat %d (turn %d)', chat_id, _turn_counts[chat_id])
    except Exception:
        logger.error('Failed to save memory for chat %d', chat_id, exc_info=True)


async def get_relevant_context(chat_id: int, user_text: str) -> str:
    """Search conversations + memories + memos and build context string for system prompt."""
    try:
        vector = await embed_text(user_text)

        # Search past conversations
        convos = qs.search_conversations(vector, chat_id, limit=3)
        # Search auto-extracted memories
        memories = qs.search_memories(vector, limit=5)
        # Search user memos
        user_memos = qs.search_memos(vector, chat_id, limit=3)

        parts = []

        if memories:
            memo_lines = [f'- {m["content"]}' for m in memories if m.get('score', 0) > 0.3]
            if memo_lines:
                parts.append('=== 제리에 대해 알고 있는 것 ===')
                parts.extend(memo_lines)

        if user_memos:
            user_memo_lines = [
                f'- {m["content"]}' for m in user_memos if m.get('score', 0) > 0.4
            ]
            if user_memo_lines:
                parts.append('=== 제리가 저장한 메모 ===')
                parts.extend(user_memo_lines)

        if convos:
            convo_lines = []
            for c in convos:
                if c.get('score', 0) > 0.4:
                    convo_lines.append(
                        f'- 제리: "{c["user_text"]}" → 자비스: "{c["assistant_text"]}"'
                    )
            if convo_lines:
                parts.append('=== 관련 과거 대화 ===')
                parts.extend(convo_lines)

        return '\n'.join(parts)
    except Exception:
        logger.error('Failed to get context for chat %d', chat_id, exc_info=True)
        return ''


def restore_histories() -> dict[int, list[ModelMessage]]:
    """Restore all chat histories from Qdrant snapshots."""
    from pydantic_ai.messages import ModelMessagesTypeAdapter

    restored: dict[int, list[ModelMessage]] = {}
    try:
        snapshots = qs.load_all_history_snapshots()
        for snap in snapshots:
            chat_id = snap['chat_id']
            messages = ModelMessagesTypeAdapter.validate_json(snap['messages_json'])
            restored[chat_id] = list(messages)
            logger.info('Restored history for chat %d (%d messages)', chat_id, len(messages))
    except Exception:
        logger.error('Failed to restore histories', exc_info=True)
    return restored
