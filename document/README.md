# ETF Report Engine PoC 문서

이 문서는 `/Users/bhkim/Documents/Codex/poc_sam_etf_report` 워크스페이스의 리포트 엔진 PoC를 실행하고, 산출물과 문서 위치를 확인하기 위한 운영 README이다.

## 프로젝트 설명

### 프로젝트 개요

이 프로젝트는 ETF 기준 데이터와 판매사별 리포트 템플릿 이미지를 입력으로 받아 월간/분기 리포트 HTML과 preview 이미지를 생성하는 PoC이다.

현재 구현은 backend CLI 중심이며, `datasetId`, `templateId`, `monthId`를 독립 입력으로 받아 아래 Stage 흐름을 수행한다.

| Stage | 역할 | 주요 산출물 |
|---|---|---|
| Stage 0 | CLI 요청 기록 | `backend/log/{jobId}/00_request/request.json` |
| Stage 1 | dataset/month/template 조회와 템플릿 preview image 확정 | `01_template/template_context.json`, `selection_context.json` |
| Stage 2 | ETF 데이터 source에서 무스타일 컴포넌트 생성 | `02_components/components.json`, `02_components/html/*.html` |
| Stage 3 | 템플릿 이미지를 보고 HTML/CSS 레이아웃 생성, local validator/correction/local repair 수행 | `03_layout/prompt_input.json`, `layout_validation_loop.json`, `report_draft.html` |
| Stage 4 | template chart profile 기준 차트 SVG 주입과 HTML preview 렌더링 | `backend/runs/{jobId}/vN/report.html`, `preview.png`, `04_render/render_result.json` |
| Stage 5 | template image와 preview image 비교 검증 및 필요 시 revision loop | `vN/verification.json`, `05_verification/verification_loop.json` |
| Stage 6 | 통과 version 또는 max iteration 소진 시 best failed version을 final 산출물 위치로 확정 | `backend/runs/{jobId}/final/report.html`, `preview.png`, `06_final/final_result.json` |

### 프로젝트 구조

| 경로 | 설명 |
|---|---|
| `backend/report_engine/` | CLI, Stage 서비스, LLM adapter, renderer, chart renderer, artifact logger 등 runtime 코드 |
| `backend/report_engine/prompt/` | Stage 2/3/5 LLM prompt와 제약 조건 파일 |
| `backend/data/` | runtime catalog와 템플릿 preview image 데이터 |
| `backend/tests/` | unittest 기반 회귀 테스트 |
| `backend/runs/` | CLI 실행 결과물 HTML/PNG/verification 저장 위치 |
| `backend/log/` | CLI 실행 로그, stage artifact, LLM call log 저장 위치 |
| `document/data/` | 데이터 구조, dataset 분석, Stage 2 계약 설명 문서 |
| `document/plan/` | 리포트 엔진 설계서, 아키텍처 문서, CLI 개발 계획 |
| `document/handoff/` | 세션 인수인계 문서와 handoff map |
| `document/reference/` | Qwen/Novita 관련 참고 테스트 보고서 |
| `document/report/` | 사람이 만든 참고 리포트 이미지/PDF |
| `document/sample/` | AI 생성 샘플 이미지와 HTML |
| `document/ETF Reporting system 데이터/` | 판매사/상품 원천 PPTX, XLSX, PDF, DOCX, HWP 자료 |

## 설치 방법

아래 명령은 repo root에서 실행하는 기준이다.

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

Novita live 테스트를 실행하려면 `backend/.env` 또는 shell 환경 변수에 인증값과 LLM 설정을 둔다. 실제 인증값은 문서나 로그에 남기지 않는다.

```bash
cd backend
cat > .env <<'EOF'
LLM_API_KEY=<novita-api-key>
LLM_BASE_URL=https://api.novita.ai/openai
LLM_MODEL=qwen/qwen3.6-27b
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=4096
LLM_TIMEOUT_SECONDS=120
LLM_CHUNK_SIZE_CHARS=12000
LLM_STAGE_BATCH_SIZE=12
EOF
```

