"""Briefing tools — set_briefing, stop_briefing for daily briefing schedule."""

import logging
import re

from pydantic_ai import RunContext

from agent import agent

logger = logging.getLogger(__name__)

# Will be set by bot.py after Application is built
_job_queue = None


def set_job_queue(jq) -> None:
    global _job_queue
    _job_queue = jq


@agent.tool
async def set_briefing(
    ctx: RunContext,
    time: str,
) -> str:
    """매일 정해진 시각에 일일 브리핑을 보내도록 설정합니다. "매일 아침 8시에 브리핑 해줘" 등에 사용하세요.

    Args:
        time: 브리핑 시각 HH:MM 형식 (KST, 예: "08:00", "07:30")
    """
    from memory.briefing import create_briefing

    if _job_queue is None:
        return '브리핑 시스템이 초기화되지 않았습니다.'

    chat_id = ctx.deps
    if not isinstance(chat_id, int):
        return '채팅 ID를 확인할 수 없습니다.'

    # Validate time format
    if not re.match(r'^\d{2}:\d{2}$', time):
        return f'시간 형식이 올바르지 않습니다: {time}. HH:MM 형식을 사용해주세요.'

    h, m = map(int, time.split(':'))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return f'유효하지 않은 시간입니다: {time}'

    await create_briefing(_job_queue, chat_id, time)
    return f'매일 {time} (KST)에 일일 브리핑을 보내드리겠습니다.'


@agent.tool
async def stop_briefing(ctx: RunContext) -> str:
    """일일 브리핑을 중지합니다. "브리핑 그만", "브리핑 중지" 등에 사용하세요."""
    from memory.briefing import stop_briefing_schedule

    if _job_queue is None:
        return '브리핑 시스템이 초기화되지 않았습니다.'

    chat_id = ctx.deps
    if not isinstance(chat_id, int):
        return '채팅 ID를 확인할 수 없습니다.'

    stopped = await stop_briefing_schedule(_job_queue, chat_id)
    if stopped:
        return '일일 브리핑이 중지되었습니다.'
    return '설정된 브리핑이 없습니다.'
