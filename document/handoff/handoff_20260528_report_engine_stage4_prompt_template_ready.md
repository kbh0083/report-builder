# Handoff: Stage 4 렌더링, Prompt 파일화, report_template 경로 전환

> 작성일: 2026-05-28
> 워크스페이스: `/Users/bhkim/Documents/Codex/poc_sam_etf_report`
> 목적: 새 세션이 report engine Task 7 이후 구현 상태를 이어받아 검증, 정리, 후속 구현을 진행할 수 있도록 현재 계약과 주의점을 남긴다.

## 1. 현재 상태 요약

- CLI는 Stage 0~4 경로를 실행할 수 있다. Stage 2는 Novita component 생성, Stage 3는 layout/CSS 포함 HTML draft 생성, Stage 4는 chart 주입과 version HTML/preview 생성을 담당한다.
- `backend/log/{jobId}/03_layout/report_draft.html`은 Stage 3 LLM 원본 draft로 유지한다.
- `backend/runs/{jobId}/v1/report.html` 또는 CLI `--output-dir` 하위 version HTML에는 Stage 4가 chart placeholder를 inline SVG chart로 교체한 최종 HTML이 저장된다.
- LLM 호출 상세 감사 로그는 stage별 artifact log에 저장하고, stdout progress event에는 prompt/output 본문을 싣지 않는 정책을 유지한다.
- LLM 정적 prompt는 `backend/report_engine/prompt` 아래 flat 파일로 분리했다. 한국어 번역은 각 prompt 파일 최상단 주석에만 배치했다.
- report template asset 위치는 `backend/data/report_template`로 전환했고, template catalog와 관련 테스트도 이 경로를 기준으로 갱신했다.
- Stage 5 자동 시각 검증은 아직 구현되지 않았다. 현재 CLI 검증은 `--verification-mode manual-pass` 경로를 기준으로 사용한다.

## 2. 주요 구현 내용

### Stage 4 Chart/Render/Version

- `backend/report_engine/chart_renderer.py`가 Stage 2 `performance_chart.chartSpec`을 inline SVG chart로 렌더링한다.
- Stage 3 HTML의 `data-chart-placeholder="{componentId}"` 컨테이너를 Stage 4에서 실제 chart markup으로 교체한다.
- chart가 삽입된 HTML만 version store로 전달한다. Stage 3 draft artifact는 LLM 출력 검수용 원본으로 남긴다.
- `backend/report_engine/version_store.py`는 `runs/{jobId}/v{version}/report.html` 저장 후 renderer로 `preview.png`를 만든다.
- `backend/report_engine/renderer.py`에는 Playwright 기반 renderer와 테스트용/placeholder renderer가 있다.
- `04_render/render_result.json`에는 chart 렌더링 여부, chart component id, draft path, final html path, preview image path를 기록한다.

### Stage 3 Validator

- chart component는 Stage 3에서 `data-component-id` 대신 `data-chart-placeholder="{componentId}"`만 있어도 존재하는 것으로 인정한다.
- chart placeholder는 정확히 1개여야 한다.
- non-chart component는 기존처럼 `data-component-id="{componentId}"`가 필요하다.
- Stage 3는 chart를 직접 렌더링하면 안 된다. 다만 header/QR/icon 등 non-chart 영역의 inline SVG는 허용한다.
- `<canvas>`, `<script>`, Chart.js 계열 markup, chart 영역 내부 SVG, `data-chart-rendered`는 Stage 3 validator에서 실패 처리한다.
- Stage 2 fragment 보존 검증은 계속 유지한다. LLM이 source fragment 값을 바꾸거나 누락하면 correction retry 후에도 실패할 수 있다.

### LLM 감사 로그

- `backend/report_engine/llm_call_logger.py`가 stage별 LLM 호출 로그를 `backend/log/{jobId}/{stage}/llm_calls/*.json`에 저장한다.
- 로그에는 request messages, model parameter, response content, finish reason, usage 원문, duration, error 정보를 남긴다.
- artifact logger의 redaction 경로를 거쳐 민감정보와 대용량 이미지 데이터를 제거한다.
- stdout의 `llm.request.started`/`llm.response.completed` event는 metadata-only 정책을 유지한다.

### Prompt Externalization

- prompt 파일은 flat 구조다.
  - `backend/report_engine/prompt/02_components_system.txt`
  - `backend/report_engine/prompt/03_layout_system.txt`
  - `backend/report_engine/prompt/03_layout_visual_objective.json`
  - `backend/report_engine/prompt/03_layout_constraints.json`
  - `backend/report_engine/prompt/03_layout_correction_requirements.json`
- `backend/report_engine/prompt_store.py`가 prompt 파일을 읽는다.
- `.txt`는 자유 형식 system prompt에 사용하고, `.json`은 Stage 3 structured prompt 조각 배열에 사용한다.
- prompt JSON 파일에는 최상단 한국어 번역 주석이 있으므로 runtime에서는 `PromptStore`를 통해 읽어야 한다. 일반 `json.load`로 직접 읽으면 주석 때문에 실패할 수 있다.

