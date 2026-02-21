"""Agent tools: search, web_fetch, search_and_read, gog."""

import asyncio
import os
import random

import httpx
import trafilatura

from agent import agent

SEARXNG_URL = os.getenv('SEARXNG_URL', 'http://searxng:8080')
GOG_PATH = os.getenv('GOG_PATH', '/app/gog')
GOG_ACCOUNT = os.getenv('GOG_ACCOUNT', '')

_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
]


def _random_headers() -> dict[str, str]:
    return {
        'User-Agent': random.choice(_USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
    }


async def _fetch_with_playwright(url: str) -> str | None:
    """Playwright 헤드리스 크롬으로 페이지 렌더링 후 본문 추출."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                locale='ko-KR',
            )
            page = await context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            # JS 렌더링 대기
            await page.wait_for_timeout(2000)
            html = await page.content()
            await browser.close()
        return trafilatura.extract(html) if html else None
    except Exception:
        return None


async def _fetch_and_extract(url: str) -> str:
    """2-Tier 페칭: httpx+trafilatura → Playwright 폴백."""
    # Tier 1: httpx + trafilatura
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=30, headers=_random_headers())
            resp.raise_for_status()
        text = trafilatura.extract(resp.text)
        if text and len(text.strip()) > 100:
            return text
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (403, 406, 429):
            pass  # Tier 2로 폴백
        else:
            return f'HTTP 오류 ({e.response.status_code}): {url}'
    except httpx.RequestError:
        pass  # Tier 2로 폴백

    # Tier 2: Playwright
    text = await _fetch_with_playwright(url)
    if text and len(text.strip()) > 50:
        return text

    return f'본문을 추출할 수 없습니다: {url}'


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
    """웹페이지의 본문 텍스트를 추출합니다."""
    text = await _fetch_and_extract(url)
    if len(text) > 8000:
        text = text[:8000] + '\n... (잘림)'
    return text


@agent.tool_plain
async def search_and_read(query: str) -> str:
    """웹 검색 후 상위 결과들의 본문을 읽어옵니다."""
    # 검색
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f'{SEARXNG_URL}/search',
            params={'q': query, 'format': 'json'},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    results = data.get('results', [])[:3]
    if not results:
        return '검색 결과가 없습니다.'

    # 상위 3개 본문 병렬 읽기
    async def _read(r: dict) -> str:
        body = await _fetch_and_extract(r['url'])
        if len(body) > 3000:
            body = body[:3000] + '\n... (잘림)'
        return f"## {r['title']}\nURL: {r['url']}\n\n{body}"

    bodies = await asyncio.gather(*[_read(r) for r in results])
    return '\n\n---\n\n'.join(bodies)


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