## 테스트 방법

테스트 방법은 CLI 실행 기준이다. 모든 예제는 `backend` 디렉터리에서 실행한다.

### no-live 테스트

외부 LLM 호출 없이 sample catalog와 placeholder renderer로 전체 Stage 1~6 경로를 빠르게 확인한다.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m report_engine run \
  --dataset-id data_kodex_us_sp500 \
  --template-id tpl_kb_monthly_guidebook \
  --month-id 2026-03 \
  --component-mode sample \
  --verification-mode manual-pass \
  --renderer-mode placeholder \
  --max-iterations 3 \
  --output-dir runs
```

기대 결과:

- exit code `0`
- stdout 마지막 줄에 `{"event": "job.logged", ...}` 출력
- `backend/runs/{jobId}/final/report.html` 생성
- `backend/runs/{jobId}/final/preview.png` 생성
- `backend/log/{jobId}/events.jsonl` 생성

### live 테스트

Novita LLM과 Playwright renderer를 사용해 실제 Stage 2 component 생성, Stage 3 layout 생성, Stage 5 image verification을 수행한다.

국민은행 템플릿 조합:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m report_engine run \
  --dataset-id data_kodex_us_sp500 \
  --template-id tpl_kb_monthly_guidebook \
  --month-id 2026-03 \
  --component-mode novita \
  --verification-mode novita \
  --renderer-mode playwright \
  --max-iterations 3 \
  --output-dir runs
```

우리은행 템플릿 조합:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m report_engine run \
  --dataset-id data_kodex_korea_dividend_growth_bond_mixed \
  --template-id tpl_woori_monthly_report \
  --month-id 2026-03 \
  --component-mode novita \
  --verification-mode novita \
  --renderer-mode playwright \
  --max-iterations 3 \
  --output-dir runs
```

기대 결과:

- Stage 2에서 Novita component call 5개 수행
- Stage 3에서 template preview image를 첨부한 layout call 수행
- Stage 3 validator 실패 시 correction 최대 3회와 source fragment local repair 수행
- Stage 4에서 chart placeholder가 template chart profile 기준 SVG chart로 교체됨
- Stage 5에서 generated preview image와 template preview image를 함께 검증
- `verification.json`의 `passed`가 `true`인 version이 있으면 해당 version이 `final/`로 복사됨
- max iteration 소진 후 passed version 부재 시 best failed version이 `final/`로 복사되고 `verificationPassed=false`가 기록됨

최근 live 검증 기준:

| 템플릿 | jobId | max iterations | 결과 |
|---|---|---|---|
| KB | `job_20260529_112832_03047792` | 2 | v2 `passed=true`, `finalizationReason=passed_verification` |
| Woori | `job_20260529_113037_92510096` | 2 | 실행 오류 없음, v1 best failed final, `verificationPassed=false`, `finalizationReason=best_failed_after_max_iterations` |

### 테스트에 사용할 파라미터 정보

| CLI 옵션 | 의미 | 대표 값 |
|---|---|---|
| `--dataset-id` | ETF 기준 데이터 선택자 | `data_kodex_us_sp500`, `data_kodex_korea_dividend_growth_bond_mixed` |
| `--template-id` | 레이아웃/스타일 기준 템플릿 이미지 선택자 | `tpl_kb_monthly_guidebook`, `tpl_woori_monthly_report` |
| `--month-id` | 월별 snapshot 선택자 | `2026-03` |
| `--component-mode` | Stage 2 component 생성 방식 | `sample`, `novita` |
| `--layout-mode` | Stage 3 layout 생성 방식 | `novita` |
| `--verification-mode` | Stage 5 검증 방식 | `manual-pass`, `novita` |
| `--renderer-mode` | preview image 렌더링 방식 | `placeholder`, `playwright` |
| `--max-iterations` | Stage 5 revision loop 최대 횟수 | `3` |
| `--output-dir` | `backend` 기준 산출물 저장 경로 | `runs` |

`manual-pass`는 sample/offline smoke 전용이다. `componentMode=novita` 실행은 `verificationMode=novita`만 허용한다.

현재 catalog의 주요 입력 값:

| 구분 | 값 | 설명 |
|---|---|---|
| dataset | `data_kodex_us_sp500_h` | KODEX 미국 S&P500(H) |
| dataset | `data_kodex_us_sp500` | KODEX 미국 S&P500 |
| dataset | `data_kodex_us_nasdaq100` | KODEX 미국나스닥100 |
| dataset | `data_kodex_korea_dividend_growth_bond_mixed` | Kodex 코리아배당성장채권혼합 ETF |
| template | `tpl_kb_monthly_guidebook` | 국민은행 월간 가이드북 템플릿 |
| template | `tpl_woori_monthly_report` | 우리은행 월간 리포트 템플릿 |

개발자 회귀 테스트가 필요하면 아래 unittest를 실행한다.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover tests -v
```