### report_template 경로 전환

- report template 파일 위치는 `backend/data/report_template`이다.
- `backend/data/report_templates.json`의 `sourceHtml`, `previewImage`가 새 위치를 가리킨다.
- 현재 catalog가 참조하는 파일은 다음과 같다.
  - `backend/data/report_template/우리은행_월간_리포트.html`
  - `backend/data/report_template/우리은행_월간_리포트.png`
  - `backend/data/report_template/국민은행_월간_리포트.png`
- Stage 1 template validation, repository loading, data catalog 테스트가 새 경로 기준으로 갱신되어 있다.

## 3. 현재 작업 트리에서 확인할 파일 범위

| 구분 | 파일/영역 |
|---|---|
| Stage 4 구현 | `backend/report_engine/chart_renderer.py`, `backend/report_engine/renderer.py`, `backend/report_engine/version_store.py`, `backend/report_engine/logging_flow.py` |
| Stage 2/3 및 LLM | `backend/report_engine/llm.py`, `backend/report_engine/llm_call_logger.py`, `backend/report_engine/stage2_components.py`, `backend/report_engine/stage3_layout.py` |
| Prompt 파일화 | `backend/report_engine/prompt_store.py`, `backend/report_engine/prompt/*` |
| Template path | `backend/data/report_templates.json`, `backend/data/report_template/*` |
| Tests | `backend/tests/test_chart_renderer.py`, `backend/tests/test_renderer.py`, `backend/tests/test_version_store.py`, `backend/tests/test_prompt_store.py`, `backend/tests/test_stage3_layout.py`, `backend/tests/test_cli_logging.py`, `backend/tests/test_data_catalogs.py`, `backend/tests/test_repository.py`, `backend/tests/test_stage1_template.py` |
| Docs | `document/plan/*20260527.md`, `document/handoff/*` |

새 세션 시작 시 `git status --short --branch --untracked-files=all`로 신규 파일 포함 범위를 먼저 확인한다. 새 구현 파일과 template asset이 untracked일 수 있으므로 commit 또는 diff 검토 전에 누락하지 않는다.

## 4. 검증 상태

최근 확인한 주요 검증 결과:

- `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_data_catalogs tests.test_repository tests.test_stage1_template tests.test_cli_logging -v`
  - 결과: `Ran 22 tests ... OK`
- `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v`
  - 결과: `Ran 104 tests ... OK (skipped=1)`
- `git diff --check`
  - 결과: 문제 없음

이 handoff 작성 후 문서 링크, markdown 구조, 민감정보 문구, 최신 handoff pointer를 다시 검수했고 추가 수정이 필요한 문제는 없었다.

## 5. 다음 세션 시작 순서

1. `document/handoff/handoff_sum.md`에서 최신 handoff가 이 문서를 가리키는지 확인한다.
2. `git status --short --branch --untracked-files=all`로 새 파일과 수정 파일 범위를 확인한다.
3. 전체 테스트를 재실행한다.
   - `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v`
   - `git diff --check`
4. live Novita CLI 검증이 필요하면 아래 형태로 Stage 4까지 확인한다.
   - `cd backend`
   - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m report_engine run --dataset-id data_kodex_us_sp500 --template-id tpl_kb_monthly_guidebook --month-id 2026-02 --component-mode novita --verification-mode manual-pass --renderer-mode playwright --output-dir runs`
5. 실행 결과에서 확인할 산출물:
   - `backend/log/{jobId}/02_components/llm_calls/*.json`
   - `backend/log/{jobId}/03_layout/llm_calls/*.json`
   - `backend/log/{jobId}/03_layout/report_draft.html`
   - `backend/log/{jobId}/04_render/render_result.json`
   - `backend/runs/{jobId}/v1/report.html` 또는 지정한 output dir 하위 `v1/report.html`
   - `preview.png`

## 6. 후속 작업 포인트

- Stage 5 Novita visual verification은 아직 남아 있다. 같은 LLM audit log 구조를 `05_verification` stage에도 주입하는 방식으로 확장하면 된다.
- Stage 3 validator는 source fragment 보존을 엄격하게 본다. 실제 Novita 출력이 template sample 값이나 이전 dataset 값을 섞으면 validator가 실패하는 것이 정상이다.
- `PromptStore`가 prompt comment stripping을 담당하므로 prompt 파일을 읽는 새 코드도 같은 store를 사용해야 한다.
- chart spec schema는 Stage 2 LLM 출력 변동에 취약할 수 있다. 새 chart type을 허용할 때는 prompt, validator, renderer, tests를 함께 갱신한다.
- Playwright가 없는 환경에서는 `--renderer-mode placeholder`로 Stage 4 chart injection과 version store 경로를 검증할 수 있다.

## 7. 이전 handoff와 관계

- 이 문서는 `handoff_20260527_report_engine_stage3_validator_stage4_ready.md`를 대체하는 최신 handoff다.
- 이전 handoff들은 삭제하지 않고 이력으로 보존한다.
