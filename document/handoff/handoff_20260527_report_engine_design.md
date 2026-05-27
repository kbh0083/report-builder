# Handoff: 리포트 엔진 설계 및 템플릿 이미지 반영

> 작성일: 2026-05-27  
> 워크스페이스: `/Users/bhkim/Documents/Codex/poc_sam_etf_report`  
> 목적: 새로운 세션이 리포트 엔진 설계 문서화와 데이터/템플릿 이미지 반영 상태를 즉시 이어받도록 현재 세션의 결정, 산출물, 검수 결과, 다음 작업을 정리한다.

## 1. 현재 상태 요약

- 이번 세션의 범위는 구현 코드 작성이 아니라 PoC 리포트 엔진 설계 문서 작성, 관련 데이터/문서 갱신, 검수였다.
- 리포트 엔진은 현재 backend 중심 파이프라인으로 설계했다.
- frontend 폴더는 존재하지만 아직 구현 파일이 없으므로, frontend 전용 설계서는 frontend 구현 착수 시 별도 작성하는 방향으로 결정했다.
- 워크스페이스는 현재 Git 저장소로 연결되어 있으므로 다음 세션에서는 브랜치, 원격, 작업트리 변경사항을 함께 확인해야 한다.

## 2. 완료 산출물

| 구분 | 파일 | 상태 |
|---|---|---|
| 원본 아이디어 | `document/plan/리포트 생성 Idea-20260526134517.md` | 기존 초안, 수정하지 않음 |
| 상세 설계서 | `document/plan/리포트_엔진_상세_설계서-20260527.md` | 신규 작성 완료 |
| 아키텍처 문서 | `document/plan/리포트_엔진_아키텍처_문서-20260527.md` | 신규 작성 완료 |
| 국민은행 데이터 분석 문서 | `document/data/국민은행_월간_가이드북_3ETF.dataset_analysis.md` | preview image 설명 갱신 완료 |
| 통합 데이터 스키마 설명 | `document/data/etf_data.schema_description.md` | D1~D4 preview image 표 갱신 완료 |
| 국민은행 템플릿 이미지 | `document/report/국민은행_월간_리포트.png` | Stage 3 시각 기준 이미지로 반영 완료 |

## 3. 핵심 설계 결정

### 3.1 Stage 흐름

리포트 생성 엔진은 Stage 1~6으로 정의했다.

| Stage | 책임 | 구현 판단 |
|---|---|---|
| Stage 1 | 템플릿 선택/이미지 확보 | 가능, 난이도 중 |
| Stage 2 | 5개 무스타일 컴포넌트 생성 | 가능, 난이도 중 |
| Stage 3 | 레이아웃/CSS 생성 | 조건부 가능, 난이도 상 |
| Stage 4 | HTML 렌더링/버전 저장 | 가능, 난이도 중 |
| Stage 5 | 이미지 검증/수정 루프 | 조건부 가능, 난이도 상 |
| Stage 6 | 최종 HTML 확정 | 가능, 난이도 중 |

Stage 3과 Stage 5는 멀티모달 LLM의 시각 품질 판단과 반복 수렴성에 의존하므로 조건부 가능으로 문서화했다.

### 3.2 backend/frontend 문서 분리 판단

- 현재 설계 문서는 backend 리포트 생성 엔진을 대상으로 하므로 당장 backend/frontend로 문서를 나누지 않는다.
- frontend는 아직 비어 있고 프레임워크 설정도 없으므로 현재 문서에는 API/SSE/CLI 경계만 유지한다.
- frontend 구현이 시작되면 화면 구성, job 진행 UI, 버전 preview, 오류 표시, 다운로드/확정 UX를 다루는 frontend 전용 상세 설계서를 추가한다.

### 3.3 차트 렌더링

- PoC 기본값은 backend SVG/이미지 렌더링이다.
- Stage 2의 `chartSpec`은 차트 생성 입력 계약으로 유지한다.
- Stage 3 HTML에는 생성된 inline SVG 또는 이미지 참조를 삽입하는 방향으로 설계했다.

## 4. LLM 설정

backend는 `backend/.env`의 Novita AI OpenAI-compatible API 설정을 사용한다. API key 값은 문서, 로그, handoff에 기록하지 않는다.

| 항목 | 현재값 또는 정책 |
|---|---|
| Provider | Novita AI |
| API 형식 | OpenAI-compatible |
| `LLM_MODEL` | `qwen/qwen3.6-27b` |
| `LLM_BASE_URL` | `https://api.novita.ai/openai` |
| `LLM_TEMPERATURE` | `0.0` |
| `LLM_MAX_TOKENS` | `65536` |
| `LLM_TIMEOUT_SECONDS` | `120` |
| `LLM_CHUNK_SIZE_CHARS` | `12000` |
| `LLM_STAGE_BATCH_SIZE` | `12` |
| Novita 인증 환경 변수 | 값 기록 금지 |

## 5. 데이터와 템플릿 이미지 상태

### 5.1 기준 데이터

현재 CLI 요청 모델은 `datasetId`, `templateId`, `monthId`를 독립 입력으로 받는다. 아래 표의 `기존 원천 template.id`는 병합 전 source dataset의 legacy 식별자이며, CLI의 `--template-id` 값이 아니다.