### 결과 산출물 설명

CLI 실행이 성공하면 stdout 마지막 `job.logged` 이벤트에 `jobId`, `reportHtmlPath`, `previewImagePath`, `verificationPassed`, `finalizationReason`, `totalDuration`, `totalDurationMs`가 출력된다.

| 경로 | 설명 |
|---|---|
| `backend/runs/{jobId}/v1/report.html` | 첫 번째 렌더링 version의 HTML |
| `backend/runs/{jobId}/v1/preview.png` | 첫 번째 렌더링 version의 preview image |
| `backend/runs/{jobId}/v1/verification.json` | 해당 version의 Stage 5 검증 결과 |
| `backend/runs/{jobId}/vN/` | Stage 5가 revision을 요청한 경우 추가 version |
| `backend/runs/{jobId}/final/report.html` | Stage 5를 통과한 version 또는 best failed fallback version의 최종 HTML |
| `backend/runs/{jobId}/final/preview.png` | Stage 5를 통과한 version 또는 best failed fallback version의 최종 preview image |

### log 설명

| 경로 | 설명 |
|---|---|
| `backend/log/{jobId}/events.jsonl` | stdout과 같은 job-scoped event 기록. stage 시작/완료, LLM 요청/응답, final event를 JSONL로 저장한다. |
| `backend/log/{jobId}/00_request/request.json` | CLI 요청 파라미터 |
| `backend/log/{jobId}/01_template/template_context.json` | 선택된 템플릿 정보 |
| `backend/log/{jobId}/01_template/selection_context.json` | dataset/template/month 선택 요약 |
| `backend/log/{jobId}/02_components/component_sources.json` | Stage 2 source 입력 |
| `backend/log/{jobId}/02_components/components.json` | Stage 2 component 결과 |
| `backend/log/{jobId}/02_components/html/*.html` | component별 HTML fragment |
| `backend/log/{jobId}/02_components/llm_calls/*.json` | Stage 2 Novita 상세 요청/응답 로그 |
| `backend/log/{jobId}/03_layout/prompt_input.json` | Stage 3 layout prompt 입력 |
| `backend/log/{jobId}/03_layout/report_draft.html` | Stage 3 LLM이 생성한 draft HTML |
| `backend/log/{jobId}/03_layout/layout_validation_loop.json` | Stage 3 initial/correction/local repair 검증 이력 |
| `backend/log/{jobId}/03_layout/attempts/attempt_*_report_draft.html` | Stage 3 attempt별 HTML |
| `backend/log/{jobId}/03_layout/llm_calls/*.json` | Stage 3 Novita 상세 요청/응답 로그 |
| `backend/log/{jobId}/04_render/render_result.json` | Stage 4 chart/render/version 결과. `originalChartSpecType`, `effectiveChartType`, `chartTypeSource` 포함 |
| `backend/log/{jobId}/05_verification/verification.json` | 마지막 verification attempt 요약 |
| `backend/log/{jobId}/05_verification/verification_loop.json` | Stage 5 전체 attempt 이력 |
| `backend/log/{jobId}/05_verification/llm_calls/*.json` | Stage 5 Novita image verification 상세 요청/응답 로그 |
| `backend/log/{jobId}/05_verification/revisions/*` | verification 실패 후 revision이 생성된 경우의 prompt/render 로그 |
| `backend/log/{jobId}/06_final/final_result.json` | final HTML/preview 경로, source version, `verificationPassed`, `finalizationReason`, 전체 처리 시간 |

