"""Alarm persistence and scheduling via Qdrant + telegram JobQueue."""

import logging
import uuid
from datetime import datetime, timezone

from telegram.ext import ContextTypes

from memory import qdrant_store as qs

logger = logging.getLogger(__name__)


async def _fire_alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for JobQueue — sends alarm message to chat."""
    job = context.job
    data = job.data
    chat_id = data['chat_id']
    alarm_id = data['alarm_id']
    message = data['message']
    repeat = data.get('repeat')

    try:
        await context.bot.send_message(chat_id=chat_id, text=f'⏰ 알림: {message}')
        logger.info('Alarm fired: %s → chat %d', alarm_id, chat_id)

        if not repeat:
            qs.deactivate_alarm(alarm_id)
    except Exception:
        logger.error('Failed to fire alarm %s', alarm_id, exc_info=True)


def schedule_alarm(
    job_queue,
    alarm_id: str,
    chat_id: int,
    message: str,
    fire_at: datetime,
    repeat: str | None = None,
) -> None:
    """Schedule an alarm in the telegram JobQueue."""
    now = datetime.now(timezone.utc)
    data = {
        'alarm_id': alarm_id,
        'chat_id': chat_id,
        'message': message,
        'repeat': repeat,
    }

    if repeat == 'daily':
        job_queue.run_daily(
            _fire_alarm,
            time=fire_at.timetz(),
            data=data,
            name=f'alarm-{alarm_id}',
        )
    elif repeat == 'weekly':
        job_queue.run_daily(
            _fire_alarm,
            time=fire_at.timetz(),
            days=(fire_at.weekday(),),
            data=data,
            name=f'alarm-{alarm_id}',
        )
    else:
        # One-shot alarm
        if fire_at <= now:
            logger.warning('Alarm %s is in the past, skipping', alarm_id)
            qs.deactivate_alarm(alarm_id)
            return
        job_queue.run_once(
            _fire_alarm,
            when=fire_at,
            data=data,
            name=f'alarm-{alarm_id}',
        )

    logger.info('Scheduled alarm %s at %s (repeat=%s)', alarm_id, fire_at, repeat)


async def create_alarm(
    job_queue,
    chat_id: int,
    message: str,
    fire_at: datetime,
    repeat: str | None = None,
) -> str:
    """Create and persist a new alarm. Returns alarm_id."""
    alarm_id = str(uuid.uuid4())

    qs.save_alarm(
        alarm_id=alarm_id,
        chat_id=chat_id,
        message=message,
        fire_at=fire_at.isoformat(),
        repeat=repeat,
    )

    schedule_alarm(job_queue, alarm_id, chat_id, message, fire_at, repeat)
    return alarm_id


def restore_alarms(job_queue) -> int:
    """Restore active alarms from Qdrant and re-register in JobQueue."""
    count = 0
    try:
        alarms = qs.load_active_alarms()
        for alarm in alarms:
            fire_at = datetime.fromisoformat(alarm['fire_at'])
            schedule_alarm(
                job_queue,
                alarm_id=alarm['alarm_id'],
                chat_id=alarm['chat_id'],
                message=alarm['message'],
                fire_at=fire_at,
                repeat=alarm.get('repeat'),
            )
            count += 1
        logger.info('Restored %d alarms', count)
    except Exception:
        logger.error('Failed to restore alarms', exc_info=True)
    return count
