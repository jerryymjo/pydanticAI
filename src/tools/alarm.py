"""Alarm tool — set_alarm for scheduling reminders."""

import logging
from datetime import datetime, timezone

from pydantic_ai import RunContext

from agent import agent

logger = logging.getLogger(__name__)

# Will be set by bot.py after Application is built
_job_queue = None


def set_job_queue(jq) -> None:
    global _job_queue
    _job_queue = jq


@agent.tool
async def set_alarm(
    ctx: RunContext,
    message: str,
    fire_at: str,
    repeat: str = '',
) -> str:
    """알람/리마인더를 설정합니다.

    Args:
        message: 알림 메시지 (예: "미팅 시작")
        fire_at: 발송 시각 ISO 8601 (예: "2026-02-23T15:00:00+09:00")
        repeat: 반복 (daily, weekly, 또는 빈 문자열)
    """
    from memory.alarms import create_alarm

    logger.info('set_alarm called: %s at %s (repeat=%s)', message, fire_at, repeat)

    if _job_queue is None:
        return '알람 시스템이 초기화되지 않았습니다.'

    try:
        dt = datetime.fromisoformat(fire_at)
        if dt.tzinfo is None:
            # Assume KST if no timezone
            from datetime import timedelta
            dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))
    except ValueError:
        return f'시간 형식이 올바르지 않습니다: {fire_at}. ISO 8601 형식을 사용해주세요.'

    # Get chat_id from context deps (set by bot.py)
    chat_id = ctx.deps
    if not isinstance(chat_id, int):
        return '채팅 ID를 확인할 수 없습니다.'

    repeat_val = repeat if repeat in ('daily', 'weekly', 'monthly') else None

    alarm_id = await create_alarm(
        job_queue=_job_queue,
        chat_id=chat_id,
        message=message,
        fire_at=dt,
        repeat=repeat_val,
    )

    repeat_labels = {'daily': '일', 'weekly': '주', 'monthly': '월'}
    repeat_text = f' (매{repeat_labels.get(repeat_val, "")} 반복)' if repeat_val else ''
    return f'알람 설정 완료: "{message}" — {dt.strftime("%Y-%m-%d %H:%M")}{repeat_text}'
