# Handoff: 리포트 엔진 Task 6 구현 후 Stage 4 착수 준비

> 작성일: 2026-05-27
> 워크스페이스: `/Users/bhkim/Documents/Codex/poc_sam_etf_report`
> 브랜치: `codex/log-artifacts`
> 목적: 새 세션이 Task 6 구현 결과, Stage 2/3 경계, 검증 상태, 남은 Stage 4/5/6 작업을 즉시 이어받도록 정리한다.

## 1. 현재 상태 요약

- Task 6의 핵심 범위는 구현된 상태다.
- `componentMode=novita` 실행 경로가 열렸고, Stage 2 component 5개는 Novita adapter를 통해 병렬 생성된다.
- 실제 Novita HTTP adapter는 구현되어 있으나 기본 자동 테스트는 fake adapter 기반으로 유지한다.
- Stage 3 layout service가 분리되었고, Stage 3는 단일 HTML draft를 생성한다.
- Novita Stage 3의 문서상 계약은 layout과 CSS를 함께 포함한 단일 HTML이다. Stage 2 fragment는 무스타일 상태를 유지하고, 표현 스타일은 Stage 3에서 생성한다.
- `componentMode=sample`처럼 LLM adapter가 없는 offline fallback draft는 구조 확인용 최소 HTML이므로 CSS가 없을 수 있다. `backend/log/job_20260527_163917_bf878831/03_layout/report_draft.html`은 이 케이스다.
- chart 실제 렌더링은 Stage 3에서 하지 않는다. Stage 3 output에는 chart placeholder만 남기고, chart 구현은 다음 Stage 4 범위로 남긴다.
- Stage 3에는 footer/bottom disclaimer가 본문과 겹치지 않도록 normal flow, absolute/fixed 금지, bottom safe area 방어 규칙이 추가되었다.
- CLI 실행 중 stage 진행 상황과 LLM 요청/응답 상태가 JSONL 형태로 콘솔에 출력된다.

## 2. 주요 구현 내용

| 영역 | 상태 | 내용 |
|---|---|---|
| LLM adapter | 구현 | `LlmAdapter` protocol과 `NovitaLlmAdapter` 추가. OpenAI-compatible `/v1/chat/completions` 호출, timeout, retry, invalid JSON 오류 변환을 처리한다. |
| Stage 2 novita mode | 구현 | `componentMode=novita`에서 component source 5개를 조회하고 LLM 호출 결과로 `Stage2Component` 5개를 만든다. |
| Stage 2 병렬화 | 구현 | `ThreadPoolExecutor` 기반 fan-out/fan-in 구조로 5개 component LLM 호출을 병렬 실행한다. 결과 순서는 고정 component 순서를 보존한다. |
| Stage 2 검증 | 구현 | source metadata를 신뢰하고 LLM 응답에서는 `html`, `chartSpec`, `styled`만 반영한다. `data-component-id`, style/class 금지, chartSpec 규칙을 검증한다. |
| Stage 3 layout/CSS | 구현/문서 보강 | template, dataset, month summary, components를 prompt input으로 구성하고 adapter 결과가 단일 HTML 문서인지 검증한다. Novita Stage 3 계약은 document-local CSS를 포함한 단일 HTML이며, sample/offline fallback draft는 CSS 없는 구조 확인용 HTML일 수 있다. |
| Stage 3 chart boundary | 구현 | `performance_chart`는 chart placeholder만 포함한다. Stage 3 prompt와 validator 모두 SVG/canvas/script/Chart.js 생성을 거부한다. |
| Stage 3 overlap defense | 구현 | footer/bottom disclaimer가 absolute/fixed positioning으로 겹치는 output을 `LAYOUT_GENERATION_INVALID`로 거부한다. |
| CLI logging | 구현 | `stage.started`, `stage.completed`, `stage.failed`, `llm.request.started`, `llm.response.completed`, `llm.response.failed` 이벤트를 콘솔에 출력한다. |

## 3. 주요 변경 파일

현재 작업 트리 기준으로 다음 변경이 있다.

| 구분 | 파일 |
|---|---|
| 신규 backend | `backend/report_engine/llm.py`, `backend/report_engine/stage3_layout.py` |
| 수정 backend | `backend/report_engine/cli.py`, `backend/report_engine/errors.py`, `backend/report_engine/logging_flow.py`, `backend/report_engine/settings.py`, `backend/report_engine/stage2_components.py` |
| 신규 tests | `backend/tests/test_llm.py`, `backend/tests/test_stage3_layout.py` |
| 수정 tests | `backend/tests/test_cli_and_settings.py`, `backend/tests/test_cli_logging.py`, `backend/tests/test_stage2_components.py` |
| 수정 문서 | `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md`, `document/plan/리포트_엔진_상세_설계서-20260527.md`, `document/plan/리포트_엔진_아키텍처_문서-20260527.md` |
| 참고 문서 | `document/reference/novita_qwen35_qwen36_readtimeout_retry_all_12runs_161919.md`, `document/reference/qwen35_qwen36_지시서_추출_비교_분석_보고서.md`, `document/reference/qwen35_qwen36_rawtext_지시서_추출_비교_분석_보고서_20260518.md` |

## 4. 검증 근거

Task 6 구현 후 아래 검증이 통과했다.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

결과:

```text
Ran 50 tests
OK
```

diff whitespace 검증:

```bash
git diff --check
```