| datasetId | 데이터셋 | 기존 원천 template.id | 지원 monthId |
|---|---|---|---|
| `data_kodex_us_sp500_h` | 국민은행 Kodex 미국 S&P500(H) ETF | `kb_kodex_monthly_guidebook_449180` | `2026-01`, `2026-02`, `2026-03` |
| `data_kodex_us_sp500` | 국민은행 Kodex 미국 S&P500 ETF | `kb_kodex_monthly_guidebook_379800` | `2026-01`, `2026-02`, `2026-03` |
| `data_kodex_us_nasdaq100` | 국민은행 Kodex 미국나스닥100 ETF | `kb_kodex_monthly_guidebook_379810` | `2026-01`, `2026-02`, `2026-03` |
| `data_kodex_korea_dividend_growth_bond_mixed` | 우리은행 Kodex 코리아배당성장채권혼합 ETF | `woori_kodex_monthly_issue_report` | `2026-01`, `2026-02`, `2026-03` |

| templateId | 템플릿 | sourceHtml | previewImage |
|---|---|---|---|
| `tpl_kb_monthly_guidebook` | 국민은행 월간 가이드북 | `document/report/우리은행_월간_리포트.html` | `document/report/국민은행_월간_리포트.png` |
| `tpl_woori_monthly_report` | 우리은행 월간 리포트 | `document/report/우리은행_월간_리포트.html` | `document/report/우리은행_월간_리포트.png` |

### 5.2 수정된 데이터 파일

- `backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500.dataset.sample.json`
- `backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500_H.dataset.sample.json`
- `backend/data/국민은행_월간_가이드북_KODEX_미국나스닥100.dataset.sample.json`
- `backend/data/etf_data.json`

우리은행 데이터셋의 preview image는 기존 `document/report/우리은행_월간_리포트.png`로 유지했다.

### 5.3 Stage 2 파생 데이터

- `backend/data/etf_stage2_component_sources.json`: componentSources 60개, componentKey 5종.
- `backend/data/etf_stage2_components.sample.json`: stage2Components 60개.
- 두 파일에는 template preview 경로가 없어 수정하지 않았다.

Stage 2 componentKey는 아래 5개로 고정한다.

| componentKey | 용도 |
|---|---|
| `performance_chart` | 성과 추이 차트 |
| `performance_summary` | 기간별 성과 요약 |
| `top_holdings` | Top 10 보유내역 |
| `review` | 운용 리뷰 |
| `outlook` | 시장 전망 |

## 6. 검수 결과

최종 검수 결과는 clean이다.

| 검수 항목 | 결과 |
|---|---|
| JSON 문법 | 관련 JSON 파일 모두 정상 |
| previewImage 값 | 국민은행 D1~D3는 국민은행 PNG, 우리은행 D4는 우리은행 PNG |
| sourceHtml 값 | 전체 데이터셋에서 기존 우리은행 HTML 유지 |
| 이미지 파일 | `국민은행_월간_리포트.png`와 `우리은행_월간_리포트.png` 존재 및 PNG 형식 확인 |
| 문서 동기화 | 데이터 분석 문서, 스키마 설명서, 상세 설계서, 아키텍처 문서 반영 완료 |
| Markdown | 설계 문서 코드블록 균형 확인 |
| Mermaid | 외부 Mermaid 이미지 링크 없음 확인 |
| 보안 | 실제 API key 값 기록 없음 |

검수 중 `document/data/etf_data.schema_description.md`의 D4까지 국민은행 preview image를 기대하는 잘못된 검수 조건이 한 번 있었으나, 이는 검수 스크립트 범위 오류였다. 섹션 범위를 바로잡아 재검수했고 문서/데이터 문제는 없었다.

## 7. 다음 세션 시작 지점

다음 세션에서 구현을 시작한다면 아래 순서가 가장 안전하다.

1. `document/plan/리포트_엔진_상세_설계서-20260527.md`와 `document/plan/리포트_엔진_아키텍처_문서-20260527.md`를 먼저 읽는다.
2. `backend/data/etf_data.json`과 Stage 2 파생 데이터 2개를 로딩하는 repository 계층을 만든다.
3. Stage 1 템플릿 선택/이미지 확보를 구현하고 파일 존재 검사를 추가한다.
4. Stage 2는 sample adapter를 먼저 구현해 LLM 없이 5개 컴포넌트 흐름을 재현한다.
5. Novita adapter는 이후 연결하고, Novita 인증 환경 변수 값이 로그나 산출물에 남지 않도록 redaction을 먼저 적용한다.
6. Stage 3는 template preview image와 Stage 2 컴포넌트 5개를 입력으로 받는 HTML 생성 경계부터 구현한다.
7. Stage 4는 Playwright/Chromium screenshot 기반으로 `report.html`, `preview.png`, `job.json`, `events.jsonl` 저장을 구현한다.
8. Stage 5는 issue JSON schema 검증과 `maxIterations=3` 반복 한도를 둔다.
9. Stage 6는 검증 통과 version을 final로 표시하고 final HTML/preview 경로를 반환한다.
10. API/CLI는 같은 orchestrator를 호출하게 만들고, 진행 이벤트는 HTTP SSE와 CLI JSON lines가 같은 payload를 쓰게 한다.

## 8. 주의사항

- Novita 인증 환경 변수의 실제 값은 어떤 문서, 로그, 테스트 출력에도 기록하지 않는다.
- 국민은행 전용 HTML 템플릿은 아직 없다. 현재 변경은 국민은행 preview image 반영이며 `sourceHtml` 변경이 아니다.
- A4 페이지네이션은 현재 PoC 제외 범위이며 운영 전환 Open Issue로 남아 있다.
- frontend 구현은 아직 시작되지 않았다. frontend 문서 분리는 UI 요구사항과 기술 스택이 정해진 뒤 진행한다.
- 기존 초안 `document/plan/리포트 생성 Idea-20260526134517.md`는 이 세션에서 수정하지 않았다.
