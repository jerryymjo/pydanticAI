# PydanticAI + vLLM 텔레그램 봇 프로젝트

OpenClaw를 대체할 경량 AI 에이전트 프레임워크 조사 및 테스트 기록.

## 목차

1. [배경: OpenClaw의 문제점](#1-배경-openclaw의-문제점)
2. [대안 프레임워크 조사](#2-대안-프레임워크-조사)
3. [PydanticAI 심층 분석](#3-pydanticai-심층-분석)
4. [vLLM 호환성 이슈 및 해결 상태](#4-vllm-호환성-이슈-및-해결-상태)
5. [테스트 결과](#5-테스트-결과)
6. [추론 엔진 비교 (DGX Spark)](#6-추론-엔진-비교-dgx-spark)
7. [아키텍처 설계](#7-아키텍처-설계)
8. [다음 단계](#8-다음-단계)

---

## 1. 배경: OpenClaw의 문제점

### 하드웨어 환경

- **DGX Spark** (HP ZGX Nano G1n): 192.168.1.242
- GPU: NVIDIA GB10 (Blackwell), 128GB 통합 메모리, aarch64
- 모델: `mesolitica/Qwen2.5-72B-Instruct-FP8`
- vLLM: NGC `nvcr.io/nvidia/vllm:26.01-py3` (v0.13.0)
- 생성 속도: ~2.8 tokens/sec

### OpenClaw 시스템 프롬프트 분석

OpenClaw의 메인 에이전트 (`pi-embedded-CWm3BvmA.js`)를 분석한 결과, 프레임워크가 강제 주입하는 시스템 프롬프트가 **~14,000 토큰**에 달함:

| 섹션 | 소스 위치 (라인) | 내용 |
|------|-----------------|------|
| Tooling | 22917 | 20개+ 내장 도구 설명 |
| Tool Call Style | 22940 | 도구 호출 형식 지시 |
| Safety | 22890 | 안전 가이드라인 |
| CLI Reference | 22947 | CLI 명령어 레퍼런스 |
| Skills | 22956 | 스킬 프롬프트 (searxng, healthcheck 등) |
| Memory | 22957 | 메모리 관리 |
| Self-Update | 22959 | 자기 업데이트 |
| Workspace | 22972 | 워크스페이스 파일 |
| Docs | 22977 | 문서 참조 |
| User Identity | 22994 | 사용자 정보 |
| Messaging | 23000 | 메시징 규칙 |
| Voice | 23008 | 음성 처리 |
| Silent Replies | 23049 | 무응답 처리 |
| Heartbeats | 23050 | 하트비트 |
| Runtime | 23051 | 런타임 정보 |
| **도구 JSON 스키마** | 22784-22809 | 20개+ 도구의 상세 스키마 (~14,000자) |

**총합: ~22,000자 시스템 프롬프트 + ~14,000자 도구 스키마 = ~12,000 입력 토큰**

사용자가 제어할 수 있는 건 IDENTITY.md (~2,500 토큰)뿐이고, 나머지 ~14,000 토큰은 프레임워크 고정 오버헤드.

### 발생한 문제들

#### 1) EXAONE 4.0 32B 시도 및 실패

EXAONE 4.0 32B BF16을 시도했으나 완전히 실패:
- 첫 응답: `"南极结束！是什么可以为您效劳？"` (중국어 출력)
- 두 번째: `"안녕하세요, 영민 조 님!"` (이름 순서 오류 — 텔레그램 라벨 그대로 사용)
- 세 번째: `"JOY보 측량 자비스AI어시스턴트! ... 연마제의 반복된 것에..."` (완전한 환각)
- **원인**: 32B 모델이 17-18K 토큰의 복잡한 영어 시스템 프롬프트를 감당 못함
- BFCL-v3 점수: EXAONE 4.0 32B = 65.2 (비추론), Qwen3-32B = 68.2

#### 2) Qwen 72B 복귀 후에도 문제 지속

- **링크만 나열**: 검색 후 web_fetch로 내용 확인 안 하고 링크 목록만 출력
- **도구 토큰 누출**: `<|im_start|>{"name": "web_fetch"...}` 원시 토큰이 사용자에게 노출
- **4시간 무응답**: web_fetch 완료 후 응답 없이 멈춤
- **피보나치 환각**: 주식 시장 질문에 피보나치 수열로 답변
  - **원인**: OpenClaw 컴팩션(LLM 기반 요약)이 가비지 생성 → 컨텍스트 오염

#### 3) OpenClaw 컴팩션의 한계

- 슬라이딩 윈도우 없음 — LLM 기반 요약만 지원
- 모드: "default" (단일 패스 요약), "safeguard" (청크 요약)
- "none", "truncate", "sliding-window" 옵션 없음
- `enabled: false` 설정 시 컨텍스트 오버플로우에서 세션 리셋
- 2.8 tok/s에서 컴팩션 자체가 수 분의 지연 추가

---

## 2. 대안 프레임워크 조사

### 조사 대상 10개 프레임워크

| 프레임워크 | GitHub Stars | 시스템 프롬프트 | 텔레그램 지원 | 평가 |
|-----------|-------------|---------------|-------------|------|
| **OpenClaw** (현재) | - | ~12,000 tok | 내장 | 너무 무거움 |
| **n3d1117/chatgpt-telegram-bot** | 3,500 | ~200-800 tok | 내장 | 가벼움, 기능 제한 |
| **AstrBot** | 17,000 | ~500-2,000 tok | 내장 | 중간, shell exec 내장 |
| **smolagents** | HuggingFace | ~3,500-4,300 tok | 없음 | ReAct 오버헤드 과다 |
| **PydanticAI** | Pydantic 공식 | **0 tok** (사용자 정의만) | 없음 | 최적 |
| **LiteLLM + Python** | - | ~100 tok | 없음 | 프록시만 |
| **DIY Python** | - | ~200-500 tok | 없음 | 개발량 많음 |

### smolagents 상세 분석

- CodeAgent: Python 코드 생성 방식 (vLLM 도구 파서 우회)
- ToolCallingAgent: JSON 함수 호출 방식
- **ReAct 루프**: 매 메시지당 30-45초 오버헤드 (2.8 tok/s 기준)
- 토큰 스트리밍 없음 (단계별 스트리밍만)
- 대화 메모리/슬라이딩 윈도우 미내장 (Issue #901)
- SmolAgentsTelegram 래퍼: 주말 프로젝트 수준, 사용 불가
- **결론: 2.8 tok/s 하드웨어에서 비현실적**

### 최종 선택: PydanticAI

선택 이유:
1. 프레임워크 시스템 프롬프트 주입 **0 토큰**
2. 도구 호출 파싱/검증 자동
3. 토큰 스트리밍 지원
4. `history_processors`로 슬라이딩 윈도우 구현 가능
5. MIT 라이선스, Pydantic 팀 공식 프로젝트
6. v1.62.0 (2026-02-18 릴리스) — 활발한 개발

---

## 3. PydanticAI 심층 분석

### 버전 정보

- 최신 버전: **1.62.0** (2026-02-18)
- Python 지원: 3.10, 3.11, 3.12, 3.13, 3.14
- 라이선스: MIT

### vLLM 연동 방식

PydanticAI에 전용 vLLM 모델 클래스는 없음. OpenAI 호환 API로 연결:

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.profiles import InlineDefsJsonSchemaTransformer
from pydantic_ai.profiles.openai import OpenAIModelProfile

model = OpenAIChatModel(
    'mesolitica/Qwen2.5-72B-Instruct-FP8',
    provider=OpenAIProvider(
        base_url='http://192.168.1.242:8000/v1',
        api_key='dummy',
    ),
    profile=OpenAIModelProfile(
        json_schema_transformer=InlineDefsJsonSchemaTransformer,  # $defs 문제 해결
        openai_supports_strict_tool_definition=False,              # vLLM strict 미지원
        openai_supports_tool_choice_required=True,                 # vLLM 0.8.3+ 지원
    ),
)
```

### 프로파일 설정 상세

| 설정 | 값 | 이유 |
|------|---|------|
| `json_schema_transformer` | `InlineDefsJsonSchemaTransformer` | 중첩 Pydantic 모델의 `$defs`/`$ref`를 플랫 스키마로 인라인. vLLM의 guided decoding 백엔드(Outlines/xgrammar)가 `$defs` 처리 불가 (vLLM #15035) |
| `openai_supports_strict_tool_definition` | `False` | vLLM이 OpenAI의 strict 모드 미지원 |
| `openai_supports_tool_choice_required` | `True` | vLLM 0.8.3+에서 `tool_choice=required` 지원 (PR #13483) |

### 시스템 프롬프트 오버헤드

| 항목 | OpenClaw | PydanticAI |
|------|---------|------------|
| 프레임워크 주입 프롬프트 | ~14,000 tok | **0 tok** |
| 사용자 시스템 프롬프트 | ~2,500 tok (IDENTITY.md) | ~200 tok (직접 작성) |
| 도구 스키마 (tools 파라미터) | ~14,000자 (20개+ 도구) | ~500 tok (3-4개 도구) |
| **합계** | **~12,000 tok** | **~700 tok** |

### 스트리밍 지원

```python
async with agent.run_stream(user_msg, message_history=history) as stream:
    async for chunk in stream.stream_text(delta=True):
        # 각 토큰 단위로 실시간 수신
        print(chunk, end="", flush=True)
```

- `delta=True`: 각 청크를 개별 전달 (최소 오버헤드, 검증 없음)
- `delta=False`: 누적 텍스트 전달 (출력 검증기 적용)
- `debounce_by` 파라미터 (기본 0.1초): 빠른 이벤트 그룹화

### 대화 기록 관리

#### history_processors (내장)

```python
from pydantic_ai.messages import ModelMessage

def sliding_window(messages: list[ModelMessage]) -> list[ModelMessage]:
    """최근 20개 메시지만 유지. 도구 호출/응답 쌍은 분리하지 않도록 주의."""
    if len(messages) <= 20:
        return messages
    return messages[:2] + messages[-18:]  # 시스템 + 최근 18개

agent = Agent(model, history_processors=[sliding_window])
```

#### 주의사항
- 도구 호출과 도구 응답은 반드시 쌍으로 유지해야 함 (분리 시 LLM 에러)
- 전송 전 토큰 카운팅은 미지원 (Issue #2989)
- 서드파티 패키지 `summarization-pydantic-ai` (v0.0.2)로 자동 요약 가능

### 도구 정의 방식

```python
@agent.tool_plain
def search(query: str) -> str:
    """SearXNG 검색을 수행합니다."""
    # 함수 독스트링이 도구 설명으로 자동 사용됨
    # 파라미터 타입 힌트가 JSON 스키마로 자동 변환됨
    ...

@agent.tool  # RunContext 접근 필요 시
async def web_fetch(ctx: RunContext[MyDeps], url: str) -> str:
    """웹페이지 내용을 읽습니다."""
    ...
```

- `@agent.tool_plain`: 단순 도구 (컨텍스트 불필요)
- `@agent.tool`: RunContext 접근 가능 (의존성 주입)
- 독스트링 → 도구 설명 자동 매핑
- 타입 힌트 → JSON 스키마 자동 생성
- 반환값 자동 검증

---

## 4. vLLM 호환성 이슈 및 해결 상태

### Issue #224: tool_choice=required 미지원

- **상태: 해결**
- 원래 문제: PydanticAI가 `tool_choice='required'` 전송 → vLLM이 `"tool_choice must either be a named tool, 'auto', or 'none'"` 에러 반환
- vLLM 해결: PR #13483으로 v0.8.3부터 지원. 현재 NGC 26.01 (v0.13.0)은 지원됨
- PydanticAI 해결: `OpenAIModelProfile.openai_supports_tool_choice_required` 설정으로 제어 가능

### Issue #728: vLLM 비호환

- **상태: 해결** (#224 중복)

### Issue #1414: 도구 호출 깨짐

- **상태: 닫힘** (비활성으로 자동 닫힘, 2025-11-05)
- pydantic-ai v0.0.43 + vLLM v0.8.3 + Llama 모델에서 발생
- Llama 3.2: 도구 호출 파싱 실패 / Llama 3.1: 무한 도구 호출 루프
- **Qwen2.5 + hermes 파서에서는 발생하지 않음** (모델 특정 이슈)
- 현재 PydanticAI v1.62 (v0.0.43 대비 대폭 업데이트)

### vLLM Issue #15035: $defs JSON 스키마 에러

- **상태: 우회 가능**
- 원래 문제: PydanticAI가 중첩 Pydantic 모델용 `$defs`/`$ref` 스키마 생성 → vLLM guided decoding 백엔드 처리 불가 → HTTP 400
- vLLM에서 수정 안 됨 (NOT PLANNED)
- **PydanticAI 우회**: `InlineDefsJsonSchemaTransformer`로 `$defs`를 플랫 스키마로 인라인

### vLLM Issue #17481: Qwen2.5 tool_choice=auto 무시

- **우려 사항이었으나 테스트에서 정상 작동 확인**
- Qwen2.5-72B가 `tool_choice=auto` 무시하고 텍스트로만 응답한다는 보고가 있었음
- **2026-02-20 테스트에서 auto 모드 정상 동작**: 도구 필요 시 자동 호출, 불필요 시 텍스트 응답

---

## 5. 테스트 결과

### 테스트 환경

- **날짜**: 2026-02-20
- **PydanticAI**: v1.62.0
- **vLLM**: v0.13.0 (NGC nvcr.io/nvidia/vllm:26.01-py3)
- **모델**: mesolitica/Qwen2.5-72B-Instruct-FP8
- **vLLM 실행 옵션**: `--enable-auto-tool-choice --tool-call-parser hermes --max-model-len 32768 --gpu-memory-utilization 0.85 --enforce-eager --swap-space 16 --max-num-seqs 4`
- **테스트 위치**: WSL (로컬) → DGX Spark (192.168.1.242:8000)

### 테스트 코드

```python
"""PydanticAI + vLLM 테스트: 기본 대화 + 도구 호출"""
import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.profiles import InlineDefsJsonSchemaTransformer
from pydantic_ai.profiles.openai import OpenAIModelProfile

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

agent = Agent(
    model,
    system_prompt='너는 자비스다. 한국어로만 답하라. 도구를 적극적으로 활용해라.',
)

@agent.tool_plain
def get_weather(city: str) -> str:
    """도시의 현재 날씨를 조회합니다."""
    return f"{city}: 맑음, 기온 5°C, 습도 40%"

@agent.tool_plain
def calculate(expression: str) -> str:
    """수학 계산을 수행합니다."""
    try:
        result = eval(expression)
        return f"계산 결과: {expression} = {result}"
    except Exception as e:
        return f"계산 오류: {e}"
```

### 테스트 결과

| # | 테스트 | 입력 | 응답 | 입력 토큰 | 출력 토큰 | 요청 수 | 도구 호출 |
|---|--------|------|------|----------|----------|---------|----------|
| 1 | 기본 대화 | "안녕! 너는 누구야?" | "안녕하세요! 저는 자비스입니다. 한국어로 대화를 나눌 수 있어요. 무엇을 도와드릴까요?" | **250** | 30 | 1 | 0 |
| 2 | 도구 호출 (날씨) | "서울 날씨 어때?" | "서울은 현재 맑은 날씨입니다. 기온은 5°C이고, 습도는 40%입니다." | **558** | 52 | 2 | 1 (`get_weather("서울")`) |
| 3 | 도구 호출 (계산) | "123 * 456 + 789 계산해줘" | "계산 결과는 56,877입니다." | **592** | 45 | 2 | 1 (`calculate("123*456+789")`) |
| 4 | 스트리밍 | "대한민국의 수도에 대해 3문장으로 설명해줘" | "대한민국의 수도는 서울입니다. 서울은 정치, 경제, 문화의 중심지로, 인구 약 1천만 명의 대도시입니다. 또한, 600년 이상의 역사를 지닌 고궁들과 현대적인 건축물이 공존하는 도시입니다." | **258** | 70 | 1 | 0 |

### 핵심 확인 사항

- **시스템 프롬프트 250 토큰**: OpenClaw 12,000 토큰 대비 **48배 가벼움**
- **tool_choice=auto 정상 작동**: 도구 필요 시 자동 호출, 불필요 시 텍스트 응답 (vLLM #17481 이슈 미발생)
- **도구 호출 루프 자동 처리**: 도구 호출 → 결과 수신 → 자연어 답변 자동 완성
- **스트리밍 정상**: 토큰 단위 실시간 출력
- **한국어 응답 완벽**: 중국어 출력 없음, 도구 토큰 누출 없음
- **import 주의**: `InlineDefsJsonSchemaTransformer`는 `pydantic_ai.profiles`에서, `OpenAIModelProfile`은 `pydantic_ai.profiles.openai`에서 import

---

## 6. 추론 엔진 비교 (DGX Spark)

### Ollama

제미나이(Gemini)가 Ollama를 추천했으나, DGX Spark에서는 다운그레이드:

| 항목 | vLLM (현재) | Ollama |
|------|-----------|--------|
| 양자화 | FP8 (Blackwell 텐서코어 활용) | GGUF Q8 (정수 연산, 텐서코어 못 씀) |
| 72B 속도 | ~2.8 tok/s | ~3-4 tok/s (Q8), ~4-5 tok/s (Q4) |
| Tool Calling API | 안정적, 성숙 | "experimental" — 언제든 변경 가능 |
| NGC 컨테이너 | 공식 지원 | 없음 (snap으로 사전 설치) |
| Docker 성능 | 정상 | 포럼에서 성능 문제 보고됨 |

- NVIDIA 공식 파트너이고 snap으로 사전 설치되어 있지만, FP8 미지원
- Blackwell 텐서코어를 제대로 활용 못 함
- 도구 호출이 "experimental" → PydanticAI의 구조화된 JSON 요구사항과 충돌 위험

### TGI (Text Generation Inference)

- **완전히 사용 불가**
- 2025년 12월 유지보수 모드 선언 (버그 수정만)
- aarch64 미지원 — ARM64 컨테이너 자체가 없음
- Blackwell 지원 없음
- 제미나이의 TGI 추천은 **잘못된 정보**

### SGLang

- NGC 공식 컨테이너 있음 (`nvcr.io/nvidia/sglang`)
- DGX Spark 전용 빌드 있음 (`lmsysorg/sglang:spark`)
- FP8 네이티브 지원, Blackwell 텐서코어 활용
- 120B 모델에서 ~52 tok/s (llama.cpp보다 13% 빠름)
- **주의**: Qwen2.5-72B는 아직 검증 목록에 없음 (Qwen3만 있음)
- Spark 전용 빌드가 메인 브랜치 뒤처짐

### 결론

| 엔진 | 양자화 | ~tok/s (72B) | Tool Calling | NGC | 상태 |
|------|--------|-------------|-------------|-----|------|
| **vLLM** (현재) | FP8 | ~2.8 | 성숙, 안정 | O | 프로덕션 |
| Ollama | GGUF Q4/Q8 | ~3-5 | 실험적 | X | 다운그레이드 |
| SGLang | FP8 | 미확인 (72B) | 지원 | O | 유망, 미검증 |
| TGI | N/A | N/A | N/A | X | 죽음 |

**현재 vLLM 유지가 최선. 추후 SGLang이 Qwen2.5-72B 공식 검증 시 전환 고려.**

---

## 7. 아키텍처 설계

### OpenClaw vs PydanticAI 봇 비교

```
[OpenClaw 현재 구조]
텔레그램 → OpenClaw Gateway (WS:19000) → OpenClaw Agent (14K tok 오버헤드)
         → vLLM (8000) → Qwen 72B
         → 20개+ 내장 도구 + exec + web_fetch
         → LLM 컴팩션 (수 분 지연)

[PydanticAI 목표 구조]
텔레그램 → python-telegram-bot → PydanticAI Agent (~700 tok)
         → vLLM (8000) → Qwen 72B
         → 3-4개 커스텀 도구 (search, web_fetch, gog)
         → sliding_window history_processor
```

### 필요한 도구 목록

| 도구 | 기능 | 구현 방식 |
|------|------|----------|
| `search` | SearXNG 웹 검색 | `curl http://searxng:8080/search?q=...&format=json` |
| `web_fetch` | 웹페이지 내용 읽기 | `httpx` 또는 `aiohttp` |
| `gog` | Google 서비스 (Gmail, Calendar, Drive 등) | `subprocess` → `gog` CLI |
| `calculate` | 수학 계산 | Python `eval` (선택) |

### 예상 코드량

| 컴포넌트 | 예상 라인 수 |
|----------|-------------|
| 모델/에이전트 설정 | ~20줄 |
| 도구 정의 (3-4개) | ~80줄 |
| 텔레그램 핸들러 (스트리밍) | ~50줄 |
| 대화 기록 관리 | ~20줄 |
| 메인/설정 | ~30줄 |
| **합계** | **~200-300줄** |

---

## 8. 다음 단계

### 즉시 실행 가능

1. [ ] PydanticAI + python-telegram-bot 텔레그램 봇 MVP 구현
2. [ ] SearXNG 검색 도구 연동
3. [ ] web_fetch 도구 구현
4. [ ] gog CLI 도구 연동 (Gmail, Calendar, Drive)
5. [ ] 슬라이딩 윈도우 history_processor 구현
6. [ ] DGX Spark에 배포 (Docker)

### 추후 고려

- [ ] EXAONE 모델 캐시 정리 (~60GB, DGX Spark 디스크)
- [ ] SGLang으로 추론 엔진 전환 테스트
- [ ] Qwen3 모델 출시 시 업그레이드 검토
- [ ] 음성 입력/출력 지원 (선택)

---

## 참고 자료

- [PydanticAI 공식 문서](https://ai.pydantic.dev/)
- [PydanticAI GitHub](https://github.com/pydantic/pydantic-ai)
- [PydanticAI OpenAI 모델 문서](https://ai.pydantic.dev/models/openai/)
- [PydanticAI 스트리밍 문서](https://ai.pydantic.dev/message-history/)
- [vLLM PR #13483: tool_choice=required 지원](https://github.com/vllm-project/vllm/pull/13483)
- [vLLM Issue #15035: $defs 스키마 문제](https://github.com/vllm-project/vllm/issues/15035)
- [vLLM Issue #17481: Qwen2.5 tool_choice=auto](https://github.com/vllm-project/vllm/issues/17481)
- [AMD ROCm PydanticAI + vLLM 튜토리얼](https://rocm.docs.amd.com/projects/ai-developer-hub/en/latest/notebooks/inference/build_airbnb_agent_mcp.html)
- [NVIDIA DGX Spark SGLang Playbooks](https://github.com/NVIDIA/dgx-spark-playbooks/tree/main/nvidia/sglang)
- [SGLang DGX Spark 지원 트래킹](https://github.com/sgl-project/sglang/issues/11658)
