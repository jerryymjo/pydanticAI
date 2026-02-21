"""PydanticAI agent configuration."""

import os
from datetime import date

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import InlineDefsJsonSchemaTransformer
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

VLLM_BASE_URL = os.getenv('VLLM_BASE_URL', 'http://vllm:8000/v1')
VLLM_MODEL = os.getenv('VLLM_MODEL', 'mesolitica/Qwen2.5-72B-Instruct-FP8')
SYSTEM_PROMPT = os.getenv(
    'SYSTEM_PROMPT',
    '너는 자비스다. 한국어로 답하라. 도구를 적극적으로 활용해라.\n'
    '일정, 이메일, 드라이브, 할일 등 Google 관련 요청에는 반드시 gog 도구를 사용해라.\n'
    '날짜 계산(다음주 금요일, 3일 후 등)은 반드시 date_calc 도구를 사용해라. 절대 직접 계산하지 마라.\n'
    '추측하거나 지어내지 말고, 항상 도구를 호출하여 실제 데이터를 가져와라.',
)

model = OpenAIChatModel(
    VLLM_MODEL,
    provider=OpenAIProvider(base_url=VLLM_BASE_URL, api_key='dummy'),
    profile=OpenAIModelProfile(
        json_schema_transformer=InlineDefsJsonSchemaTransformer,
        openai_supports_strict_tool_definition=False,
        openai_supports_tool_choice_required=True,
    ),
)


def sliding_window(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Keep only the most recent 20 messages. Preserve the first 2 (system context)."""
    if len(messages) <= 20:
        return messages
    return messages[:2] + messages[-18:]


agent = Agent(
    model,
    system_prompt=SYSTEM_PROMPT,
    history_processors=[sliding_window],
)


WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일']


@agent.system_prompt
def dynamic_date() -> str:
    today = date.today()
    wd = WEEKDAYS[today.weekday()]
    return f'오늘: {today.isoformat()} ({wd}요일)'
