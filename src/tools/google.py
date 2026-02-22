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

# Whitelist: (service, action) → valid parameter names
# Params not in the set are silently dropped before CLI assembly.
_VALID_PARAMS: dict[tuple[str, str], set[str]] = {
    # calendar
    ('calendar', 'list'): {'from_date', 'to_date', 'today', 'tomorrow', 'days'},
    ('calendar', 'search'): {'query', 'from_date', 'to_date'},
    ('calendar', 'create'): {'from_date', 'to_date', 'start_time', 'end_time', 'summary', 'description', 'location', 'attendees', 'today', 'tomorrow'},
    ('calendar', 'update'): {'item_id', 'from_date', 'to_date', 'start_time', 'end_time', 'summary', 'description', 'location', 'attendees', 'today', 'tomorrow'},
    ('calendar', 'delete'): {'item_id'},
    ('calendar', 'get'): {'item_id'},
    # gmail
    ('gmail', 'search'): {'query'},
    ('gmail', 'send'): {'to_email', 'cc', 'subject', 'body'},
    ('gmail', 'get'): {'item_id'},
    # drive
    ('drive', 'ls'): {'query'},
    ('drive', 'search'): {'query'},
    ('drive', 'get'): {'item_id'},
    ('drive', 'download'): {'item_id'},
    ('drive', 'upload'): set(),
    ('drive', 'mkdir'): set(),
    ('drive', 'delete'): {'item_id'},
    # tasks
    ('tasks', 'lists'): set(),
    ('tasks', 'list'): {'list_id'},
    ('tasks', 'add'): {'list_id', 'title', 'notes', 'due'},
    ('tasks', 'create'): {'list_id', 'title', 'notes', 'due'},
    ('tasks', 'get'): {'list_id', 'item_id'},
    ('tasks', 'update'): {'list_id', 'item_id', 'title', 'notes', 'due'},
    ('tasks', 'done'): {'list_id', 'item_id'},
    ('tasks', 'delete'): {'list_id', 'item_id'},
}


def _ensure_tz(dt_str: str) -> str:
    """시간이 포함된 날짜에 타임존이 없으면 자동 추가."""
    if not dt_str or 'T' not in dt_str:
        return dt_str
    # 이미 타임존이 있으면 그대로 (+, Z)
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
          - gmail: search, send, get
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
    # ===== Whitelist filter: drop params invalid for this service+action =====
    valid = _VALID_PARAMS.get((service, action))
    if valid is not None:
        if 'from_date' not in valid: from_date = ''
        if 'to_date' not in valid: to_date = ''
        if 'today' not in valid: today = False
        if 'tomorrow' not in valid: tomorrow = False
        if 'days' not in valid: days = 0
        if 'start_time' not in valid: start_time = ''
        if 'end_time' not in valid: end_time = ''
        if 'summary' not in valid: summary = ''
        if 'description' not in valid: description = ''
        if 'location' not in valid: location = ''
        if 'attendees' not in valid: attendees = ''
        if 'to_email' not in valid: to_email = ''
        if 'cc' not in valid: cc = ''
        if 'subject' not in valid: subject = ''
        if 'body' not in valid: body = ''
        if 'title' not in valid: title = ''
        if 'notes' not in valid: notes = ''
        if 'due' not in valid: due = ''
        if 'list_id' not in valid: list_id = ''
        if 'query' not in valid: query = ''
        if 'item_id' not in valid: item_id = ''

    # start_time/end_time이 있으면 from_date/to_date에 합성
    if start_time and from_date and 'T' not in from_date:
        from_date = f'{from_date}T{start_time}:00'
        if end_time:
            to_date = f'{(to_date or from_date.split("T")[0])}T{end_time}:00'
        else:
            # end_time 생략 시 start_time + 1시간
            h, m = start_time.split(':')
            to_date = f'{(to_date or from_date.split("T")[0])}T{int(h)+1:02d}:{m}:00'

    from_date = _ensure_tz(from_date)
    to_date = _ensure_tz(to_date)
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
    is_date_only = lambda d: bool(re.match(r'^\d{4}-\d{2}-\d{2}$', d))
    is_query = action in ('list', 'search')

    if today:
        if is_query:
            args.append('--today')
        else:
            # create/update: --today 미지원 → 오늘 날짜로 변환
            today_str = date.today().isoformat()
            if start_time:
                from_date = f'{today_str}T{start_time}:00{GOG_TIMEZONE}'
                if end_time:
                    to_date = f'{today_str}T{end_time}:00{GOG_TIMEZONE}'
                else:
                    h, m = start_time.split(':')
                    to_date = f'{today_str}T{int(h)+1:02d}:{m}:00{GOG_TIMEZONE}'
                args.append(f'--from={from_date}')
                args.append(f'--to={to_date}')
            else:
                args.append(f'--from={today_str}')
                args.append(f'--to={today_str}')
                args.append('--all-day')
    elif tomorrow:
        if is_query:
            args.append('--tomorrow')
        else:
            tmrw_str = (date.today() + timedelta(days=1)).isoformat()
            if start_time:
                from_date = f'{tmrw_str}T{start_time}:00{GOG_TIMEZONE}'
                if end_time:
                    to_date = f'{tmrw_str}T{end_time}:00{GOG_TIMEZONE}'
                else:
                    h, m = start_time.split(':')
                    to_date = f'{tmrw_str}T{int(h)+1:02d}:{m}:00{GOG_TIMEZONE}'
                args.append(f'--from={from_date}')
                args.append(f'--to={to_date}')
            else:
                args.append(f'--from={tmrw_str}')
                args.append(f'--to={tmrw_str}')
                args.append('--all-day')
    elif from_date:
        # create/update에서 날짜만 주면 → 종일 일정
        if not is_query and is_date_only(from_date):
            args.append(f'--from={from_date}')
            args.append(f'--to={to_date if to_date else from_date}')
            args.append('--all-day')
        else:
            args.append(f'--from={from_date}')
            if to_date:
                # list/search: exclusive end-date 보정
                if is_query and from_date == to_date:
                    next_day = (date.fromisoformat(to_date) + timedelta(days=1)).isoformat()
                    args.append(f'--to={next_day}')
                    logger.info('gog: adjusted --to=%s → --to=%s (exclusive end)', to_date, next_day)
                else:
                    args.append(f'--to={to_date}')
            elif is_query:
                # list/search: from만 있으면 하루치 자동 설정
                next_day = (date.fromisoformat(from_date) + timedelta(days=1)).isoformat()
                args.append(f'--to={next_day}')
    elif days > 0 and service == 'calendar':
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
