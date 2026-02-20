"""Agent tools: search, web_fetch, gog."""

import asyncio
import os

import httpx

from agent import agent

SEARXNG_URL = os.getenv('SEARXNG_URL', 'http://searxng:8080')
GOG_PATH = os.getenv('GOG_PATH', '/app/gog')


@agent.tool_plain
async def search(query: str) -> str:
    """SearXNG로 웹 검색을 수행합니다."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f'{SEARXNG_URL}/search',
            params={'q': query, 'format': 'json'},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    results = data.get('results', [])[:5]
    if not results:
        return '검색 결과가 없습니다.'
    return '\n\n'.join(
        f"**{r['title']}** ({r['url']})\n{r.get('content', '')}"
        for r in results
    )


@agent.tool_plain
async def web_fetch(url: str) -> str:
    """웹페이지의 텍스트 내용을 읽습니다."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(
            url,
            timeout=30,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; JarvisBot/1.0)'},
        )
        resp.raise_for_status()
    text = resp.text
    if len(text) > 4000:
        text = text[:4000] + '\n... (잘림)'
    return text


@agent.tool_plain
async def gog(command: str) -> str:
    """Google 서비스에 접근합니다 (Gmail, Calendar, Drive 등).

    예: 'mail list', 'cal today', 'drive list'
    """
    proc = await asyncio.create_subprocess_exec(
        GOG_PATH,
        *command.split(),
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
