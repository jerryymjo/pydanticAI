"""Web tools: search (unified), web_fetch."""

import asyncio
import html as html_mod
import logging
import os
import random

import httpx
import trafilatura

from agent import agent

logger = logging.getLogger(__name__)

SEARXNG_URL = os.getenv('SEARXNG_URL', 'http://searxng:8080')
NAVER_CLIENT_ID = os.getenv('NAVER_CLIENT_ID', '')
NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET', '')

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


async def _searxng_search(query: str) -> list[dict]:
    """SearXNG 검색 결과 반환."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f'{SEARXNG_URL}/search',
                params={'q': query, 'format': 'json'},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get('results', [])[:5]
    except Exception as e:
        logger.error('SearXNG search failed: %s', e)
        return []


async def _naver_news_search(query: str) -> list[dict]:
    """네이버 뉴스 검색. API 키 없으면 빈 리스트 반환."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                'https://openapi.naver.com/v1/search/news.json',
                params={'query': query, 'display': 3, 'sort': 'date'},
                headers={
                    'X-Naver-Client-Id': NAVER_CLIENT_ID,
                    'X-Naver-Client-Secret': NAVER_CLIENT_SECRET,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        items = data.get('items', [])
        results = []
        for item in items:
            title = html_mod.unescape(item['title'].replace('<b>', '').replace('</b>', ''))
            desc = html_mod.unescape(item['description'].replace('<b>', '').replace('</b>', ''))
            results.append({'title': title, 'url': item['link'], 'content': desc, 'source': 'naver_news'})
        return results
    except Exception as e:
        logger.error('Naver news search failed: %s', e)
        return []


@agent.tool_plain
async def search(query: str, read_content: bool = False) -> str:
    """웹 및 뉴스 통합 검색. read_content=True면 상위 결과 본문도 읽어옵니다."""
    logger.info('search tool called: query=%s, read_content=%s', query, read_content)

    # 1. SearXNG + 네이버 뉴스 병렬 검색
    web_results, news_results = await asyncio.gather(
        _searxng_search(query),
        _naver_news_search(query),
    )

    # 2. 결과 합치기
    all_results = []
    for r in web_results:
        all_results.append(f"**{r['title']}** ({r['url']})\n{r.get('content', '')}")
    if news_results:
        all_results.append('\n📰 **뉴스**')
        for r in news_results:
            all_results.append(f"**{r['title']}** ({r['url']})\n{r['content']}")

    if not all_results:
        return '검색 결과가 없습니다.'

    output = '\n\n'.join(all_results)

    # 3. read_content=True면 상위 3개 본문 병렬 fetch
    if read_content:
        urls_to_read = [r['url'] for r in (web_results + news_results)[:3]]

        async def _read(url: str) -> str:
            body = await _fetch_and_extract(url)
            if len(body) > 3000:
                body = body[:3000] + '\n... (잘림)'
            return f"---\nURL: {url}\n\n{body}"

        bodies = await asyncio.gather(*[_read(u) for u in urls_to_read])
        output += '\n\n' + '\n\n'.join(bodies)

    logger.info('search result: %d web + %d news items', len(web_results), len(news_results))
    return output


@agent.tool_plain
async def web_fetch(url: str) -> str:
    """웹페이지의 본문 텍스트를 추출합니다."""
    logger.info('web_fetch tool called: %s', url)
    text = await _fetch_and_extract(url)
    if len(text) > 8000:
        text = text[:8000] + '\n... (잘림)'
    return text
