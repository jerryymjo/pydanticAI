"""LLM-based insight extractor — runs every 3 turns to learn user habits."""

import json
import logging
import os

import httpx

from memory import qdrant_store as qs
from memory.embeddings import embed_text

logger = logging.getLogger(__name__)

VLLM_BASE_URL = os.getenv('VLLM_BASE_URL', 'http://vllm:8000/v1')
VLLM_MODEL = os.getenv('VLLM_MODEL', 'Qwen/Qwen3-32B-FP8')

EXTRACTION_PROMPT = """\
다음 대화에서 사용자(제리)에 대한 새로운 인사이트를 추출해라.
카테고리: preference(선호), habit(습관), fact(사실), relationship(관계)

대화:
User: {user_text}
Assistant: {assistant_text}

JSON 배열로 응답해라. 인사이트가 없으면 빈 배열 [].
각 항목: {{"content": "인사이트 텍스트", "category": "카테고리", "confidence": 0.0~1.0}}
/no_think"""


async def maybe_extract_insights(
    chat_id: int, user_text: str, assistant_text: str
) -> None:
    """Ask LLM to extract user insights from the conversation turn."""
    try:
        prompt = EXTRACTION_PROMPT.format(
            user_text=user_text, assistant_text=assistant_text
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f'{VLLM_BASE_URL}/chat/completions',
                json={
                    'model': VLLM_MODEL,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.1,
                    'max_tokens': 512,
                },
            )
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content'].strip()

        # Parse JSON from response (handle markdown code blocks)
        if '```' in content:
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
        content = content.strip()

        insights = json.loads(content)
        if not isinstance(insights, list):
            return

        for insight in insights:
            if not isinstance(insight, dict) or 'content' not in insight:
                continue
            text = insight['content']
            category = insight.get('category', 'fact')
            confidence = float(insight.get('confidence', 0.5))

            if confidence < 0.3:
                continue

            vector = await embed_text(text)
            # Check for duplicates — if very similar memory exists, skip
            existing = qs.search_memories(vector, limit=1)
            if existing and existing[0].get('score', 0) > 0.85:
                logger.debug('Skipping duplicate insight: %s', text)
                continue

            qs.upsert_memory(vector, text, category, confidence)
            logger.info('Extracted insight: [%s] %s (%.2f)', category, text, confidence)

    except Exception:
        logger.error('Insight extraction failed', exc_info=True)
