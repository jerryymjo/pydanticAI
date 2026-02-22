"""Shared helpers for Google (gog) service tools."""

import asyncio
import logging
import os

GOG_PATH = os.getenv('GOG_PATH', '/app/gog')
GOG_ACCOUNT = os.getenv('GOG_ACCOUNT', '')
GOG_TIMEZONE = os.getenv('GOG_TIMEZONE', '+09:00')  # KST

logger = logging.getLogger(__name__)


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


async def _run_and_format(service: str, action: str, args: list[str]) -> str:
    """실행 + 에러 시 --help 첨부 + 4000자 잘림."""
    logger.info('gog %s %s: %s', service, action, ' '.join(args))
    stdout, stderr, rc = await _run_gog(args)
    output = stdout
    if rc != 0:
        logger.error('gog %s %s failed (rc=%d): %s', service, action, rc, stderr)
        help_args = [GOG_PATH, service, action, '--help']
        help_out, _, _ = await _run_gog(help_args)
        output = f'Error: {stderr}\n\n--- 사용법 ({service} {action}) ---\n{help_out}'
    if len(output) > 4000:
        output = output[:4000] + '\n... (잘림)'
    logger.info('gog %s %s result: %d chars, rc=%d', service, action, len(output), rc)
    return output