로그에는 실제 API key, 인증 header, image base64 payload가 남지 않도록 redaction한다.

## 문서 설명

`.DS_Store` 같은 시스템 파일은 문서 목록에서 제외한다.

### 루트 문서

| 문서명 | 문서 위치 | 설명 |
|---|---|---|
| README.md | `document/README.md` | 프로젝트 실행 방법, 테스트 방법, 산출물, 로그, 문서 목록을 정리한 운영 README |

### data 문서

| 문서명 | 문서 위치 | 설명 |
|---|---|---|
| ETF 데이터 및 Stage 2 컴포넌트 데이터 상세 설명서 | `document/data/etf_data.schema_description.md` | runtime catalog, template catalog, Stage 2 source/output JSON의 역할과 스키마를 설명하는 문서 |
| 국민은행 월간 가이드북 3건 ETF 데이터셋 분석 | `document/data/국민은행_월간_가이드북_3ETF.dataset_analysis.md` | 국민은행 월간 가이드북용 3개 ETF dataset 후보와 source 값 분석 문서 |
| 우리은행 월간 리포트 템플릿 월별 데이터셋 후보 분석 | `document/data/우리은행_월간_리포트.dataset_analysis.md` | 우리은행 월간 리포트 템플릿에 사용할 월별 데이터 후보와 변동 데이터 기준을 정리한 문서 |

### plan 문서

| 문서명 | 문서 위치 | 설명 |
|---|---|---|
| 리포트 생성 Idea | `document/plan/리포트 생성 Idea-20260526134517.md` | 리포트 엔진 하네스의 초기 아이디어, 전체 아키텍처, Stage 흐름, 검증 루프 초안 |
| 리포트 엔진 CLI v1 개발 계획 | `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md` | backend CLI v1 구현 task, 검증 기준, Novita live 검증 조합을 정리한 개발 계획서 |
| 리포트 엔진 상세 설계서 | `document/plan/리포트_엔진_상세_설계서-20260527.md` | Stage 1~6 처리 흐름, 데이터/LLM/검증 계약을 상세화한 설계서 |
| 리포트 엔진 아키텍처 문서 | `document/plan/리포트_엔진_아키텍처_문서-20260527.md` | 주요 컴포넌트 책임, LLM 호출 구조, renderer/version/log architecture를 정리한 문서 |
| KB/Woori 템플릿 정합성 개선 계획 | `document/plan/KB_Woori_템플릿_정합성_개선_계획-20260529.md` | KB/Woori live 검증 결과, Stage 3 local repair, best failed finalization, 후속 deterministic layout 개선안을 정리한 문서 |

### handoff 문서

| 문서명 | 문서 위치 | 설명 |
|---|---|---|
| Handoff Map | `document/handoff/handoff_sum.md` | 최신 handoff와 누적 handoff 목록을 관리하는 인수인계 index |
| Stage 3 보정, 템플릿 chart 계약, best-failed final, 문서 최신화 | `document/handoff/handoff_20260529_report_engine_template_contract_docs_ready.md` | Stage 3 local repair, template chart profile, Stage 5/6 반복 종료 정책, KB/Woori live 검증과 문서 최신화 상태를 정리한 최신 handoff |
| 리포트 엔진 설계 및 템플릿 이미지 반영 | `document/handoff/handoff_20260527_report_engine_design.md` | 초기 설계 문서화, 데이터/템플릿 이미지 반영, 다음 작업 상태를 정리한 handoff |
| 리포트 엔진 CLI Task 6 착수 준비 | `document/handoff/handoff_20260527_report_engine_cli_task6_ready.md` | CLI Task 1~5 이후 Task 6 착수 조건과 로그 산출물 정책을 정리한 handoff |
| 리포트 엔진 Task 6 구현 후 Stage 4 착수 준비 | `document/handoff/handoff_20260527_report_engine_task6_stage3_boundary_ready.md` | Task 6 구현 결과, Stage 2/3 경계, Stage 4/5/6 잔여 작업을 정리한 handoff |
| Stage 3 validator 보정 후 Stage 4 연결 준비 | `document/handoff/handoff_20260527_report_engine_stage3_validator_stage4_ready.md` | Stage 3 validator, correction retry, source preservation 보정 상태를 정리한 handoff |
| Stage 4 렌더링, Prompt 파일화, report_template 경로 전환 | `document/handoff/handoff_20260528_report_engine_stage4_prompt_template_ready.md` | Stage 4 chart/render/version, LLM 감사 로그, prompt externalization, report_template 경로 전환 상태를 정리한 handoff |

