"""Google tools: gog (Gmail, Calendar, Chat, Drive, Docs, Sheets, Tasks)."""

import asyncio
import logging
import os
import re
from datetime import date, timedelta
from typing import Literal

from agent import agent

logger = logging.getLogger(__name__)

GOG_PATH = os.getenv('GOG_PATH', '/app/gog')
GOG_ACCOUNT = os.getenv('GOG_ACCOUNT', '')
GOG_TIMEZONE = os.getenv('GOG_TIMEZONE', '+09:00')  # KST


def _ensure_tz(dt_str: str) -> str:
    """시간이 포함된 날짜에 타임존이 없으면 자동 추가."""
    if not dt_str or 'T' not in dt_str:
        return dt_str
    if '+' in dt_str.split('T')[1] or dt_str.endswith('Z'):
        return dt_str
    return dt_str + GOG_TIMEZONE


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
    args.extend(['--no-input', '--json', '--force'])
    return args


def _merge_time(d: str, t: str, tz: str) -> str:
    """날짜(YYYY-MM-DD) + 시간(HH:MM) → RFC3339 합성."""
    return f'{d}T{t}:00{tz}'


def _auto_end_time(start: str) -> str:
    """HH:MM → 1시간 후 HH:MM."""
    h, m = start.split(':')
    return f'{int(h) + 1:02d}:{m}'


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
    start_time: str = '',
    end_time: str = '',
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
          - gmail: list (받은편지함), search (Gmail 검색 구문), send, get
          - drive: ls, search, get, download, upload, mkdir, delete
          - tasks: lists, list, add, get, update, done, delete
        from_date: YYYY-MM-DD 시작일 (캘린더)
        to_date: YYYY-MM-DD 종료일 (생략시 from_date 다음날 자동설정)
        today: 오늘 일정
        tomorrow: 내일 일정
        days: N일간 일정 (예: 7)
        start_time: 시작 시간 HH:MM (예: 19:00). from_date와 합쳐서 RFC3339 생성
        end_time: 종료 시간 HH:MM (예: 20:00). 생략시 start_time+1시간
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
    # ===== action 별칭 변환 =====
    if service == 'gmail' and action == 'list':
        action = 'search'
        if not query:
            query = 'in:inbox'

    args = _base_args() + [service, action]

    # =================================================================
    #  서비스별 positional args + flags 조립
    #  각 서비스 블록 안에서만 해당 서비스의 플래그를 추가하므로
    #  다른 서비스의 파라미터가 섞일 수 없음
    # =================================================================

    if service == 'calendar':
        _build_calendar(args, action, from_date, to_date, today, tomorrow,
                        days, start_time, end_time, summary, description,
                        location, attendees, query, item_id)

    elif service == 'gmail':
        _build_gmail(args, action, query, to_email, cc, subject, body, item_id)

    elif service == 'drive':
        _build_drive(args, action, query, item_id)

    elif service == 'tasks':
        _build_tasks(args, action, list_id, item_id, title, notes, due)

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


# =====================================================================
#  서비스별 CLI 조립 함수
# =====================================================================

