"""Google Calendar tool."""

import re
from datetime import date, timedelta

from agent import agent
from tools._gog import (
    GOG_TIMEZONE,
    _auto_end_time,
    _base_args,
    _ensure_tz,
    _merge_time,
    _run_and_format,
)


@agent.tool_plain
async def calendar(
    action: str,
    from_date: str = '',
    to_date: str = '',
    today: bool = False,
    tomorrow: bool = False,
    days: int = 0,
    start_time: str = '',
    end_time: str = '',
    summary: str = '',
    description: str = '',
    location: str = '',
    attendees: str = '',
    query: str = '',
    item_id: str = '',
) -> str:
    """Google Calendar CLI.

    Args:
        action: list, create, update, delete, get, search
        from_date: YYYY-MM-DD 시작일
        to_date: YYYY-MM-DD 종료일 (생략시 from_date 다음날 자동설정)
        today: 오늘 일정
        tomorrow: 내일 일정
        days: N일간 일정 (예: 7)
        start_time: 시작 시간 HH:MM (예: 19:00). from_date와 합쳐서 RFC3339 생성
        end_time: 종료 시간 HH:MM (예: 20:00). 생략시 start_time+1시간
        summary: 일정 제목 (create/update)
        description: 일정 설명 (create/update)
        location: 일정 장소 (create/update)
        attendees: 참석자 이메일 (쉼표 구분)
        query: search 검색어
        item_id: eventId (update/delete/get)
    """
    args = _base_args() + ['calendar', action]

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

    return await _run_and_format('calendar', action, args)