### reference 문서

| 문서명 | 문서 위치 | 설명 |
|---|---|---|
| Novita qwen3.5/qwen3.6 Tool/Function Call ReadTimeout Retry 12Run 종합 보고서 | `document/reference/novita_qwen35_qwen36_readtimeout_retry_all_12runs_161919.md` | Novita Qwen tool/function-call, timeout, retry 테스트 결과 참고 보고서 |
| qwen3.5-397B-A17B vs qwen3.6-27B 지시서 추출 비교 분석 보고서 | `document/reference/qwen35_qwen36_지시서_추출_비교_분석_보고서.md` | 이미지/OCR 기반 지시서 추출 모델 비교 참고 문서 |
| qwen3.5-397B-A17B vs qwen3.6-27B Raw Text 지시서 추출 비교 분석 보고서 | `document/reference/qwen35_qwen36_rawtext_지시서_추출_비교_분석_보고서_20260518.md` | raw text 기반 지시서 추출 모델 비교 참고 문서 |

### report 문서

| 문서명 | 문서 위치 | 설명 |
|---|---|---|
| 국민은행 월간 리포트 이미지 | `document/report/국민은행_월간_리포트.png` | 국민은행 리포트 템플릿/결과 비교용 이미지 자료 |
| 우리은행 월간 리포트 PDF | `document/report/우리은행_월간_리포트.pdf` | 우리은행 월간 리포트 참고 PDF |
| 우리은행 월간 리포트 이미지 | `document/report/우리은행_월간_리포트.png` | 우리은행 월간 리포트 참고 이미지 |
| 우리은행 ETF 분기별 리포트 PDF | `document/report/우리은행_etf_분기별_리포트.pdf` | 우리은행 ETF 분기 리포트 참고 PDF |
| 우리은행 ETF 분기별 리포트 이미지 | `document/report/우리은행_etf_분기별_리포트.png` | 우리은행 ETF 분기 리포트 참고 이미지 |

### sample 문서

| 문서명 | 문서 위치 | 설명 |
|---|---|---|
| 국민은행 AI 생성 리포트 이미지 | `document/sample/국민은행_ai_생성_레포트.png` | 국민은행 템플릿 기반 AI 생성 결과 샘플 이미지 |
| 우리은행 AI 생성 리포트 이미지 | `document/sample/우리은행_ai_생성_레포트.png` | 우리은행 템플릿 기반 AI 생성 결과 샘플 이미지 |
| 우리은행 ETF 분기별 리포트 HTML | `document/sample/우리은행_etf_분기별_리포트.html` | 우리은행 ETF 분기별 리포트 HTML 샘플 |
| 우리은행 월간 리포트 HTML | `document/sample/우리은행_월간_리포트.html` | 우리은행 월간 리포트 HTML 샘플 |

### ETF Reporting system 데이터

