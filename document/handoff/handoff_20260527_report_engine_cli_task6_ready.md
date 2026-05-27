# Handoff: 리포트 엔진 CLI Task 6 착수 준비

> 작성일: 2026-05-27
> 워크스페이스: `/Users/bhkim/Documents/Codex/poc_sam_etf_report`
> 브랜치: `codex/log-artifacts`
> 목적: 새 세션이 리포트 엔진 CLI Task 1~5 구현 이후 상태, 로그 산출물 정책, 입력 문서 정합화, Task 6 착수 조건을 즉시 이어받도록 정리한다.

## 1. 현재 작업 상태 요약

- 리포트 엔진 CLI 개발 계획 기준 Task 1~5 구현은 완료된 상태다.
- `report_engine run`은 현재 Stage 1 template context 생성과 Stage 2 sample component 생성까지 실행 가능하다.
- 전체 실행 로그 저장 계층이 추가되어 CLI 실행 시 `backend/log/{jobId}/` 아래에 stage별 JSON/HTML 디버깅 산출물을 남긴다.
- 입력 변수 `dataset-id`, `template-id`, `month-id`의 허용 값과 관련 문서 정합화가 완료되었다.
- `document/data/etf_data.schema_description.md` 최상단에 `backend/data` JSON 8개 역할 맵이 추가되었다.
- Task 6 계획에는 Stage 3 layout 경계 구현 전에 Stage 2 `componentMode=novita` 생성 기능을 선행 구현하도록 반영되어 있다.
- 현재 `--component-mode novita`는 CLI 선택값에는 있지만 Stage 2 service에서 아직 거부된다. 실제 구현은 Task 6의 첫 작업이다.

## 2. 완료된 구현/문서 작업

| 구분 | 상태 | 주요 파일 |
|---|---|---|
| CLI foundation | 완료 | `backend/report_engine/cli.py`, `backend/report_engine/repository.py`, `backend/report_engine/models.py` |
| Stage 1 template context | 완료 | `backend/report_engine/stage1_template.py`, `backend/tests/test_stage1_template.py` |
| Stage 2 sample component | 완료 | `backend/report_engine/stage2_components.py`, `backend/tests/test_stage2_components.py` |
| 실행 artifact logging | 완료 | `backend/report_engine/artifact_logger.py`, `backend/report_engine/logging_flow.py`, `backend/tests/test_artifact_logger.py`, `backend/tests/test_cli_logging.py` |
| 입력 변수 값 문서화 | 완료 | `document/data/etf_data.schema_description.md`, `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md`, `document/plan/리포트_엔진_상세_설계서-20260527.md` |
| 데이터 JSON 역할 맵 | 완료 | `document/data/etf_data.schema_description.md` |
| Task 6 Novita 선행 작업 명시 | 반영됨, 아직 미커밋 | `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md` |

## 3. Git 상태와 push 상태

handoff 작성 직전 기준 상태는 아래와 같다.

| 항목 | 상태 |
|---|---|
| 현재 브랜치 | `codex/log-artifacts` |
| 원격 추적 | `origin/codex/log-artifacts` |
| 로컬/원격 차이 | 로컬이 원격보다 1커밋 ahead |
| push 완료 커밋 | `0c2bb50 feat: add artifact logging and input docs` |
| 로컬 미 push 커밋 | `2a880dc docs: document data json roles` |
| 미커밋 변경 | `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md` |

주요 커밋:

| 커밋 | 설명 | push 상태 |
|---|---|---|
| `f8b31a3` | `feat: add report engine cli foundation` | 기준 이력 |
| `0c2bb50` | `feat: add artifact logging and input docs` | push 완료 |
| `2a880dc` | `docs: document data json roles` | 로컬에만 있음 |

이 handoff 작성 후에는 신규 handoff 문서와 `document/handoff/handoff_sum.md` 변경이 추가된다. 다음 세션은 `git status --short --branch --untracked-files=all`로 최종 상태를 먼저 확인해야 한다.

## 4. 실행/검증 명령

작업 재개 시 기본 확인 명령:

```bash
git status --short --branch --untracked-files=all
git log --oneline -5
git diff --stat
```

backend 테스트 실행:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

CLI sample 실행:

```bash
cd backend
.venv/bin/python -m report_engine run \
  --dataset-id data_kodex_us_sp500 \
  --template-id tpl_kb_monthly_guidebook \
  --month-id 2026-03
```

지원 입력값은 `document/data/etf_data.schema_description.md`의 `CLI 입력 변수 값 목록`을 기준으로 확인한다.

## 5. 로그 산출물 위치

`report_engine run` 실행 시 상세 로그는 `backend/log/{jobId}/` 아래에 생성된다. `backend/log/`는 실행 산출물이므로 `.gitignore` 대상이며 Git에 올리지 않는다.

예상 산출물 구조:

