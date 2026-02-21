"""Google tools: gog (Gmail, Calendar, Chat, Drive, Docs, Sheets, Tasks)."""

import asyncio
import logging
import os

from agent import agent

logger = logging.getLogger(__name__)

GOG_PATH = os.getenv('GOG_PATH', '/app/gog')
GOG_ACCOUNT = os.getenv('GOG_ACCOUNT', '')


@agent.tool_plain
async def gog(command: str) -> str:
    """Google 서비스 CLI. 명령어와 플래그를 문자열로 전달합니다.

    캘린더:
      'calendar list' - 오늘 일정
      'calendar list --tomorrow' - 내일 일정
      'calendar list --week' - 이번 주 일정
      'calendar list --days=3' - 앞으로 3일 일정
      'calendar list --from=2026-02-25 --to=2026-02-28' - 특정 기간 일정
    Gmail:
      'gmail list' - 받은편지함
      'gmail search "from:someone subject:hello"' - 검색
    드라이브: 'drive list', 'drive search "keyword"'
    할일: 'tasks list'

    주의: 시간 필터는 반드시 --플래그로 전달하세요 (예: --tomorrow, --week).
    """
    args = [GOG_PATH]
    if GOG_ACCOUNT:
        args.append(f'--account={GOG_ACCOUNT}')
    args.extend(['--no-input', '--json'])
    args.extend(command.split())
    logger.info('gog tool called: %s', ' '.join(args))
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode()
    if proc.returncode != 0:
        err = stderr.decode()
        logger.error('gog failed (rc=%d): %s', proc.returncode, err)
        output += f'\nError: {err}'
    if len(output) > 4000:
        output = output[:4000] + '\n... (잘림)'
    logger.info('gog result: %d chars, rc=%d', len(output), proc.returncode)
    return output
