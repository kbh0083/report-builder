# Handoff: Stage 3 validator 보정 후 Stage 4 연결 준비

> 작성일: 2026-05-27
> 워크스페이스: `/Users/bhkim/Documents/Codex/poc_sam_etf_report`
> 브랜치: `codex/log-artifacts`
> 목적: 새 세션이 Stage 3 CSS/layout 생성, correction retry, source preservation validator 보정, Stage 4 renderer/version store 착수 상태를 즉시 이어받도록 정리한다.

## 1. 현재 상태 요약

- Stage 2 `componentMode=novita` 경로는 component source 5개를 Novita adapter로 병렬 호출하고, 결과 순서를 고정 component order로 되돌린다.
- Stage 3는 template preview image를 우선 시각 기준으로 삼아 A4 portrait 단일 HTML과 document-local `<style>` CSS를 생성한다.
- Stage 3 Novita 호출은 template preview PNG data URL을 OpenAI-compatible multimodal message로 첨부한다.
- LLM call artifact는 상세 요청/응답을 남기되 image base64 원문은 기록하지 않고 MIME/크기 metadata만 남긴다.
- Stage 3 validator는 단일 HTML, 5개 component marker, non-empty `<style>`, 외부 resource 금지, chart rendering 금지, chart placeholder, footer normal-flow 규칙을 검사한다.
- Stage 3 correction retry는 `LAYOUT_GENERATION_INVALID`에만 1회 수행한다. 두 번째 실패도 동일 error code로 실패한다.
- source preservation 검사는 chart component를 제외하고 비차트 component의 표 헤더, 표 셀, 문단, 리스트 문구를 보존 대상으로 삼는다.
- Stage 3 제목/섹션 라벨은 template preview image 기준으로 재배치 또는 재라벨링될 수 있다.
- Stage 4 관련 `renderer.py`, `version_store.py`와 테스트 파일이 작업 트리에 untracked 상태로 존재한다. 다음 세션에서 통합 범위를 먼저 확인해야 한다.

## 2. 이번 세션의 핵심 보정

### Stage 3 CSS/layout 계약

- `stage3_layout.py`의 prompt input에 `styleCandidates`, visual objective, CSS constraints가 포함되었다.
- `logging_flow.py`가 template preview image를 data URL로 만들어 Stage 3 adapter에 전달한다.
- sample/offline fallback draft도 최소 A4 CSS, typography, section spacing, chart placeholder 공간, normal-flow footer를 포함한다.

### Correction retry

- `Stage3LayoutService.generate_report_draft()`는 1차 HTML 검증 실패가 `LAYOUT_GENERATION_INVALID`일 때 correction prompt로 같은 adapter를 1회 재호출한다.
- correction prompt에는 `attempt: 1`, `previousError`, `requirements`, `rejectedHtml`가 포함된다.
- progress event의 Stage 3 두 번째 request/completed metadata에는 `correctionAttempt=1`이 포함된다.
- stdout/progress event에는 prompt input, rejected HTML, HTML 원문, image base64가 노출되지 않는다.

### Source preservation validator

- 초기 구현은 모든 text node를 보존 대상으로 삼아 `h2` 제목까지 필수 검사했다.
- Novita live 산출물에서 `ETF 성과 추이 요약` 제목이 template 기준으로 `ETF 성과 추이`로 바뀌었고, 이 때문에 `LAYOUT_GENERATION_INVALID`가 발생했다.
- 보정 후 source preservation 대상은 `th`, `td`, `li`, `p`에 한정된다.
- 표 헤더, 숫자, 종목명, 리스트/문단 문구는 계속 deterministic하게 검증한다.
- chart component 원천 텍스트는 Stage 3 placeholder로 대체되므로 source preservation 검사에서 제외한다.

## 3. 현재 작업 트리 요약

현재 브랜치에는 아래 변경이 남아 있다.

| 구분 | 내용 |
|---|---|
| Stage 2/3 backend | `llm.py`, `logging_flow.py`, `stage3_layout.py` 수정 |
| Stage 2/3 tests | `test_cli_logging.py`, `test_llm.py`, `test_stage2_components.py`, `test_stage3_layout.py` 수정 |
| Stage 4 후보 | `renderer.py`, `version_store.py`, `test_renderer.py`, `test_version_store.py` untracked |
| 문서 | plan 문서 3개와 이전 handoff 문서 1개 수정, `handoff_sum.md` 최신 포인터 갱신, 이 handoff 문서 신규 추가 |