결과: 문제 없음.

## 5. CLI 재검증 명령

sample/manual-pass 기본 경로는 API credential 없이 계속 성공해야 한다.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m report_engine run \
  --dataset-id data_kodex_us_sp500 \
  --template-id tpl_kb_monthly_guidebook \
  --month-id 2026-03 \
  --component-mode sample \
  --verification-mode manual-pass
```

Novita live 경로는 로컬 환경에 Novita credential이 설정된 상태에서 실행한다.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m report_engine run \
  --dataset-id data_kodex_us_nasdaq100 \
  --template-id tpl_woori_monthly_report \
  --month-id 2026-03 \
  --component-mode novita \
  --verification-mode manual-pass
```

예상 콘솔 출력은 stage별 진행 이벤트와 LLM 요청/응답 이벤트가 섞인 JSONL이다. 성공 시 마지막에는 `job.logged` 이벤트와 `backend/log/{jobId}` 경로가 출력된다.

## 6. 로그 산출물 확인 포인트

`report_engine run` 실행 시 산출물은 `backend/log/{jobId}/` 아래에 생성된다. 이 폴더는 실행 산출물이므로 Git 관리 대상으로 보지 않는다.

중요 확인 파일:

```text
backend/log/{jobId}/00_request/request.json
backend/log/{jobId}/01_template/template_context.json
backend/log/{jobId}/02_components/component_sources.json
backend/log/{jobId}/02_components/components.json
backend/log/{jobId}/02_components/html/*.html
backend/log/{jobId}/03_layout/prompt_input.json
backend/log/{jobId}/03_layout/report_draft.html
backend/log/{jobId}/04_render/render_result.json
backend/log/{jobId}/05_verification/verification.json
backend/log/{jobId}/06_final/final_result.json
```

Stage 3 draft에서 `performance_chart` 영역은 chart placeholder만 있어야 한다. `<svg>`, `<canvas>`, `<script>`, Chart.js 기반 chart render는 Stage 3 결과물에 포함되면 안 된다. Novita Stage 3 draft는 `<style>` block 또는 동등한 document-local CSS를 포함해야 하며, sample/offline fallback draft는 CSS가 없을 수 있다.

## 7. 보안 및 로그 주의사항

- Novita credential 원문은 prompt, log artifact, console event, exception, handoff에 기록하지 않는다.
- Stage 2/3 prompt input에는 인증 정보가 포함되면 안 된다.
- LLM 요청/응답 progress event는 metadata 중심으로 출력한다. 원문 prompt나 원문 credential은 콘솔에 출력하지 않는다.
- redaction은 방어 계층으로 유지하지만, 기본 원칙은 민감한 값 자체를 artifact에 쓰지 않는 것이다.

## 8. 남은 작업

다음 세션은 Stage 4부터 이어가면 된다.

1. `git status --short --branch --untracked-files=all`로 작업 트리 상태를 먼저 확인한다.
2. 전체 테스트를 다시 실행해 현재 환경에서도 50개 테스트가 통과하는지 확인한다.
3. Novita live CLI 경로를 한 번 더 실행해 `componentMode=novita`와 Stage 3 draft가 end-to-end로 동작하는지 확인한다.
4. Stage 3 CSS 생성 계약을 코드 prompt, validator, test에도 반영할지 검토한다. 현재 문서 보강은 CSS 요구를 명확히 한 것이며, production validator 강제는 별도 구현 범위다.
5. Stage 4 renderer를 구현한다. 여기서 chartSpec을 실제 chart로 렌더링하고 PDF/image 등 final draft 산출물 경계를 정의한다.
6. Stage 5 visual verification을 구현한다. Stage 3에서 막는 footer overlap 같은 레이아웃 문제를 Stage 5에서도 시각적으로 검출할 수 있게 한다.
7. Stage 6 finalization/version store 경계를 구현한다.
8. Task 6 변경분과 handoff 변경분을 커밋하기 전 `git diff --check`와 전체 테스트를 다시 실행한다.

## 9. 다음 세션 읽기 순서

| 순서 | 문서/파일 | 목적 |
|---|---|---|
| 1 | `document/handoff/handoff_sum.md` | 최신 handoff 위치 확인 |
| 2 | `document/handoff/handoff_20260527_report_engine_task6_stage3_boundary_ready.md` | 현재 handoff 본문 |
| 3 | `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md` | 다음 Stage 4/5/6 작업 범위 확인 |
| 4 | `document/plan/리포트_엔진_상세_설계서-20260527.md` | Stage boundary와 validation policy 확인 |
| 5 | `backend/report_engine/stage3_layout.py` | Stage 3 chart/overlap 방어 구현 확인 |
| 6 | `backend/report_engine/stage2_components.py` | Stage 2 parallel Novita component 생성 확인 |
| 7 | `backend/report_engine/llm.py` | Novita adapter, retry, JSON normalization 확인 |

## 10. 이전 handoff와의 관계

- 이전 최신 문서였던 `handoff_20260527_report_engine_cli_task6_ready.md`는 Task 6 착수 전 상태를 기록한 historical snapshot이다.
- 이 문서가 현재 최신 handoff이며, Task 6 구현 후 Stage 4 착수 준비 상태를 기준으로 한다.
- 더 이전 문서인 `handoff_20260527_report_engine_design.md`는 설계 문서화 시점의 snapshot으로만 참조한다.
