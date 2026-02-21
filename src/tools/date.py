"""Date tools: date_calc for accurate date arithmetic."""

import logging
import re
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from agent import agent

logger = logging.getLogger(__name__)

WEEKDAYS_KO = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
WEEKDAY_MAP = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
    '월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6,
    '월요일': 0, '화요일': 1, '수요일': 2, '목요일': 3,
    '금요일': 4, '토요일': 5, '일요일': 6,
}


def _next_weekday(today: date, target_wd: int) -> date:
    """Return the date of the next occurrence of target weekday (0=Mon)."""
    days_ahead = target_wd - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def _fmt(d: date) -> str:
    return f'{d.isoformat()} ({WEEKDAYS_KO[d.weekday()]})'


def _apply_offset(base: date, n: int, unit: str) -> date:
    if unit.startswith('day') or unit == '일':
        return base + timedelta(days=n)
    if unit.startswith('week') or unit == '주':
        return base + timedelta(weeks=n)
    if unit.startswith('month') or unit == '개월':
        return base + relativedelta(months=n)
    if unit.startswith('year') or unit == '년':
        return base + relativedelta(years=n)
    raise ValueError(f'unknown unit: {unit}')


def _calc(expression: str) -> str:
    today = date.today()
    expr = expression.strip().lower()

    # "today" / "오늘"
    if expr in ('today', '오늘'):
        return _fmt(today)

    # "tomorrow" / "내일"
    if expr in ('tomorrow', '내일'):
        return _fmt(today + timedelta(days=1))

    # "yesterday" / "어제"
    if expr in ('yesterday', '어제'):
        return _fmt(today - timedelta(days=1))

    # "YYYY-MM-DD + N days/weeks/months/years" (base date + offset)
    m = re.match(
        r'^(\d{4}-\d{2}-\d{2})\s*([+-])\s*(\d+)\s*(days?|weeks?|months?|years?|일|주|개월|년)$',
        expr,
    )
    if m:
        base = date.fromisoformat(m.group(1))
        sign = 1 if m.group(2) == '+' else -1
        n = sign * int(m.group(3))
        return _fmt(_apply_offset(base, n, m.group(4)))

    # "+N days/weeks/months/years" or "-N ..." (from today)
    m = re.match(r'^([+-]?\d+)\s*(days?|weeks?|months?|years?|일|주|개월|년)$', expr)
    if m:
        n = int(m.group(1))
        return _fmt(_apply_offset(today, n, m.group(2)))

    # "next/this friday" / "다음주 금요일" / "이번주 금요일"
    m = re.match(r'^(next|this|다음주?|이번주?)\s+(\w+)$', expr)
    if m:
        prefix = m.group(1)
        target_wd = WEEKDAY_MAP.get(m.group(2))
        if target_wd is not None:
            if prefix in ('this', '이번', '이번주'):
                # This week: find the target weekday in current week (Mon-Sun)
                days_since_monday = today.weekday()
                this_monday = today - timedelta(days=days_since_monday)
                d = this_monday + timedelta(days=target_wd)
            else:
                # Next week: find the target weekday in next week
                days_until_next_monday = 7 - today.weekday()
                next_monday = today + timedelta(days=days_until_next_monday)
                d = next_monday + timedelta(days=target_wd)
            return _fmt(d)

    # "YYYY-MM-DD" (weekday lookup)
    m = re.match(r'^(\d{4}-\d{2}-\d{2})(?:\s+(?:weekday|요일|무슨\s*요일))?$', expr)
    if not m:
        m = re.match(r'^(?:weekday\s+(?:of\s+)?)?(\d{4}-\d{2}-\d{2})$', expr)
    if m:
        return _fmt(date.fromisoformat(m.group(1)))

    # "days until YYYY-MM-DD" / "며칠 남 YYYY-MM-DD"
    m = re.match(r'^(?:days?\s+(?:until|to|till)|며칠\s*(?:남|뒤))\s+(\d{4}-\d{2}-\d{2})$', expr)
    if m:
        d = date.fromisoformat(m.group(1))
        delta = (d - today).days
        return f'{abs(delta)}일 ({"후" if delta >= 0 else "전"})'

    return f'식을 이해할 수 없습니다: {expression}. 예: "next friday", "+3 days", "2026-03-15", "2026-02-21 + 7 days", "다음주 목요일"'


@agent.tool_plain
def date_calc(expression: str) -> str:
    """날짜를 계산합니다. 날짜 관련 질문에는 반드시 이 도구를 사용하세요.

    예:
      'today' / '오늘' - 오늘 날짜와 요일
      'tomorrow' / '내일' - 내일
      'next friday' / '다음주 금요일' - 다음주 특정 요일
      '+3 days' / '+2 weeks' / '+1 months' - N일/주/개월 후
      '-7 days' - 7일 전
      '2026-12-25' - 특정 날짜의 요일
    """
    logger.info('date_calc tool called: %s', expression)
    result = _calc(expression)
    logger.info('date_calc result: %s', result)
    return result
