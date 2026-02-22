"""Weather tool using wttr.in — no API key required."""

import logging

import httpx

from agent import agent

logger = logging.getLogger(__name__)

_WTTR_URL = 'https://wttr.in'
_DEFAULT_LOCATION = '서울'


@agent.tool_plain
async def weather(location: str = '') -> str:
    """현재 날씨와 3일 예보를 조회합니다. 날씨 관련 질문에 사용하세요.

    Args:
        location: 도시명 (예: "서울", "부산", "제주"). 생략하면 서울.
    """
    loc = location.strip() or _DEFAULT_LOCATION
    logger.info('weather tool called: %s', loc)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f'{_WTTR_URL}/{loc}',
                params={'format': 'j1', 'lang': 'ko'},
                headers={'Accept': 'application/json'},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error('weather fetch failed: %s', e)
        return f'날씨 정보를 가져올 수 없습니다: {e}'

    # Current conditions
    cur = data.get('current_condition', [{}])[0]
    area = data.get('nearest_area', [{}])[0]
    area_name = area.get('areaName', [{}])[0].get('value', loc)

    current = (
        f'📍 {area_name} 현재 날씨\n'
        f'🌡️ {cur.get("temp_C", "?")}°C (체감 {cur.get("FeelsLikeC", "?")}°C)\n'
        f'💧 습도 {cur.get("humidity", "?")}%\n'
        f'💨 바람 {cur.get("windspeedKmph", "?")}km/h\n'
        f'☁️ {cur.get("lang_ko", [{}])[0].get("value", cur.get("weatherDesc", [{}])[0].get("value", ""))}'
    )

    # 3-day forecast
    forecasts = []
    for day in data.get('weather', [])[:3]:
        date_str = day.get('date', '')
        max_t = day.get('maxtempC', '?')
        min_t = day.get('mintempC', '?')
        desc = day.get('hourly', [{}])[4].get('lang_ko', [{}])[0].get('value', '')
        forecasts.append(f'{date_str}: {min_t}~{max_t}°C {desc}')

    forecast_text = '\n'.join(forecasts)
    return f'{current}\n\n📅 3일 예보\n{forecast_text}'
