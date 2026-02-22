"""Memo/bookmark tools — save, search, list, delete user memos."""

import logging

from pydantic_ai import RunContext

from agent import agent

logger = logging.getLogger(__name__)


@agent.tool
async def save_memo(
    ctx: RunContext,
    content: str,
    category: str = 'memo',
) -> str:
    """사용자의 메모/북마크를 저장합니다. "기억해", "메모해", "저장해" 등의 요청에 사용하세요.

    Args:
        content: 저장할 내용 (예: "제리 생일은 3월 15일")
        category: 분류 — memo, bookmark, note 중 하나
    """
    from memory import qdrant_store as qs
    from memory.embeddings import embed_text

    chat_id = ctx.deps
    if not isinstance(chat_id, int):
        return '채팅 ID를 확인할 수 없습니다.'

    if category not in ('memo', 'bookmark', 'note'):
        category = 'memo'

    vector = await embed_text(content)
    memo_id = qs.save_memo(vector, chat_id, content, category)
    logger.info('Saved memo %s for chat %d: %s', memo_id, chat_id, content[:50])
    return f'메모 저장 완료: "{content}"'


@agent.tool
async def search_memo(
    ctx: RunContext,
    query: str,
) -> str:
    """저장된 메모를 시맨틱 검색합니다. "~에 대한 메모 뭐 있어?", "~관련 기억나?" 등에 사용하세요.

    Args:
        query: 검색 키워드 또는 질문 (예: "생일", "회의실 비번")
    """
    from memory import qdrant_store as qs
    from memory.embeddings import embed_text

    chat_id = ctx.deps
    if not isinstance(chat_id, int):
        return '채팅 ID를 확인할 수 없습니다.'

    vector = await embed_text(query)
    results = qs.search_memos(vector, chat_id, limit=5)

    if not results:
        return '관련 메모가 없습니다.'

    lines = []
    for r in results:
        if r.get('score', 0) > 0.3:
            lines.append(f'- [{r["memo_id"][:8]}] {r["content"]}')
    if not lines:
        return '관련 메모가 없습니다.'
    return '검색 결과:\n' + '\n'.join(lines)


@agent.tool
async def list_memos(ctx: RunContext) -> str:
    """저장된 모든 메모 목록을 보여줍니다. "내 메모 보여줘", "메모 목록" 등에 사용하세요."""
    from memory import qdrant_store as qs

    chat_id = ctx.deps
    if not isinstance(chat_id, int):
        return '채팅 ID를 확인할 수 없습니다.'

    memos = qs.list_memos(chat_id)
    if not memos:
        return '저장된 메모가 없습니다.'

    lines = []
    for m in memos:
        cat_label = {'memo': '메모', 'bookmark': '북마크', 'note': '노트'}.get(
            m.get('category', 'memo'), '메모'
        )
        lines.append(f'- [{m["memo_id"][:8]}] ({cat_label}) {m["content"]}')
    return f'메모 {len(lines)}건:\n' + '\n'.join(lines)


@agent.tool
async def delete_memo(
    ctx: RunContext,
    query: str,
) -> str:
    """메모를 삭제합니다. "~메모 지워", "~삭제해" 등에 사용하세요. query로 검색 후 가장 관련도 높은 메모를 삭제합니다.

    Args:
        query: 삭제할 메모의 키워드 (예: "회의실 비번", "생일")
    """
    from memory import qdrant_store as qs
    from memory.embeddings import embed_text

    chat_id = ctx.deps
    if not isinstance(chat_id, int):
        return '채팅 ID를 확인할 수 없습니다.'

    vector = await embed_text(query)
    results = qs.search_memos(vector, chat_id, limit=1)

    if not results or results[0].get('score', 0) < 0.3:
        return '삭제할 메모를 찾지 못했습니다.'

    target = results[0]
    ok = qs.delete_memo(target['memo_id'])
    if ok:
        return f'메모 삭제 완료: "{target["content"]}"'
    return '메모 삭제에 실패했습니다.'
