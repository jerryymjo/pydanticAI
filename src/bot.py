"""Telegram bot with PydanticAI agent.run() + Qdrant vector memory.

Uses agent.run() instead of run_stream() because run_stream() stops executing
tool calls when the model also produces text content (e.g. <think> tags).
agent.run() always runs the full agent graph including all tool calls.
"""

import logging
import os
from collections import defaultdict

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent import agent, set_memory_context  # noqa: F401 — must import before tools
import tools  # noqa: F401 — registers tools on agent
from format import md_to_html, strip_markdown, strip_think
from pydantic_ai.messages import ModelMessage

logging.basicConfig(
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
ALLOWED_CHAT_IDS = os.getenv('ALLOWED_CHAT_IDS', '')

# Per-chat conversation history
chat_histories: dict[int, list[ModelMessage]] = defaultdict(list)

# Memory system availability flag
_memory_ready = False


def is_allowed(chat_id: int) -> bool:
    if not ALLOWED_CHAT_IDS:
        return True
    allowed = {int(x.strip()) for x in ALLOWED_CHAT_IDS.split(',') if x.strip()}
    return chat_id in allowed


async def post_init(app: Application) -> None:
    """Initialize Qdrant + restore histories and alarms after bot starts."""
    global _memory_ready

    try:
        from memory import qdrant_store as qs
        from memory.manager import restore_histories
        from memory.alarms import restore_alarms
        from memory.briefing import restore_briefings
        from tools.alarm import set_job_queue
        from tools.briefing import set_job_queue as set_briefing_job_queue

        qs.ensure_collections()
        logger.info('Qdrant collections ready')

        # Restore chat histories
        restored = restore_histories()
        for chat_id, messages in restored.items():
            chat_histories[chat_id] = messages
        logger.info('Restored %d chat histories', len(restored))

        # Set job queue for alarm and briefing tools
        set_job_queue(app.job_queue)
        set_briefing_job_queue(app.job_queue)

        # Restore alarms
        count = restore_alarms(app.job_queue)
        logger.info('Restored %d alarms', count)

        # Restore briefings
        briefing_count = restore_briefings(app.job_queue)
        logger.info('Restored %d briefings', briefing_count)

        _memory_ready = True
        logger.info('Memory system initialized')
    except Exception:
        logger.error('Memory system init failed — running without memory', exc_info=True)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('안녕하세요! 자비스입니다. 무엇을 도와드릴까요?')


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat_histories[chat_id] = []
    await update.message.reply_text('대화 기록이 초기화되었습니다.')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_allowed(chat_id):
        return

    user_msg = update.message.text
    history = chat_histories[chat_id]

    await update.effective_chat.send_action('typing')

    try:
        # Search memory for relevant context
        if _memory_ready:
            from memory.manager import get_relevant_context, on_turn_complete

            mem_ctx = await get_relevant_context(chat_id, user_msg)
            set_memory_context(mem_ctx)
        else:
            set_memory_context('')

        result = await agent.run(user_msg, message_history=history, deps=chat_id)
        text = strip_think(result.output or '')
        if not text:
            text = '처리 완료했습니다.'

        formatted = md_to_html(text)
        plain = strip_markdown(text)
        if not plain:
            plain = text

        try:
            await update.message.reply_text(formatted, parse_mode=ParseMode.HTML)
        except Exception:
            logger.warning('HTML send failed, falling back to plain text')
            await update.message.reply_text(plain)

        chat_histories[chat_id] = list(result.all_messages())

        # Save to memory asynchronously (don't block response)
        if _memory_ready:
            import asyncio

            asyncio.create_task(
                on_turn_complete(chat_id, user_msg, text, chat_histories[chat_id])
            )

    except Exception as e:
        logger.error('Error handling message: %s', e, exc_info=True)
        await update.message.reply_text(f'오류가 발생했습니다: {type(e).__name__}')


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.post_init = post_init
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('reset', cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info('Bot starting...')
    app.run_polling()


if __name__ == '__main__':
    main()
