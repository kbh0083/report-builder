# Handoff: Stage 5/6 검증 루프, 로그 보강, README 정리 완료

> 작성일: 2026-05-28
> 워크스페이스: `/Users/bhkim/Documents/Codex/poc_sam_etf_report`
> 브랜치: `codex/log-artifacts`
> 기준 커밋: `07cbe2d feat: add report verification and logging flow`
> 목적: 새 세션이 Stage 5/6, Novita 검증, 로그 artifact, README까지 반영된 현재 상태에서 바로 이어서 작업할 수 있도록 구현 범위와 검증 증거를 정리한다.

## 1. 현재 상태 요약

- `codex/log-artifacts` 브랜치의 구현 변경은 `07cbe2d`로 커밋되어 `origin/codex/log-artifacts`에 push 완료됐다.
- CLI는 Stage 0~6 경로를 모두 실행한다.
  - Stage 0: 요청 기록
  - Stage 1: dataset/month/template 선택
  - Stage 2: sample 또는 Novita component 생성
  - Stage 3: template preview image 기반 layout HTML 생성
  - Stage 4: chart SVG 주입, version HTML/preview 생성
  - Stage 5: manual-pass 또는 Novita preview image 검증 및 revision loop
  - Stage 6: 통과 version을 `final/` 산출물로 확정
- Stage 3 LLM 입력에서 `styleCandidates` 제공을 제거했다. 스타일 판단 기준은 template preview image이며, Stage 3 HTML의 CSS 변수는 LLM이 이미지에서 추론해 출력한다.
- template catalog와 관련 코드에서 `sourceHtml` 의존을 제거했다. template 선택의 기준 파일은 `previewImage`다.
- Stage 4 chart renderer는 Stage 3 HTML의 CSS 변수 `--chart-series-1`, `--chart-series-2`를 재사용한다. 변수가 없으면 푸른 계열이 아니라 neutral fallback을 쓴다.
- Stage 5 Novita verification은 generated preview image와 template preview image를 함께 전달해 색상/시각 톤 일치까지 검증하도록 구현했다.
- `renderer-mode=placeholder`는 Novita component 또는 Novita verification 조합에서 HTML과 맞는 preview를 만들 수 없으므로 CLI가 `playwright`로 자동 승격한다.
- `document/README.md`를 새로 작성했고, CLI 기준 no-live/live 테스트 방법, 결과 산출물, 로그 설명, `document` 폴더 문서 목록을 포함했다.

## 2. 주요 변경 파일

| 구분 | 파일/영역 | 내용 |
|---|---|---|
| Stage 5 | `backend/report_engine/stage5_verification.py` | manual-pass/Novita verification loop, version별 `verification.json`, revision decision |
| Stage 6 | `backend/report_engine/stage6_finalize.py` | 통과 version의 HTML/preview를 `final/`로 확정 |
| LLM adapter | `backend/report_engine/llm.py` | Stage 5 multimodal verification, JSON normalization, image metadata logging |
| Prompt | `backend/report_engine/prompt/05_verification_system.txt`, `05_verification_requirements.json` | Stage 5 검증 시스템 프롬프트와 요구사항 |
| Orchestration | `backend/report_engine/logging_flow.py` | Stage 5/6 연결, revision 생성, `events.jsonl`, stage duration, final duration |
| Artifact logging | `backend/report_engine/artifact_logger.py`, `llm_call_logger.py` | 민감정보 redaction과 stage별 LLM call log 저장 |
| Chart/render | `backend/report_engine/chart_renderer.py`, `renderer.py` | CSS 변수 기반 chart color, Playwright file URL 렌더링 안정화 |
| CLI | `backend/report_engine/cli.py` | Novita 조합에서 placeholder renderer 자동 승격 |
| Data contract | `backend/data/etf_data.json`, legacy `*.dataset.sample.json`, `backend/data/report_templates.json` | `styleCandidates`, `sourceHtml` 제거 |
| Tests | `backend/tests/test_*` | Stage 5/6, logging, renderer, chart color, data contract, README 관련 회귀 테스트 |
| Docs | `document/README.md`, `document/plan/*20260527.md` | CLI 사용법, live/no-live 테스트, Stage 5/6 및 로그 계획 반영 |
| Samples | `document/sample/*` | AI 생성 샘플 이미지/HTML과 sample 문서 목록 정리 |

## 3. Runtime 산출물 계약

CLI 실행 후 기본 산출물:

- `backend/runs/{jobId}/v1/report.html`
- `backend/runs/{jobId}/v1/preview.png`
- `backend/runs/{jobId}/v1/verification.json`
- revision이 발생하면 `backend/runs/{jobId}/v2`, `v3` 순서로 추가 version 생성
- 통과 version은 `backend/runs/{jobId}/final/report.html`, `final/preview.png`로 확정

로그 산출물:

