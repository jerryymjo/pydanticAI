"""Daily briefing — scheduling, callback, and restore via Qdrant + telegram JobQueue."""

import logging
from datetime import time as dt_time, timezone, timedelta

from telegram.ext import ContextTypes

from memory import qdrant_store as qs

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


async def _briefing_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for JobQueue — runs agent to generate briefing and sends it."""
    job = context.job
    chat_id = job.data['chat_id']

    try:
        from agent import agent, set_memory_context
        from memory.manager import get_relevant_context
        from format import md_to_html, strip_markdown, strip_think

        mem_ctx = await get_relevant_context(chat_id, '오늘 일정, 읽지 않은 메일, 할일 요약')
        set_memory_context(mem_ctx)

        result = await agent.run(
            '오늘 일정, 읽지 않은 메일, 할일을 요약해줘. 간결하게 브리핑 형식으로.',
            deps=chat_id,
        )
        text = strip_think(result.output or '')
        if not text:
            text = '오늘 브리핑할 내용이 없습니다.'

        formatted = md_to_html(text)
        plain = strip_markdown(text)

        from telegram.constants import ParseMode
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=formatted, parse_mode=ParseMode.HTML,
            )
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=plain or text)

        logger.info('Briefing sent to chat %d', chat_id)
    except Exception:
        logger.error('Failed to send briefing to chat %d', chat_id, exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=chat_id, text='브리핑 생성 중 오류가 발생했습니다.',
            )
        except Exception:
            pass


def schedule_briefing(job_queue, chat_id: int, time_str: str) -> None:
    """Schedule a daily briefing in the telegram JobQueue."""
    # Remove existing briefing job for this chat
    job_name = f'briefing-{chat_id}'
    current_jobs = job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    # Parse HH:MM and create time in KST
    h, m = map(int, time_str.split(':'))
    run_time = dt_time(hour=h, minute=m, tzinfo=KST)

    job_queue.run_daily(
        _briefing_callback,
        time=run_time,
        data={'chat_id': chat_id},
        name=job_name,
    )
    logger.info('Scheduled daily briefing for chat %d at %s KST', chat_id, time_str)


async def create_briefing(job_queue, chat_id: int, time_str: str) -> None:
    """Create and persist a new briefing schedule."""
    qs.save_briefing(chat_id, time_str)
    schedule_briefing(job_queue, chat_id, time_str)


async def stop_briefing_schedule(job_queue, chat_id: int) -> bool:
    """Stop and deactivate briefing for a chat. Returns True if was active."""
    briefing = qs.load_briefing(chat_id)
    if not briefing or not briefing.get('active'):
        return False

    qs.deactivate_briefing(chat_id)

    job_name = f'briefing-{chat_id}'
    current_jobs = job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    logger.info('Stopped briefing for chat %d', chat_id)
    return True


def restore_briefings(job_queue) -> int:
    """Restore active briefings from Qdrant and re-register in JobQueue."""
    count = 0
    try:
        briefings = qs.load_active_briefings()
        for b in briefings:
            schedule_briefing(job_queue, b['chat_id'], b['time'])
            count += 1
        logger.info('Restored %d briefings', count)
    except Exception:
        logger.error('Failed to restore briefings', exc_info=True)
    return count
