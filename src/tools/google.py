"""Google tools: gog (Gmail, Calendar, Chat, Drive, Docs, Sheets, Tasks)."""

import asyncio
import os

from agent import agent

GOG_PATH = os.getenv('GOG_PATH', '/app/gog')
GOG_ACCOUNT = os.getenv('GOG_ACCOUNT', '')


@agent.tool_plain
async def gog(command: str) -> str:
    """Google 서비스에 접근합니다 (Gmail, Calendar, Chat, Drive, Docs, Sheets, Tasks 등).

    예: 'gmail search "from:someone"', 'calendar list', 'drive list', 'tasks list'
    """
    args = [GOG_PATH]
    if GOG_ACCOUNT:
        args.append(f'--account={GOG_ACCOUNT}')
    args.extend(['--no-input', '--json'])
    args.extend(command.split())
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode()
    if proc.returncode != 0:
        output += f'\nError: {stderr.decode()}'
    if len(output) > 4000:
        output = output[:4000] + '\n... (잘림)'
    return output