다음 세션은 먼저 `git status --short --branch --untracked-files=all`로 변경 범위를 확인하고, Stage 4 후보 파일을 이번 변경에 포함할지 별도 작업으로 분리할지 결정한다.

## 4. 검증 근거

이번 상태에서 아래 검증이 통과했다.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

결과:

```text
Ran 78 tests
OK (skipped=1)
```

diff whitespace 검증:

```bash
git diff --check
```

결과: 문제 없음.

이전 실패 artifact 재검증:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c 'import json; from pathlib import Path; from report_engine.models import Stage2Component; from report_engine.stage3_layout import Stage3LayoutService; base=Path("log/job_20260527_181931_d6e2f616"); comps=[Stage2Component(**item) for item in json.loads((base/"02_components/components.json").read_text(encoding="utf-8"))]; html=json.loads((base/"03_layout/llm_calls/0007_stage3_layout_layout.json").read_text(encoding="utf-8"))["response"]["content"]; Stage3LayoutService(None).validate_report_draft(html, comps); print("previous failing stage3 artifact validates")'
```

결과:

```text
previous failing stage3 artifact validates
```

## 5. Live CLI 재확인 상태

사용자가 실패시킨 명령은 아래와 같다.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m report_engine run \
  --dataset-id data_kodex_us_nasdaq100 \
  --template-id tpl_woori_monthly_report \
  --month-id 2026-03 \
  --component-mode novita \
  --verification-mode manual-pass
```

현재 sandbox 내부 재실행은 Stage 2에서 `CONFIG_INVALID at llm: LLM request failed`로 실패했다. 제한 없는 네트워크 재실행은 외부 LLM 전송 정책으로 거부되었다. 따라서 다음 세션에서 사용자가 허용한 로컬 환경 또는 사용자의 터미널에서 live 재확인을 진행한다.

## 6. 다음 세션 시작 순서

1. `document/handoff/handoff_sum.md`에서 최신 handoff가 이 문서인지 확인한다.
2. `git status --short --branch --untracked-files=all`로 tracked/untracked 변경 범위를 확인한다.
3. `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v`를 실행한다.
4. `git diff --check`를 실행한다.
5. 필요 시 사용자의 터미널에서 Novita live CLI를 재실행해 Stage 3가 `job.logged`까지 완료되는지 확인한다.
6. Stage 4 renderer/version store 후보 파일을 검토하고, `logging_flow.py`의 Stage 4 skipped 경로와 실제 renderer/version store를 연결할지 결정한다.
7. Stage 5 visual verification과 Stage 6 finalization/version alias 경계를 이어서 구현한다.

## 7. 다음 세션에서 주의할 점

- Stage 3에서 `<svg>`, `<canvas>`, `<script>`, Chart.js를 생성하면 안 된다. chart는 Stage 4가 처리한다.
- Stage 3 footer/bottom disclaimer는 `position:absolute` 또는 `position:fixed`를 쓰면 안 된다.
- source preservation 실패가 발생하면 먼저 `th`, `td`, `li`, `p`의 실제 데이터 누락인지 확인한다. 제목 변경만으로 실패하면 validator가 잘못된 것이다.
- detailed LLM call artifact에는 rejected HTML이 남을 수 있으나, stdout/progress event에는 prompt, rejected HTML, HTML 원문, image base64가 노출되면 안 된다.
- 문서와 handoff에는 인증값을 기록하지 않는다.

## 8. 이전 handoff와의 관계

- 이전 최신 문서 `handoff_20260527_report_engine_task6_stage3_boundary_ready.md`는 Stage 3 boundary 구현 직후 snapshot이다.
- 이 문서는 Stage 3 CSS generation, correction retry, source preservation validator 보정까지 반영한 최신 snapshot이다.
- `handoff_20260527_report_engine_cli_task6_ready.md`와 `handoff_20260527_report_engine_design.md`는 historical snapshot으로 보존한다.
