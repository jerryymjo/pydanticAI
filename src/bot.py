"""Telegram bot with PydanticAI streaming."""

import html
import logging
import os
import re
import time
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

from agent import agent  # noqa: F401 — must import before tools
import tools  # noqa: F401 — registers tools on agent
from pydantic_ai.messages import ModelMessage

logging.basicConfig(
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

def md_to_html(text: str) -> str:
    """Convert common Markdown to Telegram-safe HTML."""
    t = html.escape(text)
    # code blocks: ```lang\n...\n``` → <pre><code>...</code></pre>
    t = re.sub(
        r'```(?:\w*)\n(.*?)```',
        lambda m: f'<pre><code>{m.group(1)}</code></pre>',
        t,
        flags=re.DOTALL,
    )
    # inline code
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    # bold: **text** or __text__
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'__(.+?)__', r'<b>\1</b>', t)
    # italic: *text* or _text_
    t = re.sub(r'\*(.+?)\*', r'<i>\1</i>', t)
    t = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<i>\1</i>', t)
    # strikethrough
    t = re.sub(r'~~(.+?)~~', r'<s>\1</s>', t)
    # headings → bold
    t = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', t, flags=re.MULTILINE)
    # links [text](url)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
    return t


TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
ALLOWED_CHAT_IDS = os.getenv('ALLOWED_CHAT_IDS', '')

# Per-chat conversation history
chat_histories: dict[int, list[ModelMessage]] = defaultdict(list)

# Streaming config
EDIT_INTERVAL = 1.0  # min seconds between message edits
MIN_CHARS_DELTA = 50  # min new chars before editing


def is_allowed(chat_id: int) -> bool:
    if not ALLOWED_CHAT_IDS:
        return True
    allowed = {int(x.strip()) for x in ALLOWED_CHAT_IDS.split(',') if x.strip()}
    return chat_id in allowed


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

    sent_message = None
    buffer = ''
    last_sent = ''
    last_edit_time = 0.0

    try:
        async with agent.run_stream(user_msg, message_history=history) as stream:
            async for chunk in stream.stream_text(delta=True):
                buffer += chunk
                now = time.time()

                should_edit = (
                    len(buffer) - len(last_sent) >= MIN_CHARS_DELTA
                    and now - last_edit_time >= EDIT_INTERVAL
                )
                if should_edit:
                    if sent_message is None:
                        sent_message = await update.message.reply_text(buffer)
                    else:
                        try:
                            await sent_message.edit_text(buffer)
                        except Exception:
                            pass
                    last_sent = buffer
                    last_edit_time = now

            # Final update with HTML formatting
            if buffer:
                formatted = md_to_html(buffer)
                if sent_message is None:
                    try:
                        sent_message = await update.message.reply_text(
                            formatted, parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        sent_message = await update.message.reply_text(buffer)
                elif buffer != last_sent:
                    try:
                        await sent_message.edit_text(
                            formatted, parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        try:
                            await sent_message.edit_text(buffer)
                        except Exception:
                            pass

            # Save conversation history
            chat_histories[chat_id] = list(stream.all_messages())

    except Exception as e:
        logger.error('Error handling message: %s', e, exc_info=True)
        error_msg = f'오류가 발생했습니다: {type(e).__name__}'
        if sent_message:
            try:
                await sent_message.edit_text(error_msg)
            except Exception:
                pass
        else:
            await update.message.reply_text(error_msg)


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('reset', cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info('Bot starting...')
    app.run_polling()


if __name__ == '__main__':
    main()
