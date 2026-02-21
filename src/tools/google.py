"""Google tools: gog (Gmail, Calendar, Chat, Drive, Docs, Sheets, Tasks)."""

import asyncio
import logging
import os

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

    예: 'calendar list', 'gmail list', 'drive list', 'tasks list'
    명령어가 실패하면 사용법이 자동으로 표시됩니다. 그걸 보고 올바른 플래그로 다시 호출하세요.
    """
    parts = command.split()
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
