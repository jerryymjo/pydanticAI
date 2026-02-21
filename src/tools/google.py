"""Google tools: gog (Gmail, Calendar, Chat, Drive, Docs, Sheets, Tasks)."""

import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Literal

from agent import agent

logger = logging.getLogger(__name__)

GOG_PATH = os.getenv('GOG_PATH', '/app/gog')
GOG_ACCOUNT = os.getenv('GOG_ACCOUNT', '')


async def _run_gog(args: list[str]) -> tuple[str, str, int]:
    """Run gog binary and return (stdout, stderr, returncode)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(), stderr.decode(), proc.returncode


def _base_args() -> list[str]:
    args = [GOG_PATH]
    if GOG_ACCOUNT:
        args.append(f'--account={GOG_ACCOUNT}')
    args.extend(['--no-input', '--json'])
    return args


@agent.tool_plain
async def gog(
    service: Literal['calendar', 'gmail', 'drive', 'tasks'],
    action: str,
    # --- calendar 날짜 ---
    from_date: str = '',
    to_date: str = '',
    today: bool = False,
    tomorrow: bool = False,
    days: int = 0,
    # --- calendar create/update ---
    summary: str = '',
    description: str = '',
    location: str = '',
    attendees: str = '',
    # --- gmail ---
    to_email: str = '',
    cc: str = '',
    subject: str = '',
    body: str = '',
    # --- tasks ---
    title: str = '',
    notes: str = '',
    due: str = '',
    list_id: str = '',
    # --- 공통 ---
    query: str = '',
    item_id: str = '',
) -> str:
    """Google 서비스 CLI.

    Args:
        service: calendar, gmail, drive, tasks
        action: 서비스별 명령어
          - calendar: list, create, update, delete, get, search
          - gmail: search, send, get
          - drive: ls, search, get, download, upload, mkdir, delete
          - tasks: lists, list, add, get, update, done, delete
        from_date: YYYY-MM-DD 시작일 (캘린더)
        to_date: YYYY-MM-DD 종료일 (생략시 from_date 다음날 자동설정)
        today: 오늘 일정
        tomorrow: 내일 일정
        days: N일간 일정 (예: 7)
        summary: 캘린더 일정 제목 (create/update)
        description: 캘린더 일정 설명 (create/update)
        location: 캘린더 일정 장소 (create/update)
        attendees: 캘린더 참석자 이메일 (쉼표 구분)
        to_email: gmail 수신자 (쉼표 구분)
        cc: gmail CC (쉼표 구분)
        subject: gmail 제목 (send)
        body: gmail 본문 (send)
        title: tasks 할일 제목 (add/update)
        notes: tasks 메모 (add/update)
        due: tasks 마감일 YYYY-MM-DD (add/update)
        list_id: tasks 목록 ID (기본: 첫번째 목록)
        query: 검색어 (calendar search, gmail search, drive search)
        item_id: 대상 ID (eventId, messageId, taskId, fileId)
    """
    args = _base_args() + [service, action]

    # ===== positional args =====
    if service == 'calendar':
        if action in ('create', 'update', 'delete', 'get'):
            args.append('primary')
            if action in ('update', 'delete', 'get') and item_id:
                args.append(item_id)
        elif action == 'search' and query:
            args.append(query)  # 단일 positional arg, split 안 함
    elif service == 'gmail':
        if action == 'get' and item_id:
            args.append(item_id)
        elif action == 'search' and query:
            args.append(query)  # 단일 positional arg
    elif service == 'drive':
        if action == 'search' and query:
            args.append(query)  # 단일 positional arg
        elif action in ('get', 'download', 'delete') and item_id:
            args.append(item_id)
    elif service == 'tasks':
        if action in ('list', 'add', 'create') and list_id:
            args.append(list_id)
        elif action in ('get', 'done', 'delete', 'update') and list_id:
            args.append(list_id)
            if item_id:
                args.append(item_id)

    # ===== calendar 날짜 플래그 =====
    if today:
        args.append('--today')
    elif tomorrow:
        args.append('--tomorrow')
    elif from_date:
        args.append(f'--from={from_date}')
        if to_date:
            if from_date == to_date:
                next_day = (date.fromisoformat(to_date) + timedelta(days=1)).isoformat()
                args.append(f'--to={next_day}')
                logger.info('gog: adjusted --to=%s → --to=%s (exclusive end)', to_date, next_day)
            else:
                args.append(f'--to={to_date}')
        else:
            next_day = (date.fromisoformat(from_date) + timedelta(days=1)).isoformat()
            args.append(f'--to={next_day}')
    elif days > 0:
        args.append(f'--days={days}')

    # ===== calendar create/update 플래그 =====
    if summary:
        args.append(f'--summary={summary}')
    if description:
        args.append(f'--description={description}')
    if location:
        args.append(f'--location={location}')
    if attendees:
        args.append(f'--attendees={attendees}')

    # ===== gmail send 플래그 =====
    if to_email:
        args.append(f'--to={to_email}')
    if cc:
        args.append(f'--cc={cc}')
    if subject:
        args.append(f'--subject={subject}')
    if body:
        args.append(f'--body={body}')

    # ===== tasks 플래그 =====
    if title:
        args.append(f'--title={title}')
    if notes:
        args.append(f'--notes={notes}')
    if due:
        args.append(f'--due={due}')

    # ===== drive ls --query 플래그 (positional이 아닌 경우) =====
    if service == 'drive' and action == 'ls' and query:
        args.append(f'--query={query}')

    logger.info('gog tool called: %s', ' '.join(args))
    stdout, stderr, rc = await _run_gog(args)
    output = stdout
    if rc != 0:
        logger.error('gog failed (rc=%d): %s', rc, stderr)
        help_args = [GOG_PATH, service, action, '--help']
        help_out, _, _ = await _run_gog(help_args)
        output = f'Error: {stderr}\n\n--- 사용법 ({service} {action}) ---\n{help_out}'
    if len(output) > 4000:
        output = output[:4000] + '\n... (잘림)'
    logger.info('gog result: %d chars, rc=%d', len(output), rc)
    return output
