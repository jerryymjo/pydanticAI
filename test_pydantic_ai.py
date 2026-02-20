"""PydanticAI + vLLM 테스트: 기본 대화 + 도구 호출"""
import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.profiles import InlineDefsJsonSchemaTransformer
from pydantic_ai.profiles.openai import OpenAIModelProfile

# === 1. 모델 설정 ===
model = OpenAIChatModel(
    'mesolitica/Qwen2.5-72B-Instruct-FP8',
    provider=OpenAIProvider(
        base_url='http://192.168.1.242:8000/v1',
        api_key='dummy',
    ),
    profile=OpenAIModelProfile(
        json_schema_transformer=InlineDefsJsonSchemaTransformer,
        openai_supports_strict_tool_definition=False,
        openai_supports_tool_choice_required=True,
    ),
)

# === 2. 에이전트 (도구 포함) ===
agent = Agent(
    model,
    system_prompt='너는 자비스다. 한국어로만 답하라. 도구를 적극적으로 활용해라.',
)

@agent.tool_plain
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다."""
    # 테스트용 더미 데이터
    return f"{city}: 맑음, 기온 5°C, 습도 40%"

@agent.tool_plain
def calculate(expression: str) -> str:
    """수학 계산을 수행합니다."""
    try:
        result = eval(expression)
        return f"계산 결과: {expression} = {result}"
    except Exception as e:
        return f"계산 오류: {e}"


async def main():
    print("=" * 60)
    print("테스트 1: 기본 대화 (도구 호출 없이)")
    print("=" * 60)
    try:
        result = await agent.run("안녕! 너는 누구야?")
        print(f"응답: {result.output}")
        print(f"토큰: {result.usage()}")
    except Exception as e:
        print(f"에러: {e}")

    print()
    print("=" * 60)
    print("테스트 2: 도구 호출 (날씨)")
    print("=" * 60)
    try:
        result = await agent.run("서울 날씨 어때?")
        print(f"응답: {result.output}")
        print(f"토큰: {result.usage()}")
    except Exception as e:
        print(f"에러: {e}")

    print()
    print("=" * 60)
    print("테스트 3: 도구 호출 (계산)")
    print("=" * 60)
    try:
        result = await agent.run("123 * 456 + 789 계산해줘")
        print(f"응답: {result.output}")
        print(f"토큰: {result.usage()}")
    except Exception as e:
        print(f"에러: {e}")

    print()
    print("=" * 60)
    print("테스트 4: 스트리밍")
    print("=" * 60)
    try:
        async with agent.run_stream("대한민국의 수도에 대해 3문장으로 설명해줘") as stream:
            print("스트리밍: ", end="", flush=True)
            async for chunk in stream.stream_text(delta=True):
                print(chunk, end="", flush=True)
            print()
            print(f"토큰: {stream.usage()}")
    except Exception as e:
        print(f"에러: {e}")


if __name__ == "__main__":
    asyncio.run(main())
