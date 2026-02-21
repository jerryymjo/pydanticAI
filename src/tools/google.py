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
    from_date: str = '',
    to_date: str = '',
    today: bool = False,
    tomorrow: bool = False,
    days: int = 0,
    query: str = '',
) -> str:
    """Google 서비스 CLI.

    Args:
        service: calendar, gmail, drive, tasks
        action: list, get, send, create, delete
        from_date: YYYY-MM-DD 시작일 (캘린더)
        to_date: YYYY-MM-DD 종료일 (캘린더, 생략시 from_date 다음날 자동설정)
        today: True면 오늘 일정 조회
        tomorrow: True면 내일 일정 조회
        days: N일간 일정 조회 (예: 7)
        query: gmail/drive 검색어 등 추가 인자
    """
    args = _base_args() + [service, action]

    if today:
        args.append('--today')
    elif tomorrow:
        args.append('--tomorrow')
    elif from_date:
        args.append(f'--from={from_date}')
        if to_date:
            # Google Calendar API --to is exclusive.
            # If from and to are same date, bump to by 1 day.
            if from_date == to_date:
                next_day = (date.fromisoformat(to_date) + timedelta(days=1)).isoformat()
                args.append(f'--to={next_day}')
                logger.info('gog: adjusted --to=%s → --to=%s (exclusive end)', to_date, next_day)
            else:
                args.append(f'--to={to_date}')
        else:
            # from_date only → single day query
            next_day = (date.fromisoformat(from_date) + timedelta(days=1)).isoformat()
            args.append(f'--to={next_day}')
    elif days > 0:
        args.append(f'--days={days}')

    if query:
        args.extend(query.split())

    logger.info('gog tool called: %s', ' '.join(args))
    stdout, stderr, rc = await _run_gog(args)
    output = stdout
    if rc != 0:
        logger.error('gog failed (rc=%d): %s', rc, stderr)
        # Auto-attach help for the subcommand so LLM can self-correct
        help_args = [GOG_PATH, service, action, '--help']
        help_out, _, _ = await _run_gog(help_args)
        output = f'Error: {stderr}\n\n--- 사용법 ({service} {action}) ---\n{help_out}'
    if len(output) > 4000:
        output = output[:4000] + '\n... (잘림)'
    logger.info('gog result: %d chars, rc=%d', len(output), rc)
    return output