- `backend/log/{jobId}/events.jsonl`: stdout과 같은 job-scoped event 저장
- `00_request/request.json`: CLI 요청 파라미터
- `01_template/template_context.json`, `selection_context.json`: template 및 선택 요약
- `02_components/components.json`, `02_components/html/*.html`, `02_components/llm_calls/*.json`
- `03_layout/prompt_input.json`, `03_layout/report_draft.html`, `03_layout/llm_calls/*.json`
- `04_render/render_result.json`
- `05_verification/verification.json`, `verification_loop.json`, `llm_calls/*.json`
- revision 발생 시 `05_verification/revisions/v{n}_prompt_input.json`, draft/render artifact
- `06_final/final_result.json`: final path, source version, `jobStartedAt`, `jobCompletedAt`, `totalDurationMs`, `totalDuration`

로그에는 인증값, 인증 header, image base64 payload를 남기지 않는 정책을 유지한다.

## 4. 검증 상태

커밋 전 수행한 검증:

- `git diff --check`
  - 결과: 통과
- `git diff --cached --check`
  - 결과: 통과
- `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover tests -v`
  - 결과: `Ran 127 tests in 2.756s`
  - 결과: `OK (skipped=1)`

README 검수에서 확인한 내용:

- `settings.py`의 필수 LLM 설정과 README `.env` 예시 일치
- CLI parser 옵션과 README parameter 표 일치
- catalog dataset/template ID가 README에 모두 반영됨
- `document` 아래 non-hidden 파일 47개 누락 없음
- README의 `document/...` 경로 broken path 없음
- Markdown fence, heading, table separator, trailing whitespace 문제 없음

최근 Novita live acceptance artifact:

| jobId | 조합 | 검증 |
|---|---|---|
| `job_20260528_152247_b88f7235` | `data_kodex_us_sp500` + `tpl_kb_monthly_guidebook`, `componentMode=novita`, `verificationMode=novita` | Stage 2/3/5 LLM call 수행, `v1/verification.json`의 `passed=true` |
| `job_20260528_152409_f82ff90c` | `data_kodex_korea_dividend_growth_bond_mixed` + `tpl_woori_monthly_report`, `componentMode=novita`, `verificationMode=novita` | Stage 2/3/5 LLM call 수행, `v1/verification.json`의 `passed=true` |
| `job_20260528_152952_58d614ac` | Woori 조합, `componentMode=novita`, `verificationMode=manual-pass` | Stage 2/3 LLM call 수행, final HTML/preview 생성 |
| `job_20260528_153103_f71da7dc` | KB 조합, `componentMode=novita`, `verificationMode=manual-pass` | Stage 2/3 LLM call 수행, final HTML/preview 생성 |

이 handoff 작성 시점에는 handoff 문서 1개 추가와 `handoff_sum.md` 업데이트가 아직 별도 커밋되지 않은 문서 변경으로 남는다.

## 5. 다음 세션 시작 순서

1. `document/handoff/handoff_sum.md`에서 최신 handoff가 이 문서를 가리키는지 확인한다.
2. `git status --short --branch --untracked-files=all`로 이 handoff 문서와 `handoff_sum.md` 변경 상태를 확인한다.
3. 문서 변경만 마무리할 경우 아래 검증을 먼저 수행한다.
   - `git diff --check`
   - handoff markdown 구조 검사
   - `document/handoff` 민감정보 문구 scan
4. 코드나 prompt를 수정할 경우 backend 테스트를 재실행한다.
   - `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover tests -v`
5. LLM 경계, renderer, Stage 3/5 prompt를 수정한 경우 Novita live CLI smoke를 다시 수행한다.
   - KB: `data_kodex_us_sp500` + `tpl_kb_monthly_guidebook`
   - Woori: `data_kodex_korea_dividend_growth_bond_mixed` + `tpl_woori_monthly_report`

## 6. 주의할 점

- `sourceHtml`은 runtime catalog와 code path에서 제거된 상태다. 새 코드가 template HTML 파일을 다시 참조하지 않도록 한다.
- `styleCandidates`는 Stage 3 LLM 입력에서 제거된 상태다. 색상/스타일 값은 JSON으로 주지 않고 template preview image로 판단하게 유지한다.
- Novita live 검증에는 실제 HTML을 렌더링한 preview가 필요하다. `componentMode=novita` 또는 `verificationMode=novita`에서는 placeholder renderer를 사용하지 않는다.
- Stage 5 verification은 이미지 판단 품질에 의존한다. issue schema 검증, `maxIterations`, artifact 보존은 유지해야 한다.
- `events.jsonl`과 stage별 `llm_calls`에는 prompt/output 본문 일부가 남을 수 있으나 인증값과 image base64는 redaction되어야 한다.
- 실제 인증값이나 민감정보 값을 handoff, README, log 설명에 기록하지 않는다.

## 7. 이전 handoff와 관계

- 이 문서는 `handoff_20260528_report_engine_stage4_prompt_template_ready.md`를 대체하는 최신 handoff다.
- 이전 handoff들은 삭제하지 않고 이력으로 보존한다.
- `document/handoff/handoff_sum.md`는 이 문서를 최신 handoff로 가리키도록 함께 업데이트했다.