| 문서명 | 문서 위치 | 설명 |
|---|---|---|
| 부산은행 월간 성과 리뷰 코멘트 | `document/ETF Reporting system 데이터/(부산은행) 월간 성과 리뷰 코멘트(KODEX)_26년 3월.xlsx` | 부산은행 월간 성과 리뷰 코멘트 원천 Excel |
| 최종 종목요약 | `document/ETF Reporting system 데이터/(최종)종목요약(KODEX)_260331.pptx` | KODEX 종목 요약 원천 PowerPoint |
| KODEX 금융고배당TOP10타겟위클리커버드콜 | `document/ETF Reporting system 데이터/19) KODEX 금융고배당TOP10타겟위클리커버드콜.pptx` | 상품 소개/요약 원천 PowerPoint |
| KODEX 200 상품소개 | `document/ETF Reporting system 데이터/2. 상품소개_KODEX 200_260331.pptx` | KODEX 200 상품 소개 원천 PowerPoint |
| 26년 04월 월간 상품-삼성 - 밸류업추가 | `document/ETF Reporting system 데이터/26년 04월 월간 상품-삼성 - 밸류업추가.xlsx` | 2026년 4월 월간 상품 데이터 원천 Excel |
| Kodex 미국30년국채액티브(H) 이슈리포트 | `document/ETF Reporting system 데이터/[이슈리포트] Kodex 미국30년국채액티브(H)_26.02.09.pdf` | 이슈리포트 참고 PDF |
| iM뱅크 라인업 | `document/ETF Reporting system 데이터/iM뱅크 라인업.xlsx` | iM뱅크 판매사 라인업 원천 Excel |
| 경남은행 라인업 | `document/ETF Reporting system 데이터/경남은행 라인업.xlsx` | 경남은행 판매사 라인업 원천 Excel |
| 국민은행 라인업 DOCX | `document/ETF Reporting system 데이터/국민은행 라인업.docx` | 국민은행 라인업 원천 Word 문서 |
| 국민은행 라인업 PPTX | `document/ETF Reporting system 데이터/국민은행 라인업.pptx` | 국민은행 라인업 원천 PowerPoint |
| 국민은행 라인업 XLSX | `document/ETF Reporting system 데이터/국민은행 라인업.xlsx` | 국민은행 라인업 원천 Excel |
| 국민은행 분기 리포트 | `document/ETF Reporting system 데이터/국민은행 분기 리포트.xlsx` | 국민은행 분기 리포트 원천 Excel |
| 국민은행 월간 가이드북 | `document/ETF Reporting system 데이터/국민은행 월간 가이드북.pptx` | 국민은행 월간 가이드북 템플릿/원천 PowerPoint |
| 기업은행 라인업 | `document/ETF Reporting system 데이터/기업은행 라인업.hwp` | 기업은행 라인업 원천 HWP |
| 기업은행 분기 가이드북 | `document/ETF Reporting system 데이터/기업은행 분기 가이드북.xlsx` | 기업은행 분기 가이드북 원천 Excel |
| 삼성 Kodex AI전력핵심설비 이슈리포트 | `document/ETF Reporting system 데이터/삼성_Kodex AI전력핵심설비 이슈리포트_260417.pdf` | AI전력핵심설비 이슈리포트 참고 PDF |
| 우리은행 분기 안내장 | `document/ETF Reporting system 데이터/우리은행 분기 안내장.pptx` | 우리은행 분기 안내장 템플릿/원천 PowerPoint |
| 우리은행 월간 리포트 | `document/ETF Reporting system 데이터/우리은행 월간 리포트.pptx` | 우리은행 월간 리포트 템플릿/원천 PowerPoint |
| 월간운용보고서 Kodex 2차전지산업 | `document/ETF Reporting system 데이터/월간운용보고서_Kodex 2차전지산업_20260331.pdf` | 월간 운용보고서 참고 PDF |
| 하나은행 월간 가이드북 | `document/ETF Reporting system 데이터/하나은행 월간 가이드북.pptx` | 하나은행 월간 가이드북 템플릿/원천 PowerPoint |
| 하나은행 월간 리포트 | `document/ETF Reporting system 데이터/하나은행 월간 리포트.pptx` | 하나은행 월간 리포트 템플릿/원천 PowerPoint |
