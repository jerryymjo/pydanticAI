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
_BASE_PROMPT = os.getenv(
    'SYSTEM_PROMPT',
    '너는 자비스다. 한국어로 답하라. 도구를 적극적으로 활용해라.',
)
SYSTEM_PROMPT = f'{_BASE_PROMPT}\n오늘 날짜: {date.today().isoformat()}'

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
