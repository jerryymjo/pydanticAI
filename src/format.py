"""Markdown → Telegram HTML converter using markdown-it-py."""

import html as html_mod
import re

from markdown_it import MarkdownIt

_md = MarkdownIt()

# Telegram이 지원하는 HTML 태그
_TG_TAGS = frozenset('b i s u a code pre blockquote'.split())


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from model output."""
    # Closed tags: <think>...</think>
    t = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Unclosed tag: <think>... (no closing tag)
    t = re.sub(r'<think>.*', '', t, flags=re.DOTALL)
    return t.strip()


def md_to_html(text: str) -> str:
    """Convert Markdown to Telegram-compatible HTML via markdown-it-py."""
    text = strip_think(text)
    if not text:
        return ''

    rendered = _md.render(text)

    t = rendered

    # --- 텔레그램 미지원 태그 → 텍스트 변환 ---

    # <p> → 줄바꿈
    t = t.replace('<p>', '').replace('</p>', '\n')

    # 제목 → 볼드
    t = re.sub(r'<h[1-6][^>]*>', '<b>', t)
    t = re.sub(r'</h[1-6]>', '</b>\n', t)

    # 시맨틱 → 텔레그램 태그
    t = t.replace('<strong>', '<b>').replace('</strong>', '</b>')
    t = t.replace('<em>', '<i>').replace('</em>', '</i>')
    t = t.replace('<del>', '<s>').replace('</del>', '</s>')

    # 리스트 → 유니코드 불릿
    t = re.sub(r'<[ou]l>\n?', '', t)
    t = re.sub(r'</[ou]l>\n?', '', t)
    t = re.sub(r'<li>\n?', '• ', t)
    t = t.replace('</li>', '')

    # <br> → 줄바꿈
    t = re.sub(r'<br\s*/?>', '\n', t)

    # <hr> → 구분선
    t = re.sub(r'<hr\s*/?>', '', t)

    # 미지원 태그 제거 (내용은 유지)
    def _keep_tg(m: re.Match) -> str:
        tag = m.group(1).strip('/').split()[0].lower()
        return m.group(0) if tag in _TG_TAGS else ''
    t = re.sub(r'<(/?\w[^>]*)>', _keep_tg, t)

    # 여러 줄바꿈 정리
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def strip_markdown(text: str) -> str:
    """Strip Markdown formatting, returning clean plain text."""
    text = strip_think(text)
    if not text:
        return ''
    rendered = _md.render(text)
    plain = re.sub(r'<[^>]+>', '', rendered)
    plain = html_mod.unescape(plain)
    plain = re.sub(r'\n{3,}', '\n\n', plain)
    return plain.strip()
