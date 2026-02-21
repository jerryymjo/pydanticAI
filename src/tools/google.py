"""Google tools: gog (Gmail, Calendar, Chat, Drive, Docs, Sheets, Tasks)."""

import asyncio
import logging
import os
import re
from datetime import date, timedelta

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
async def gog(command: str) -> str:
    """Google 서비스 CLI (Gmail, Calendar, Drive, Tasks 등).

    캘린더:
      'calendar list --today' - 오늘 일정
      'calendar list --tomorrow' - 내일 일정
      'calendar list --from=2026-02-25 --to=2026-02-26' - 특정 기간 일정
      'calendar list --days=7' - 앞으로 7일간 일정

    기타:
      'gmail list' - 이메일 목록
      'drive list' - 드라이브 파일
      'tasks list' - 할일 목록

    주의: --date 플래그는 없습니다. 날짜 조회는 반드시 --from/--to 또는 --today/--tomorrow를 사용하세요.
    명령어가 실패하면 사용법이 자동으로 표시됩니다.
    """
    parts = command.split()
    # Normalize space-separated flags to = format: --from 2026-01-01 → --from=2026-01-01
    normalized = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and parts[i] in ('--from', '--to') and re.match(r'^\d{4}-\d{2}-\d{2}$', parts[i + 1]):
            normalized.append(f'{parts[i]}={parts[i + 1]}')
            i += 2
        else:
            normalized.append(parts[i])
            i += 1
    parts = normalized
    # Fix: Google Calendar API --to is exclusive.
    # If --from and --to are the same date, bump --to by 1 day.
    from_val = to_val = None
    for p in parts:
        m = re.match(r'^--from=(\d{4}-\d{2}-\d{2})$', p)
        if m:
            from_val = m.group(1)
        m = re.match(r'^--to=(\d{4}-\d{2}-\d{2})$', p)
        if m:
            to_val = m.group(1)
    if from_val and to_val and from_val == to_val:
        next_day = (date.fromisoformat(to_val) + timedelta(days=1)).isoformat()
        parts = [f'--to={next_day}' if p == f'--to={to_val}' else p for p in parts]
        logger.info('gog: adjusted --to=%s → --to=%s (exclusive end)', to_val, next_day)
    args = _base_args() + parts
    logger.info('gog tool called: %s', ' '.join(args))
    stdout, stderr, rc = await _run_gog(args)
    output = stdout
    if rc != 0:
        logger.error('gog failed (rc=%d): %s', rc, stderr)
        # Auto-attach help for the subcommand so LLM can self-correct
        help_args = [GOG_PATH] + parts[:2] + ['--help']
        help_out, _, _ = await _run_gog(help_args)
        output = f'Error: {stderr}\n\n--- 사용법 ({" ".join(parts[:2])}) ---\n{help_out}'
    if len(output) > 4000:
        output = output[:4000] + '\n... (잘림)'
    logger.info('gog result: %d chars, rc=%d', len(output), rc)
    return output
