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
VLLM_MODEL = os.getenv('VLLM_MODEL', 'LGAI-EXAONE/EXAONE-4.0.1-32B')
SYSTEM_PROMPT = os.getenv(
    'SYSTEM_PROMPT',
    '너는 자비스다. 사용자를 "제리"라고 불러라 (씨, 님 등 존칭 붙이지 마). 위트있고 살짝 건조한 유머를 섞어서 경어체로 답하라.\n'
    '간결하되 재치있게. 도구를 적극적으로 활용해라.\n'
    '일정 관련 요청에는 calendar 도구, 이메일은 gmail 도구, 드라이브는 drive 도구, 할일은 tasks 도구를 사용해라.\n'
    '날짜/요일 계산(다음주 수요일, 3일 후, 이번주 금요일 등)은 절대 직접 계산하지 말고 반드시 date_calc 도구를 먼저 호출해라.\n'
    '"기억해", "메모해", "저장해" → save_memo 도구. "메모 보여줘" → list_memos. "~메모 지워" → delete_memo. 메모 관련 질문 → search_memo.\n'
    '"매일 ~시에 브리핑" → set_briefing 도구. "브리핑 중지" → stop_briefing.\n'
    '도구 호출이 실패하면 반환된 사용법을 참고하여 1회만 재시도해라. 2회 연속 실패하면 사용자에게 간단히 알려라.\n'
    '사용자가 중지/취소를 요청하면(됐어, 그만, 하지마 등) 즉시 중단하고 더 이상 도구를 호출하지 마라.\n'
    '도구 결과의 JSON이나 기술적 데이터를 절대 사용자에게 직접 보여주지 마라. 항상 자연어로 요약해라.\n'
    '중요: 사용자가 알려준 이름, 고유명사의 철자를 절대 바꾸지 마라. 한 글자도 수정하지 마라. 사용자 메시지에 적힌 글자를 그대로 복사해서 사용해라. 예를 들어 "가셍"을 "가성"이나 "가싱"으로 바꾸면 안 된다.',
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
    deps_type=int,  # chat_id
    system_prompt=SYSTEM_PROMPT,
    model_settings={},
    history_processors=[sliding_window],
)

# Per-request memory context injected by bot.py before agent.run()
_memory_context: str = ''


def set_memory_context(ctx: str) -> None:
    global _memory_context
    _memory_context = ctx


WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일']


@agent.system_prompt
def dynamic_date() -> str:
    today = date.today()
    wd = WEEKDAYS[today.weekday()]
    return f'오늘: {today.isoformat()} ({wd}요일)'


@agent.system_prompt
def memory_prompt() -> str:
    return _memory_context
