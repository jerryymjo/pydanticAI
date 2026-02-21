"""Naver tools: news_search for Korean news via Naver Search API."""

import html as html_mod
import logging
import os

import httpx

from agent import agent

logger = logging.getLogger(__name__)

NAVER_CLIENT_ID = os.getenv('NAVER_CLIENT_ID', '')
NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET', '')


@agent.tool_plain
async def news_search(query: str) -> str:
    """네이버 뉴스 검색. 최신 한국 뉴스를 검색합니다.

    예: '삼성전자 실적', '날씨 서울', '대통령 기자회견'
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return '네이버 API 키가 설정되지 않았습니다.'
    logger.info('news_search tool called: %s', query)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            'https://openapi.naver.com/v1/search/news.json',
            params={'query': query, 'display': 5, 'sort': 'date'},
            headers={
                'X-Naver-Client-Id': NAVER_CLIENT_ID,
                'X-Naver-Client-Secret': NAVER_CLIENT_SECRET,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    items = data.get('items', [])
    if not items:
        return '뉴스 검색 결과가 없습니다.'
    results = []
    for item in items:
        title = html_mod.unescape(item['title'].replace('<b>', '').replace('</b>', ''))
        desc = html_mod.unescape(item['description'].replace('<b>', '').replace('</b>', ''))
        results.append(f"**{title}**\n{item['link']}\n{desc}")
    output = '\n\n'.join(results)
    logger.info('news_search result: %d items', len(items))
    return output