def _build_calendar(
    args: list[str], action: str,
    from_date: str, to_date: str, today: bool, tomorrow: bool,
    days: int, start_time: str, end_time: str,
    summary: str, description: str, location: str, attendees: str,
    query: str, item_id: str,
) -> None:
    is_query = action in ('list', 'search')
    is_date_only = lambda d: bool(re.match(r'^\d{4}-\d{2}-\d{2}$', d))

    # --- positional args ---
    if action in ('create', 'update', 'delete', 'get'):
        args.append('primary')
        if action in ('update', 'delete', 'get') and item_id:
            args.append(item_id)
    elif action == 'search' and query:
        args.append(query)

    # --- start_time/end_time → from_date/to_date 합성 ---
    if start_time and from_date and 'T' not in from_date:
        from_date = _merge_time(from_date, start_time, GOG_TIMEZONE)
        end = end_time or _auto_end_time(start_time)
        to_date = _merge_time(to_date or from_date.split('T')[0], end, GOG_TIMEZONE)

    from_date = _ensure_tz(from_date)
    to_date = _ensure_tz(to_date)

    # --- 날짜 플래그 ---
    if today:
        if is_query:
            args.append('--today')
        else:
            today_str = date.today().isoformat()
            if start_time:
                args.append(f'--from={_merge_time(today_str, start_time, GOG_TIMEZONE)}')
                end = end_time or _auto_end_time(start_time)
                args.append(f'--to={_merge_time(today_str, end, GOG_TIMEZONE)}')
            else:
                args.extend([f'--from={today_str}', f'--to={today_str}', '--all-day'])
    elif tomorrow:
        if is_query:
            args.append('--tomorrow')
        else:
            tmrw_str = (date.today() + timedelta(days=1)).isoformat()
            if start_time:
                args.append(f'--from={_merge_time(tmrw_str, start_time, GOG_TIMEZONE)}')
                end = end_time or _auto_end_time(start_time)
                args.append(f'--to={_merge_time(tmrw_str, end, GOG_TIMEZONE)}')
            else:
                args.extend([f'--from={tmrw_str}', f'--to={tmrw_str}', '--all-day'])
    elif from_date:
        if not is_query and is_date_only(from_date):
            args.extend([f'--from={from_date}', f'--to={to_date or from_date}', '--all-day'])
        else:
            args.append(f'--from={from_date}')
            if to_date:
                if is_query and from_date == to_date:
                    next_day = (date.fromisoformat(to_date) + timedelta(days=1)).isoformat()
                    args.append(f'--to={next_day}')
                    logger.info('gog: adjusted --to=%s → --to=%s (exclusive end)', to_date, next_day)
                else:
                    args.append(f'--to={to_date}')
            elif is_query:
                next_day = (date.fromisoformat(from_date) + timedelta(days=1)).isoformat()
                args.append(f'--to={next_day}')
    elif days > 0:
        args.append(f'--days={days}')

    # --- create/update 플래그 ---
    if action in ('create', 'update'):
        if summary:
            args.append(f'--summary={summary}')
        if description:
            args.append(f'--description={description}')
        if location:
            args.append(f'--location={location}')
        if attendees:
            args.append(f'--attendees={attendees}')


def _build_gmail(
    args: list[str], action: str,
    query: str, to_email: str, cc: str, subject: str, body: str,
    item_id: str,
) -> None:
    # --- positional args ---
    if action == 'get' and item_id:
        args.append(item_id)
    elif action == 'search' and query:
        args.append(query)

    # --- send 플래그 ---
    if action == 'send':
        if to_email:
            args.append(f'--to={to_email}')
        if cc:
            args.append(f'--cc={cc}')
        if subject:
            args.append(f'--subject={subject}')
        if body:
            args.append(f'--body={body}')


def _build_drive(
    args: list[str], action: str,
    query: str, item_id: str,
) -> None:
    # --- positional args ---
    if action == 'search' and query:
        args.append(query)
    elif action in ('get', 'download', 'delete') and item_id:
        args.append(item_id)

    # --- ls --query 플래그 ---
    if action == 'ls' and query:
        args.append(f'--query={query}')


def _build_tasks(
    args: list[str], action: str,
    list_id: str, item_id: str,
    title: str, notes: str, due: str,
) -> None:
    # --- positional args ---
    if action in ('list', 'add', 'create') and list_id:
        args.append(list_id)
    elif action in ('get', 'done', 'delete', 'update') and list_id:
        args.append(list_id)
        if item_id:
            args.append(item_id)

    # --- add/create/update 플래그 ---
    if action in ('add', 'create', 'update'):
        if title:
            args.append(f'--title={title}')
        if notes:
            args.append(f'--notes={notes}')
        if due:
            args.append(f'--due={due}')