```text
backend/log/{jobId}/00_request/request.json
backend/log/{jobId}/01_template/template_context.json
backend/log/{jobId}/02_components/component_sources.json
backend/log/{jobId}/02_components/components.json
backend/log/{jobId}/02_components/html/performance_chart.html
backend/log/{jobId}/02_components/html/performance_summary.html
backend/log/{jobId}/02_components/html/top_holdings.html
backend/log/{jobId}/02_components/html/review.html
backend/log/{jobId}/02_components/html/outlook.html
backend/log/{jobId}/03_layout/prompt_input.json
backend/log/{jobId}/03_layout/report_draft.html
backend/log/{jobId}/04_render/render_result.json
backend/log/{jobId}/05_verification/verification.json
backend/log/{jobId}/06_final/final_result.json
```

현재 Task 1~5 구현 범위에서는 Stage 1~2 결과가 실제로 생성되고, Stage 3~6 로그는 placeholder/manual-pass 흐름에 맞춰 생성된다.

## 6. Stage 2 component 출력 방식

Stage 2는 데이터 소스별 HTML component를 5개 고정 순서로 생성한다.

| 순서 | componentKey | 파일명 | 비고 |
|---|---|---|---|
| 1 | `performance_chart` | `performance_chart.html` | `chartSpec` object 허용 |
| 2 | `performance_summary` | `performance_summary.html` | `chartSpec`은 `null` |
| 3 | `top_holdings` | `top_holdings.html` | `chartSpec`은 `null` |
| 4 | `review` | `review.html` | `chartSpec`은 `null` |
| 5 | `outlook` | `outlook.html` | `chartSpec`은 `null` |

각 HTML fragment에는 `data-component-id`가 포함되어야 한다. Stage 2 output은 JSON으로도 `components.json`에 저장되고, 사람이 직접 열어 검수할 수 있도록 component별 `.html` 파일로도 저장된다.

## 7. Task 6 착수 시 주의사항

- Task 6은 Stage 3부터 시작하지 않는다. 먼저 Stage 2 `componentMode=novita`를 구현한다.
- 현재 `backend/tests/test_stage2_components.py`에는 novita mode가 Task 5 범위 밖으로 거부되는 테스트가 있다. Task 6에서는 이 테스트를 fake adapter 기반 성공 케이스로 갱신해야 한다.
- `LlmAdapter`, `NovitaLlmAdapter`, `FakeLlmAdapter` 경계를 만든다.
- 자동 테스트는 Novita 실호출이 아니라 fake adapter 기반으로 작성한다.
- `componentMode=novita`도 sample mode와 동일한 검수 규칙을 통과해야 한다.
  - componentKey 순서는 `performance_chart`, `performance_summary`, `top_holdings`, `review`, `outlook`이다.
  - HTML fragment에 `<style`, `style=`, `class=`를 허용하지 않는다.
  - `performance_chart`만 `chartSpec` object를 가진다.
  - 나머지 4개 component의 `chartSpec`은 `null`이다.
- `LLM_API_KEY` 실제 값은 prompt, log, exception, event, handoff, test output에 기록하지 않는다.
- Novita 실호출은 API key와 네트워크 의존성이 있으므로 기본 CI/자동 테스트 경로로 두지 않는다.

## 8. 다음 세션 작업 체크리스트

1. `git status --short --branch --untracked-files=all`로 현재 변경 상태를 확인한다.
2. `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md`의 Task 6 변경분을 재검수한다.
3. 필요하면 Task 6 계획 변경과 handoff 변경을 함께 커밋하고 push한다.
4. Task 6 구현을 시작할 때는 `backend/report_engine/llm.py`를 만들고 adapter 경계를 먼저 고정한다.
5. `backend/report_engine/stage2_components.py`에 `componentMode=novita` 분기를 추가한다.
6. fake adapter 기반 Stage 2 Novita 테스트를 먼저 통과시킨다.
7. 그 다음 `backend/report_engine/stage3_layout.py`에서 Stage 3 layout 생성 경계를 구현한다.
8. 전체 테스트와 CLI sample 실행으로 `backend/log/{jobId}/02_components/html/*.html` 산출물을 확인한다.

## 9. 이어서 읽을 문서

| 순서 | 문서 | 목적 |
|---|---|---|
| 1 | `document/handoff/handoff_sum.md` | 현재 handoff 목록과 최신 handoff 위치 확인 |
| 2 | `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md` | Task 6 구현 범위와 완료 기준 확인 |
| 3 | `document/plan/리포트_엔진_상세_설계서-20260527.md` | Stage 1~6 전체 설계 확인 |
| 4 | `document/data/etf_data.schema_description.md` | 입력 변수 값과 데이터 JSON 역할 확인 |
| 5 | `backend/tests/test_stage2_components.py` | Stage 2 검수 규칙과 sample mode 기대값 확인 |
