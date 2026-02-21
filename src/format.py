"""Markdown → Telegram HTML converter."""

import html
import re


def strip_think(text: str) -> str:
    """Remove Qwen3 <think>...</think> blocks from model output."""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


def md_to_html(text: str) -> str:
    """Convert common Markdown to Telegram-safe HTML."""
    t = strip_think(text)
    t = html.escape(t)
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


def strip_markdown(text: str) -> str:
    """Strip Markdown formatting, returning clean plain text."""
    t = strip_think(text)
    # code blocks → content only
    t = re.sub(r'```(?:\w*)\n(.*?)```', r'\1', t, flags=re.DOTALL)
    # inline code → content only
    t = re.sub(r'`([^`]+)`', r'\1', t)
    # bold/italic/strikethrough → content only
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
    t = re.sub(r'__(.+?)__', r'\1', t)
    t = re.sub(r'\*(.+?)\*', r'\1', t)
    t = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', t)
    t = re.sub(r'~~(.+?)~~', r'\1', t)
    # headings → content only
    t = re.sub(r'^#{1,6}\s+(.+)$', r'\1', t, flags=re.MULTILINE)
    # links → text (url)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', t)
    return t
