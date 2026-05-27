# ETF 데이터 및 Stage 2 컴포넌트 데이터 상세 설명서

## 0. 데이터 JSON 파일 역할 맵

`backend/data` 폴더에는 리포트 엔진이 직접 조회하는 런타임 catalog, Stage 2 입력/출력 계약을 고정하기 위한 파생 catalog, 그리고 병합 전 단일 ETF source dataset sample이 함께 있다. 현재 CLI와 repository 구현은 런타임 catalog를 우선 사용하며, source dataset sample은 데이터 lineage 확인과 bundle 재생성 기준으로 보존한다.

### 0.1 런타임 catalog/bundle

| 파일 | schemaVersion | 데이터 성격 | 주요 내용 | 용도 | 생성/참조 관계 | CLI/Stage 사용 위치 |
| --- | --- | --- | --- | --- | --- | --- |
| `backend/data/etf_data.json` | `poc.etfMonthlyIssueReport.bundle.v1` | ETF 데이터 병합 bundle | dataset 4개, dataset별 `baseData`, `monthlySnapshots` 3개월, `sourceFiles` | 상품/월별 데이터 조회의 기준 데이터 | 4개 `*.dataset.sample.json`을 병합한 결과이며 Stage 2 catalog의 원천 bundle | CLI `--dataset-id`, `--month-id` 검증과 Stage 2 source/component 조회의 기준 |
| `backend/data/report_templates.json` | `poc.etfReport.templates.v1` | 템플릿 catalog | template 2개, `sourceHtml`, `previewImage`, A4 page 설정 | 시각 템플릿과 preview image 선택 기준 | 데이터셋과 분리된 독립 catalog이며 `etf_data.json`과 판매사 일치 검사를 하지 않음 | CLI `--template-id` 검증과 Stage 1 템플릿 context 생성 |

### 0.2 Stage 2 파생 데이터

| 파일 | schemaVersion | 데이터 성격 | 주요 내용 | 용도 | 생성/참조 관계 | CLI/Stage 사용 위치 |
| --- | --- | --- | --- | --- | --- | --- |
| `backend/data/etf_stage2_component_sources.json` | `poc.etfReport.stage2ComponentSources.v1` | Stage 2 입력 catalog | component source 60개, componentKey 5종, `datasetRef.datasetId`, `snapshotRef.monthId`, payload | `datasetId + monthId + componentKey` 단위로 LLM 또는 sample adapter에 넘길 입력 payload 고정 | `etf_data.json`의 dataset/month 데이터를 컴포넌트 단위로 펼친 파생 데이터 | Stage 2 component source 조회, Novita adapter 입력 경계, 로그의 `component_sources.json` |
| `backend/data/etf_stage2_components.sample.json` | `poc.etfReport.stage2Components.v1` | Stage 2 sample 출력 catalog | 무스타일 HTML component 60개, `componentId`, `dataSourceId`, `chartSpec`, `styled=false` | LLM 없이 Stage 2 출력 계약을 재현하는 sample 결과 | `etf_stage2_component_sources.json`를 기준으로 미리 만든 Stage 2 출력 sample | CLI `--component-mode sample` 실행 시 Stage 2 결과와 component별 HTML 로그 생성 |

### 0.3 병합 전 source dataset sample

아래 4개 파일은 단일 ETF 단위의 원천 sample dataset이다. 각 파일은 `schemaVersion`, legacy/source lineage용 `template.id`, 월별로 변하지 않는 `baseData`, 3개월 `monthlySnapshots`, 시각 후보값인 `styleCandidates`를 가진다. 현재 런타임 조회는 병합 결과인 `etf_data.json`을 사용하므로, 이 파일들의 `template.id`는 CLI `--template-id`가 아니라 병합 전 원천 식별자로 해석한다.

| 파일 | schemaVersion | 기존 원천 template.id | 판매사 | 상품명 | 주요 내용 | 용도 | 생성/참조 관계 | CLI/Stage 사용 위치 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500_H.dataset.sample.json` | `poc.etfMonthlyIssueReport.dataset.v1` | `kb_kodex_monthly_guidebook_449180` | 국민은행 | Kodex 미국 S&P500(H) ETF | 국민은행 월간 가이드북 기반 S&P500 환헤지형 sample, 3개월 snapshot | 병합 전 source 보존, 데이터 lineage 확인, bundle 재생성 기준 | `etf_data.json`의 `sourceFiles[]` 1번과 `data_kodex_us_sp500_h`의 원천 | 런타임 직접 조회 대상 아님 |
| `backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500.dataset.sample.json` | `poc.etfMonthlyIssueReport.dataset.v1` | `kb_kodex_monthly_guidebook_379800` | 국민은행 | Kodex 미국 S&P500 ETF | 국민은행 월간 가이드북 기반 S&P500 비헤지형 sample, 3개월 snapshot | 병합 전 source 보존, 데이터 lineage 확인, bundle 재생성 기준 | `etf_data.json`의 `sourceFiles[]` 2번과 `data_kodex_us_sp500`의 원천 | 런타임 직접 조회 대상 아님 |
| `backend/data/국민은행_월간_가이드북_KODEX_미국나스닥100.dataset.sample.json` | `poc.etfMonthlyIssueReport.dataset.v1` | `kb_kodex_monthly_guidebook_379810` | 국민은행 | Kodex 미국나스닥100 ETF | 국민은행 월간 가이드북 기반 나스닥100 sample, 3개월 snapshot | 병합 전 source 보존, 데이터 lineage 확인, bundle 재생성 기준 | `etf_data.json`의 `sourceFiles[]` 3번과 `data_kodex_us_nasdaq100`의 원천 | 런타임 직접 조회 대상 아님 |
| `backend/data/우리은행_월간_리포트.dataset.sample.json` | `poc.etfMonthlyIssueReport.dataset.v1` | `woori_kodex_monthly_issue_report` | 우리은행 | Kodex 코리아배당성장채권혼합 ETF | 우리은행 월간 리포트 HTML source 기반 sample, 3개월 snapshot | 병합 전 source 보존, 데이터 lineage 확인, bundle 재생성 기준 | `etf_data.json`의 `sourceFiles[]` 4번과 `data_kodex_korea_dividend_growth_bond_mixed`의 원천 | 런타임 직접 조회 대상 아님 |

- 대상 파일: `backend/data/etf_data.json`
- 템플릿 catalog: `backend/data/report_templates.json`
- Stage 2 입력 catalog: `backend/data/etf_stage2_component_sources.json`
- Stage 2 출력 sample: `backend/data/etf_stage2_components.sample.json`
- 병합 스키마: `poc.etfMonthlyIssueReport.bundle.v1`
- 내부 데이터셋 스키마: `poc.etfMonthlyIssueReport.dataset.v1`
- Stage 2 componentSources 스키마: `poc.etfReport.stage2ComponentSources.v1`
- Stage 2 stage2Components 스키마: `poc.etfReport.stage2Components.v1`
- ETF 데이터셋 수: `4`
- 각 ETF 월별 스냅샷: `2026-01`, `2026-02`, `2026-03`
- 작성 목적: PoC 리포트 생성/바인딩에서 사용할 ETF 원천 데이터와 Stage 2 무스타일 컴포넌트 데이터를 빠르게 식별하도록 스키마와 데이터를 표로 정리한다.

## 1. 전체 구조 요약

| 항목 | 값 |
| --- | --- |
| bundle schemaVersion | poc.etfMonthlyIssueReport.bundle.v1 |
| sourceSchemaVersion | poc.etfMonthlyIssueReport.dataset.v1 |
| sourceFiles count | 4 |
| datasetCount | 4 |
| datasets length | 4 |
| 단일 ETF dataset schema | poc.etfMonthlyIssueReport.dataset.v1 |
| 월별 스냅샷 수 | ETF별 3개 |
| 기준 데이터 위치 | `datasets[].baseData` |
| 월별 변동 데이터 위치 | `datasets[].monthlySnapshots[]` |

### 1.1 CLI 입력 변수 값 목록

`report_engine run`은 `dataset-id`, `template-id`, `month-id`를 독립 입력으로 받는다. 데이터셋과 템플릿은 독립 선택 단위이므로 아래 `dataset-id` 4개는 아래 `template-id` 2개와 모두 조합 가능하다.

#### dataset-id

| dataset-id | 상품명 | 기본 판매사 | 기존 원천 template.id | 지원 month-id |
| --- | --- | --- | --- | --- |
| `data_kodex_us_sp500_h` | Kodex 미국 S&P500(H) ETF | 국민은행 | `kb_kodex_monthly_guidebook_449180` | `2026-01`, `2026-02`, `2026-03` |
| `data_kodex_us_sp500` | Kodex 미국 S&P500 ETF | 국민은행 | `kb_kodex_monthly_guidebook_379800` | `2026-01`, `2026-02`, `2026-03` |
| `data_kodex_us_nasdaq100` | Kodex 미국나스닥100 ETF | 국민은행 | `kb_kodex_monthly_guidebook_379810` | `2026-01`, `2026-02`, `2026-03` |
| `data_kodex_korea_dividend_growth_bond_mixed` | Kodex 코리아배당성장채권혼합 ETF | 우리은행 | `woori_kodex_monthly_issue_report` | `2026-01`, `2026-02`, `2026-03` |

#### template-id

| template-id | 템플릿명 | sourceHtml | previewImage | page |
| --- | --- | --- | --- | --- |
| `tpl_kb_monthly_guidebook` | 국민은행 월간 가이드북 | `document/report/우리은행_월간_리포트.html` | `document/report/국민은행_월간_리포트.png` | A4 portrait |
| `tpl_woori_monthly_report` | 우리은행 월간 리포트 | `document/report/우리은행_월간_리포트.html` | `document/report/우리은행_월간_리포트.png` | A4 portrait |

#### month-id

| month-id | 의미 |
| --- | --- |
| `2026-01` | 2026년 1월 스냅샷 |
| `2026-02` | 2026년 2월 스냅샷 |
| `2026-03` | 2026년 3월 스냅샷 |

## 2. 원본 파일 목록

| 순번 | sourceFiles[] | 연결 dataset-id | 기존 원천 template.id |
| --- | --- | --- | --- |
| 1 | backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500_H.dataset.sample.json | `data_kodex_us_sp500_h` | `kb_kodex_monthly_guidebook_449180` |
| 2 | backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500.dataset.sample.json | `data_kodex_us_sp500` | `kb_kodex_monthly_guidebook_379800` |
| 3 | backend/data/국민은행_월간_가이드북_KODEX_미국나스닥100.dataset.sample.json | `data_kodex_us_nasdaq100` | `kb_kodex_monthly_guidebook_379810` |
| 4 | backend/data/우리은행_월간_리포트.dataset.sample.json | `data_kodex_korea_dividend_growth_bond_mixed` | `woori_kodex_monthly_issue_report` |

## 3. 데이터 출처 성격

| sampleDataType | 건수 | 의미 |
| --- | --- | --- |
| source_numeric_with_synthetic_commentary | 3 | 성과/Top 10 등 수치 데이터는 국민은행 가이드북 PPTX 원천 기반이고 리뷰/전망 문구는 synthetic commentary |
| synthetic | 8 | 실제 원천 DB가 없어 PoC 시연용으로 구성한 샘플 데이터 |
| template_source | 1 | 우리은행 HTML 템플릿에 포함된 원천 값을 그대로 반영한 데이터 |

- 국민은행 3건의 `2026-03` 수치 데이터는 `국민은행 월간 가이드북.pptx`에서 추출한 값이다.
- 국민은행 3건의 `review`, `outlook` 문구는 PPTX에 원문이 없으므로 PoC용 synthetic commentary이다.
- 우리은행 `2026-03` 데이터는 `우리은행_월간_리포트.html` 템플릿 source 값이다.

## 4. 전체 스키마 사전

| JSON path | type | 필수 여부 | 설명 |
| --- | --- | --- | --- |
| `$` | object | required | 병합 JSON의 최상위 객체 |
| `$.schemaVersion` | string | required | 병합 파일 스키마 버전. 현재 `poc.etfMonthlyIssueReport.bundle.v1` |
| `$.sourceSchemaVersion` | string | required | 내부 `datasets[]` 항목의 원천 데이터셋 스키마 버전 |
| `$.sourceFiles` | string[] | required | 병합에 사용된 원본 JSON 파일 경로 목록. 배열 순서는 `datasets[]` 순서와 동일 |
| `$.sourceFiles[]` | string | required | 병합 원본 JSON 파일 경로 |
| `$.datasetCount` | number | required | 병합된 ETF 데이터셋 개수 |
| `$.datasets` | Dataset[] | required | ETF별 월간 리포트 데이터셋 배열 |
| `$.datasets[]` | object | required | 단일 ETF 월간 리포트 데이터셋 객체 |
| `$.datasets[].schemaVersion` | string | required | 단일 ETF 데이터셋 스키마 버전. 현재 `poc.etfMonthlyIssueReport.dataset.v1` |
| `$.datasets[].datasetId` | string | required | CLI `--dataset-id`로 사용하는 데이터셋 식별자 |
| `$.datasets[].baseData` | object | required | ETF/판매사/섹션 정의 등 월별로 변하지 않는 기준 데이터 |
| `$.datasets[].baseData.issuer` | object | required | 발행사/운용사 정보 |
| `$.datasets[].baseData.issuer.brandName` | string | required | 브랜드명 |
| `$.datasets[].baseData.issuer.companyNameKo` | string | required | 운용사 한글명 |
| `$.datasets[].baseData.issuer.companyNameEn` | string | required | 운용사 영문명 |
| `$.datasets[].baseData.issuer.teamName` | string | required | 담당 팀명 |
| `$.datasets[].baseData.issuer.contactEmail` | string | required | 담당 연락 이메일 |
| `$.datasets[].baseData.salesChannel` | object | required | 판매사 및 문서 분류 정보 |
| `$.datasets[].baseData.salesChannel.distributorName` | string | required | 판매사명 |
| `$.datasets[].baseData.salesChannel.classificationLabel` | string | required | 문서 분류/배포 라벨 |
| `$.datasets[].baseData.product` | object | required | 상품 기준 정보 |
| `$.datasets[].baseData.product.brandPrefix` | string | required | 상품 브랜드 prefix |
| `$.datasets[].baseData.product.fundName` | string | required | 펀드명 핵심 표기 |
| `$.datasets[].baseData.product.productName` | string | required | 리포트에 표시할 ETF 상품명 |
| `$.datasets[].baseData.product.reportTitleSuffix` | string | required | 리포트 제목 suffix |
| `$.datasets[].baseData.product.benchmarkName` | string | required | 벤치마크 명칭 |
| `$.datasets[].baseData.sectionDefinitions` | object | required | 섹션별 고정 UI/렌더링 정의 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend` | object | required | 성과 추이 섹션 정의 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.title` | string | required | 성과 섹션 제목 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.unit` | string | required | 성과 데이터 단위 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.chartCategories` | string[] | required | 차트 x축 카테고리 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.chartCategories[]` | string | required | 차트 x축 카테고리 단일 항목 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.chartLegend` | string[] | required | 차트 범례 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.chartLegend[]` | string | required | 차트 범례 단일 항목 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.summaryColumns` | string[] | required | 성과 요약표 컬럼 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.summaryColumns[]` | string | required | 성과 요약표 컬럼 단일 항목 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.noteTemplates` | string[] | required | 성과 섹션 하단 주석 템플릿 |
| `$.datasets[].baseData.sectionDefinitions.performanceTrend.noteTemplates[]` | string | required | 성과 섹션 하단 주석 템플릿 단일 항목 |
| `$.datasets[].baseData.sectionDefinitions.topHoldings` | object | required | Top 10 보유내역 섹션 정의 |
| `$.datasets[].baseData.sectionDefinitions.topHoldings.title` | string | required | 보유내역 섹션 제목 |
| `$.datasets[].baseData.sectionDefinitions.topHoldings.columns` | string[] | required | 보유내역 표 컬럼 |
| `$.datasets[].baseData.sectionDefinitions.topHoldings.columns[]` | string | required | 보유내역 표 컬럼 단일 항목 |
| `$.datasets[].baseData.sectionDefinitions.topHoldings.totalLabel` | string | required | 합계 행 라벨 |
| `$.datasets[].baseData.sectionDefinitions.topHoldings.captionTemplates` | string[] | required | 보유내역 caption 템플릿 |
| `$.datasets[].baseData.sectionDefinitions.topHoldings.captionTemplates[]` | string | required | 보유내역 caption 템플릿 단일 항목 |
| `$.datasets[].baseData.sectionDefinitions.review` | object | required | 리뷰 섹션 정의 |
| `$.datasets[].baseData.sectionDefinitions.review.title` | string | required | 리뷰 섹션 제목 |
| `$.datasets[].baseData.sectionDefinitions.review.renderType` | string | required | 리뷰 렌더링 방식 |
| `$.datasets[].baseData.sectionDefinitions.outlook` | object | required | 향후 전망 섹션 정의 |
| `$.datasets[].baseData.sectionDefinitions.outlook.title` | string | required | 전망 섹션 제목 |
| `$.datasets[].baseData.sectionDefinitions.outlook.renderType` | string | required | 전망 렌더링 방식 |
| `$.datasets[].baseData.sectionDefinitions.outlook.numberLabels` | string[] | required | 전망 numbered item 번호 라벨 |
| `$.datasets[].baseData.sectionDefinitions.outlook.numberLabels[]` | string | required | 전망 numbered item 번호 라벨 단일 항목 |
| `$.datasets[].baseData.sectionDefinitions.footer` | object | required | 푸터 주석 정의 |
| `$.datasets[].baseData.sectionDefinitions.footer.note` | string | required | 푸터 고정 주석 |
| `$.datasets[].monthlySnapshots` | MonthlySnapshot[] | required | 월별로 변동되는 데이터 배열 |
| `$.datasets[].monthlySnapshots[]` | object | required | 단일 월별 스냅샷 객체 |
| `$.datasets[].monthlySnapshots[].monthId` | string | required | 월 식별자. 형식 `YYYY-MM` |
| `$.datasets[].monthlySnapshots[].periodLabel` | string | required | 월 표시 라벨 |
| `$.datasets[].monthlySnapshots[].asOf` | string | required | 기준일. 형식 `YYYY.MM.DD` |
| `$.datasets[].monthlySnapshots[].asOfKo` | string | required | 기준일 한글 표시 |
| `$.datasets[].monthlySnapshots[].sampleDataType` | string | required | 해당 월 데이터의 출처/샘플 성격 |
| `$.datasets[].monthlySnapshots[].performanceTrend` | object | required | 월별 성과 데이터 |
| `$.datasets[].monthlySnapshots[].performanceTrend.chartSeries` | ChartSeries[] | required | 차트용 ETF/BM 시계열 배열 |
| `$.datasets[].monthlySnapshots[].performanceTrend.chartSeries[]` | object | required | 단일 차트 series 객체 |
| `$.datasets[].monthlySnapshots[].performanceTrend.chartSeries[].name` | string | required | 차트 series 이름 |
| `$.datasets[].monthlySnapshots[].performanceTrend.chartSeries[].values` | number[] | required | 차트 카테고리 순서에 대응하는 성과값 |
| `$.datasets[].monthlySnapshots[].performanceTrend.chartSeries[].values[]` | number | required | 차트 카테고리 단일 성과값 |
| `$.datasets[].monthlySnapshots[].performanceTrend.summaryValues` | number[] | required | 성과 요약표 컬럼 순서에 대응하는 ETF 성과값 |
| `$.datasets[].monthlySnapshots[].performanceTrend.summaryValues[]` | number | required | 성과 요약표 단일 성과값 |
| `$.datasets[].monthlySnapshots[].topHoldings` | object | required | 월별 Top 10 보유내역 |
| `$.datasets[].monthlySnapshots[].topHoldings.rows` | HoldingRow[] | required | Top 10 보유종목 행 배열 |
| `$.datasets[].monthlySnapshots[].topHoldings.rows[]` | object | required | 단일 보유종목 행 객체 |
| `$.datasets[].monthlySnapshots[].topHoldings.rows[].rank` | number | required | 보유종목 순위 |
| `$.datasets[].monthlySnapshots[].topHoldings.rows[].name` | string | required | 보유종목명 |
| `$.datasets[].monthlySnapshots[].topHoldings.rows[].weightPercent` | number | required | 보유비중(%) |
| `$.datasets[].monthlySnapshots[].topHoldings.top10TotalWeightPercent` | number | required | Top 10 보유비중 합계 |
| `$.datasets[].monthlySnapshots[].topHoldings.totalHoldingCount` | number | required | 전체 보유종목 수 |
| `$.datasets[].monthlySnapshots[].review` | object | required | 월별 ETF 리뷰 데이터 |
| `$.datasets[].monthlySnapshots[].review.items` | string[] | required | 리뷰 bullet 문구 배열 |
| `$.datasets[].monthlySnapshots[].review.items[]` | string | required | 리뷰 bullet 단일 문구 |
| `$.datasets[].monthlySnapshots[].outlook` | object | required | 월별 ETF 향후 전망 데이터 |
| `$.datasets[].monthlySnapshots[].outlook.lead` | string | required | 전망 도입 문구 |
| `$.datasets[].monthlySnapshots[].outlook.numberedItems` | NumberedOutlookItem[] | required | 번호가 붙는 전망 문구 배열 |
| `$.datasets[].monthlySnapshots[].outlook.numberedItems[]` | object | required | 단일 numbered outlook item 객체 |
| `$.datasets[].monthlySnapshots[].outlook.numberedItems[].number` | string | required | 번호 라벨 |
| `$.datasets[].monthlySnapshots[].outlook.numberedItems[].text` | string | required | 전망 본문 |
| `$.datasets[].monthlySnapshots[].outlook.numberedItems[].highlightText` | string | optional | 본문 중 강조 표시할 부분 문자열. 일부 item에만 존재 |
| `$.datasets[].monthlySnapshots[].outlook.closing` | string | required | 전망 마무리 문구 |
| `$.datasets[].styleCandidates` | object | required | 템플릿 스타일 후보 정의 |
| `$.datasets[].styleCandidates.theme` | object | required | 색상 테마 후보 |
| `$.datasets[].styleCandidates.theme.primary` | string | required | 주 색상 |
| `$.datasets[].styleCandidates.theme.chartBlue` | string | required | ETF 차트 색상 |
| `$.datasets[].styleCandidates.theme.benchmarkGray` | string | required | BM 차트 색상 |
| `$.datasets[].styleCandidates.theme.tableHeaderBlue` | string | required | 표 헤더 색상 |
| `$.datasets[].styleCandidates.theme.ruleGray` | string | required | 구분선 색상 |
| `$.datasets[].styleCandidates.theme.paper` | string | required | 배경 색상 |
| `$.datasets[].styleCandidates.layout` | object | required | 레이아웃 후보 |
| `$.datasets[].styleCandidates.layout.pageSize` | string | required | 페이지 크기/방향 설명 |
| `$.datasets[].styleCandidates.layout.columns` | number | required | 본문 컬럼 수 |
| `$.datasets[].styleCandidates.layout.mainSections` | string[] | required | 주요 렌더링 섹션 순서 |
| `$.datasets[].styleCandidates.layout.mainSections[]` | string | required | 주요 렌더링 섹션 단일 항목 |

## 5. 선택 필드와 배열 길이

| 필드/배열 | 현재 값/길이 | 설명 |
| --- | --- | --- |
| `datasets[]` | 4 | 병합된 ETF 데이터셋 수 |
| `datasets[].monthlySnapshots[]` | 3 | 각 ETF별 월별 스냅샷 수 |
| `monthlySnapshots[].performanceTrend.chartSeries[]` | 2 | ETF series와 BM series |
| `chartSeries[].values[]` | 5 | `1개월`, `3개월`, `6개월`, `1년`, `상장이후` 순서 |
| `performanceTrend.summaryValues[]` | 6 | `1개월`, `3개월`, `6개월`, `1년`, `연초후`, `상장후` 순서 |
| `topHoldings.rows[]` | 10 | Top 10 보유내역 |
| `review.items[]` | 4 | 월별 리뷰 bullet 수 |
| `outlook.numberedItems[]` | 3 | 월별 전망 numbered item 수 |
| `outlook.numberedItems[].highlightText` | optional | 각 월의 두 번째 numbered item에만 존재하는 강조 문자열 |

## 6. ETF 데이터셋 목록

| 순번 | datasetId | 기존 원천 template.id | 판매사 | 분류 | 상품명 | BM | 월수 | source file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `data_kodex_us_sp500_h` | `kb_kodex_monthly_guidebook_449180` | 국민은행 | 월간 가이드북 | Kodex 미국 S&P500(H) ETF | S&P500 Index | 3 | backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500_H.dataset.sample.json |
| 2 | `data_kodex_us_sp500` | `kb_kodex_monthly_guidebook_379800` | 국민은행 | 월간 가이드북 | Kodex 미국 S&P500 ETF | S&P500 Index | 3 | backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500.dataset.sample.json |
| 3 | `data_kodex_us_nasdaq100` | `kb_kodex_monthly_guidebook_379810` | 국민은행 | 월간 가이드북 | Kodex 미국나스닥100 ETF | NASDAQ 100 Index | 3 | backend/data/국민은행_월간_가이드북_KODEX_미국나스닥100.dataset.sample.json |
| 4 | `data_kodex_korea_dividend_growth_bond_mixed` | `woori_kodex_monthly_issue_report` | 우리은행 | 판매사 사내한 | Kodex 코리아배당성장채권혼합 ETF | 배당성장 채권혼합지수 | 3 | backend/data/우리은행_월간_리포트.dataset.sample.json |

## 7. 기준 데이터 상세

| dataset | datasetId | 기존 원천 template.id | brandName | companyNameKo | companyNameEn | teamName | contactEmail | distributorName | classificationLabel | brandPrefix | fundName | productName | reportTitleSuffix | benchmarkName | primary | chartBlue | benchmarkGray | tableHeaderBlue | ruleGray | paper | layout.pageSize | layout.columns | layout.mainSections |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1: Kodex 미국 S&P500(H) ETF | `data_kodex_us_sp500_h` | `kb_kodex_monthly_guidebook_449180` | Kodex | 삼성자산운용 | Samsung Asset Management | 삼성자산운용 연금마케팅팀 | pension.fund@samsung.com | 국민은행 | 월간 가이드북 | Kodex | 미국 S&P500(H) | Kodex 미국 S&P500(H) ETF | 월간 가이드북 | S&P500 Index | #0258ff | #1967f2 | #8e8e8e | #2d66f3 | #c4c4c4 | #ffffff | A4 portrait | 2 | performanceTrend, topHoldings, review, outlook |
| D2: Kodex 미국 S&P500 ETF | `data_kodex_us_sp500` | `kb_kodex_monthly_guidebook_379800` | Kodex | 삼성자산운용 | Samsung Asset Management | 삼성자산운용 연금마케팅팀 | pension.fund@samsung.com | 국민은행 | 월간 가이드북 | Kodex | 미국 S&P500 | Kodex 미국 S&P500 ETF | 월간 가이드북 | S&P500 Index | #0258ff | #1967f2 | #8e8e8e | #2d66f3 | #c4c4c4 | #ffffff | A4 portrait | 2 | performanceTrend, topHoldings, review, outlook |
| D3: Kodex 미국나스닥100 ETF | `data_kodex_us_nasdaq100` | `kb_kodex_monthly_guidebook_379810` | Kodex | 삼성자산운용 | Samsung Asset Management | 삼성자산운용 연금마케팅팀 | pension.fund@samsung.com | 국민은행 | 월간 가이드북 | Kodex | 미국나스닥100 | Kodex 미국나스닥100 ETF | 월간 가이드북 | NASDAQ 100 Index | #0258ff | #1967f2 | #8e8e8e | #2d66f3 | #c4c4c4 | #ffffff | A4 portrait | 2 | performanceTrend, topHoldings, review, outlook |
| D4: Kodex 코리아배당성장채권혼합 ETF | `data_kodex_korea_dividend_growth_bond_mixed` | `woori_kodex_monthly_issue_report` | Kodex | 삼성자산운용 | Samsung Asset Management | 삼성자산운용 연금마케팅팀 | pension.fund@samsung.com | 우리은행 | 판매사 사내한 | Kodex | 코리아배당성장채권혼합 | Kodex 코리아배당성장채권혼합 ETF | 이슈 리포트 | 배당성장 채권혼합지수 | #0258ff | #1967f2 | #8e8e8e | #2d66f3 | #c4c4c4 | #ffffff | A4 portrait | 2 | performanceTrend, topHoldings, review, outlook |

## 8. 섹션 정의 상세

| dataset | 성과 제목 | 단위 | 차트 카테고리 | 차트 범례 | 성과표 컬럼 | 성과 주석 템플릿 | Top10 제목 | Top10 컬럼 | 합계 라벨 | Top10 caption 템플릿 | 리뷰 제목 | 리뷰 렌더 | 전망 제목 | 전망 렌더 | 전망 번호 | footer note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1: Kodex 미국 S&P500(H) ETF | ETF 성과 추이 | % | 1개월, 3개월, 6개월, 1년, 상장이후 | Kodex 미국 S&P500(H), BM | 1개월, 3개월, 6개월, 1년, 연초후, 상장후 | 자료 : 삼성자산운용 {asOfKo} 기준, 단위 : %<br>BM : S&P500 Index<br>(ETF) 분배금이 재투자된 수정기준가 활용, 세전 수익률 기준<br>과거수익률이 미래성과를 보장하지 않습니다. | ETF Top 10 보유내역 | No., 종목명, 보유비중(%) | 합계 | 총 보유종목 수: {totalHoldingCount}개<br>자료 : 삼성자산운용, {asOfKo} 기준 | Kodex 미국 S&P500(H) ETF 리뷰 | bullet-list | Kodex 미국 S&P500(H) ETF 향후 전망 | lead-numbered-closing-list | ①, ②, ③ | 상기 내용은 증권사 애널리스트 의견을 종합하여 작성한 것으로, 향후 시장 상황에 따라 변경 될 수 있습니다. |
| D2: Kodex 미국 S&P500 ETF | ETF 성과 추이 | % | 1개월, 3개월, 6개월, 1년, 상장이후 | Kodex 미국 S&P500, BM | 1개월, 3개월, 6개월, 1년, 연초후, 상장후 | 자료 : 삼성자산운용 {asOfKo} 기준, 단위 : %<br>BM : S&P500 Index<br>(ETF) 분배금이 재투자된 수정기준가 활용, 세전 수익률 기준<br>과거수익률이 미래성과를 보장하지 않습니다. | ETF Top 10 보유내역 | No., 종목명, 보유비중(%) | 합계 | 총 보유종목 수: {totalHoldingCount}개<br>자료 : 삼성자산운용, {asOfKo} 기준 | Kodex 미국 S&P500 ETF 리뷰 | bullet-list | Kodex 미국 S&P500 ETF 향후 전망 | lead-numbered-closing-list | ①, ②, ③ | 상기 내용은 증권사 애널리스트 의견을 종합하여 작성한 것으로, 향후 시장 상황에 따라 변경 될 수 있습니다. |
| D3: Kodex 미국나스닥100 ETF | ETF 성과 추이 | % | 1개월, 3개월, 6개월, 1년, 상장이후 | Kodex 미국나스닥100, BM | 1개월, 3개월, 6개월, 1년, 연초후, 상장후 | 자료 : 삼성자산운용 {asOfKo} 기준, 단위 : %<br>BM : NASDAQ 100 Index<br>(ETF) 분배금이 재투자된 수정기준가 활용, 세전 수익률 기준<br>과거수익률이 미래성과를 보장하지 않습니다. | ETF Top 10 보유내역 | No., 종목명, 보유비중(%) | 합계 | 총 보유종목 수: {totalHoldingCount}개<br>자료 : 삼성자산운용, {asOfKo} 기준 | Kodex 미국나스닥100 ETF 리뷰 | bullet-list | Kodex 미국나스닥100 ETF 향후 전망 | lead-numbered-closing-list | ①, ②, ③ | 상기 내용은 증권사 애널리스트 의견을 종합하여 작성한 것으로, 향후 시장 상황에 따라 변경 될 수 있습니다. |
| D4: Kodex 코리아배당성장채권혼합 ETF | ETF 성과 추이 | % | 1개월, 3개월, 6개월, 1년, 상장이후 | Kodex 코리아배당성장채권혼합, BM | 1개월, 3개월, 6개월, 1년, 연초후, 상장후 | 자료 : 삼성자산운용 {asOfKo} 기준, 단위 : %<br>BM : 배당성장 채권혼합지수<br>(ETF) 분배금이 재투자된 수정기준가 활용, 세전 수익률 기준<br>과거수익률이 미래성과를 보장하지 않습니다. | ETF Top 10 보유내역 | No., 종목명, 보유비중(%) | 합계 | 총 보유종목 수: {totalHoldingCount}개<br>자료 : 삼성자산운용, {asOfKo} 기준 | Kodex 코리아배당성장채권혼합 ETF 리뷰 | bullet-list | Kodex 코리아배당성장채권혼합 ETF 향후 전망 | lead-numbered-closing-list | ①, ②, ③ | 상기 내용은 증권사 애널리스트 의견을 종합하여 작성한 것으로, 향후 시장 상황에 따라 변경 될 수 있습니다. |

## 9. 월별 스냅샷 요약

| dataset | monthId | periodLabel | asOf | asOfKo | sampleDataType | chartSeries 수 | summaryValues 수 | Top10 rows 수 | Top10 합계 | 총 보유종목 수 | review items 수 | outlook numbered 수 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1: Kodex 미국 S&P500(H) ETF | 2026-01 | 2026년 1월 | 2026.01.31 | 2026년 1월 31일 | synthetic | 2 | 6 | 10 | 37.12 | 507 | 4 | 3 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-02 | 2026년 2월 | 2026.02.28 | 2026년 2월 28일 | synthetic | 2 | 6 | 10 | 37.29 | 507 | 4 | 3 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-03 | 2026년 3월 | 2026.03.31 | 2026년 3월 31일 | source_numeric_with_synthetic_commentary | 2 | 6 | 10 | 37.46 | 507 | 4 | 3 |
| D2: Kodex 미국 S&P500 ETF | 2026-01 | 2026년 1월 | 2026.01.31 | 2026년 1월 31일 | synthetic | 2 | 6 | 10 | 37.11 | 505 | 4 | 3 |
| D2: Kodex 미국 S&P500 ETF | 2026-02 | 2026년 2월 | 2026.02.28 | 2026년 2월 28일 | synthetic | 2 | 6 | 10 | 37.27 | 505 | 4 | 3 |
| D2: Kodex 미국 S&P500 ETF | 2026-03 | 2026년 3월 | 2026.03.31 | 2026년 3월 31일 | source_numeric_with_synthetic_commentary | 2 | 6 | 10 | 37.37 | 505 | 4 | 3 |
| D3: Kodex 미국나스닥100 ETF | 2026-01 | 2026년 1월 | 2026.01.31 | 2026년 1월 31일 | synthetic | 2 | 6 | 10 | 50.60 | 102 | 4 | 3 |
| D3: Kodex 미국나스닥100 ETF | 2026-02 | 2026년 2월 | 2026.02.28 | 2026년 2월 28일 | synthetic | 2 | 6 | 10 | 50.91 | 102 | 4 | 3 |
| D3: Kodex 미국나스닥100 ETF | 2026-03 | 2026년 3월 | 2026.03.31 | 2026년 3월 31일 | source_numeric_with_synthetic_commentary | 2 | 6 | 10 | 51.27 | 102 | 4 | 3 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-01 | 2026년 1월 | 2026.01.31 | 2026년 1월 31일 | synthetic | 2 | 6 | 10 | 89.30 | 58 | 4 | 3 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-02 | 2026년 2월 | 2026.02.28 | 2026년 2월 28일 | synthetic | 2 | 6 | 10 | 89.57 | 58 | 4 | 3 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-03 | 2026년 3월 | 2026.03.31 | 2026년 3월 31일 | template_source | 2 | 6 | 10 | 90.00 | 58 | 4 | 3 |

## 10. 성과 요약표 데이터

| dataset | monthId | 1개월 | 3개월 | 6개월 | 1년 | 연초후 | 상장후 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1: Kodex 미국 S&P500(H) ETF | 2026-01 | 1.42 | 8.90 | 1.35 | 12.06 | 1.42 | 44.82 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-02 | 0.86 | 10.44 | 2.36 | 13.14 | 2.29 | 46.91 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-03 | 2.91 | 13.92 | 3.94 | 15.37 | 13.92 | 50.20 |
| D2: Kodex 미국 S&P500 ETF | 2026-01 | 2.84 | 7.92 | -1.18 | 16.42 | 2.84 | 95.20 |
| D2: Kodex 미국 S&P500 ETF | 2026-02 | 1.18 | 8.66 | -0.42 | 17.34 | 4.05 | 97.46 |
| D2: Kodex 미국 S&P500 ETF | 2026-03 | 5.95 | 11.97 | 0.56 | 19.09 | 11.97 | 101.13 |
| D3: Kodex 미국나스닥100 ETF | 2026-01 | 3.10 | 10.82 | 0.42 | 21.18 | 3.10 | 105.40 |
| D3: Kodex 미국나스닥100 ETF | 2026-02 | 2.24 | 12.95 | 1.28 | 22.46 | 5.41 | 108.62 |
| D3: Kodex 미국나스닥100 ETF | 2026-03 | 6.45 | 16.72 | 3.86 | 25.70 | 16.72 | 113.70 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-01 | 3.24 | 8.41 | 11.83 | 22.36 | 3.24 | 60.18 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-02 | -1.36 | 7.86 | 10.42 | 20.77 | 1.84 | 58.02 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-03 | -4.89 | 6.65 | 9.55 | 19.69 | 6.65 | 55.81 |

## 11. 차트 데이터

| dataset | monthId | series | 1개월 | 3개월 | 6개월 | 1년 | 상장이후 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1: Kodex 미국 S&P500(H) ETF | 2026-01 | Kodex 미국 S&P500(H) | 1.4 | 8.9 | 1.4 | 12.1 | 44.8 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-01 | BM | 1.6 | 9.2 | 1.8 | 13.2 | 49.2 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-02 | Kodex 미국 S&P500(H) | 0.9 | 10.4 | 2.4 | 13.1 | 46.9 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-02 | BM | 1.0 | 10.9 | 3.0 | 14.5 | 52.1 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-03 | Kodex 미국 S&P500(H) | 2.9 | 13.9 | 3.9 | 15.4 | 50.2 |
| D1: Kodex 미국 S&P500(H) ETF | 2026-03 | BM | 3.1 | 14.4 | 4.8 | 17.0 | 56.1 |
| D2: Kodex 미국 S&P500 ETF | 2026-01 | Kodex 미국 S&P500 | 2.8 | 7.9 | -1.2 | 16.4 | 95.2 |
| D2: Kodex 미국 S&P500 ETF | 2026-01 | BM | 2.6 | 7.6 | -1.4 | 16.3 | 98.1 |
| D2: Kodex 미국 S&P500 ETF | 2026-02 | Kodex 미국 S&P500 | 1.2 | 8.7 | -0.4 | 17.3 | 97.5 |
| D2: Kodex 미국 S&P500 ETF | 2026-02 | BM | 1.0 | 8.4 | -0.6 | 17.4 | 100.0 |
| D2: Kodex 미국 S&P500 ETF | 2026-03 | Kodex 미국 S&P500 | 6.0 | 12.0 | 0.6 | 19.1 | 101.1 |
| D2: Kodex 미국 S&P500 ETF | 2026-03 | BM | 5.7 | 11.7 | 0.4 | 19.2 | 104.2 |
| D3: Kodex 미국나스닥100 ETF | 2026-01 | Kodex 미국나스닥100 | 3.1 | 10.8 | 0.4 | 21.2 | 105.4 |
| D3: Kodex 미국나스닥100 ETF | 2026-01 | BM | 2.9 | 10.5 | 0.3 | 21.3 | 108.0 |
| D3: Kodex 미국나스닥100 ETF | 2026-02 | Kodex 미국나스닥100 | 2.2 | 12.9 | 1.3 | 22.5 | 108.6 |
| D3: Kodex 미국나스닥100 ETF | 2026-02 | BM | 2.1 | 12.7 | 1.1 | 22.7 | 111.2 |
| D3: Kodex 미국나스닥100 ETF | 2026-03 | Kodex 미국나스닥100 | 6.5 | 16.7 | 3.9 | 25.7 | 113.7 |
| D3: Kodex 미국나스닥100 ETF | 2026-03 | BM | 6.2 | 16.5 | 3.7 | 25.8 | 116.6 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-01 | Kodex 코리아배당성장채권혼합 | 3.2 | 8.4 | 11.8 | 22.4 | 60.2 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-01 | BM | 2.9 | 7.8 | 11.1 | 21.7 | 50.4 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-02 | Kodex 코리아배당성장채권혼합 | -1.4 | 7.9 | 10.4 | 20.8 | 58.0 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-02 | BM | -1.6 | 7.2 | 9.9 | 20.2 | 48.3 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-03 | Kodex 코리아배당성장채권혼합 | -4.9 | 6.7 | 9.6 | 19.7 | 55.8 |
| D4: Kodex 코리아배당성장채권혼합 ETF | 2026-03 | BM | -5.2 | 6.4 | 9.2 | 19.5 | 45.7 |

## 12. Top 10 보유내역 데이터


### D1: Kodex 미국 S&P500(H) ETF

| monthId | rank | name | weightPercent | top10TotalWeightPercent | totalHoldingCount |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | 1 | NVIDIA Corp | 7.48 | 37.12 | 507 |
| 2026-01 | 2 | MICROSOFT | 6.96 | 37.12 | 507 |
| 2026-01 | 3 | APPLE Inc | 5.85 | 37.12 | 507 |
| 2026-01 | 4 | Amazon.com Inc | 3.86 | 37.12 | 507 |
| 2026-01 | 5 | Meta Platforms | 2.69 | 37.12 | 507 |
| 2026-01 | 6 | iShares S&P500 Index Fund | 2.61 | 37.12 | 507 |
| 2026-01 | 7 | BROADCOM LTD | 2.44 | 37.12 | 507 |
| 2026-01 | 8 | ALPHABET INC-CL A | 2.01 | 37.12 | 507 |
| 2026-01 | 9 | ALPHABET INC-CL C | 1.64 | 37.12 | 507 |
| 2026-01 | 10 | TESLA MOTORS | 1.58 | 37.12 | 507 |
| 2026-02 | 1 | NVIDIA Corp | 7.60 | 37.29 | 507 |
| 2026-02 | 2 | MICROSOFT | 6.91 | 37.29 | 507 |
| 2026-02 | 3 | APPLE Inc | 5.76 | 37.29 | 507 |
| 2026-02 | 4 | Amazon.com Inc | 3.90 | 37.29 | 507 |
| 2026-02 | 5 | Meta Platforms | 2.72 | 37.29 | 507 |
| 2026-02 | 6 | iShares S&P500 Index Fund | 2.64 | 37.29 | 507 |
| 2026-02 | 7 | BROADCOM LTD | 2.48 | 37.29 | 507 |
| 2026-02 | 8 | ALPHABET INC-CL A | 2.03 | 37.29 | 507 |
| 2026-02 | 9 | ALPHABET INC-CL C | 1.65 | 37.29 | 507 |
| 2026-02 | 10 | TESLA MOTORS | 1.60 | 37.29 | 507 |
| 2026-03 | 1 | NVIDIA Corp | 7.71 | 37.46 | 507 |
| 2026-03 | 2 | MICROSOFT | 6.87 | 37.46 | 507 |
| 2026-03 | 3 | APPLE Inc | 5.69 | 37.46 | 507 |
| 2026-03 | 4 | Amazon.com Inc | 3.93 | 37.46 | 507 |
| 2026-03 | 5 | Meta Platforms | 2.74 | 37.46 | 507 |
| 2026-03 | 6 | iShares S&P500 Index Fund | 2.67 | 37.46 | 507 |
| 2026-03 | 7 | BROADCOM LTD | 2.52 | 37.46 | 507 |
| 2026-03 | 8 | ALPHABET INC-CL A | 2.05 | 37.46 | 507 |
| 2026-03 | 9 | ALPHABET INC-CL C | 1.66 | 37.46 | 507 |
| 2026-03 | 10 | TESLA MOTORS | 1.62 | 37.46 | 507 |

### D2: Kodex 미국 S&P500 ETF

| monthId | rank | name | weightPercent | top10TotalWeightPercent | totalHoldingCount |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | 1 | NVIDIA Corp | 7.62 | 37.11 | 505 |
| 2026-01 | 2 | MICROSOFT | 7.15 | 37.11 | 505 |
| 2026-01 | 3 | APPLE Inc | 6.08 | 37.11 | 505 |
| 2026-01 | 4 | Amazon.com Inc | 3.96 | 37.11 | 505 |
| 2026-01 | 5 | Meta Platforms | 2.75 | 37.11 | 505 |
| 2026-01 | 6 | BROADCOM LTD | 2.43 | 37.11 | 505 |
| 2026-01 | 7 | ALPHABET INC-CL A | 2.06 | 37.11 | 505 |
| 2026-01 | 8 | ALPHABET INC-CL C | 1.69 | 37.11 | 505 |
| 2026-01 | 9 | TESLA MOTORS | 1.73 | 37.11 | 505 |
| 2026-01 | 10 | BERKSHIRE HATHAWAY | 1.64 | 37.11 | 505 |
| 2026-02 | 1 | NVIDIA Corp | 7.78 | 37.27 | 505 |
| 2026-02 | 2 | MICROSOFT | 7.10 | 37.27 | 505 |
| 2026-02 | 3 | APPLE Inc | 5.96 | 37.27 | 505 |
| 2026-02 | 4 | Amazon.com Inc | 4.02 | 37.27 | 505 |
| 2026-02 | 5 | Meta Platforms | 2.79 | 37.27 | 505 |
| 2026-02 | 6 | BROADCOM LTD | 2.51 | 37.27 | 505 |
| 2026-02 | 7 | ALPHABET INC-CL A | 2.09 | 37.27 | 505 |
| 2026-02 | 8 | ALPHABET INC-CL C | 1.70 | 37.27 | 505 |
| 2026-02 | 9 | TESLA MOTORS | 1.69 | 37.27 | 505 |
| 2026-02 | 10 | BERKSHIRE HATHAWAY | 1.63 | 37.27 | 505 |
| 2026-03 | 1 | NVIDIA Corp | 7.93 | 37.37 | 505 |
| 2026-03 | 2 | MICROSOFT | 7.05 | 37.37 | 505 |
| 2026-03 | 3 | APPLE Inc | 5.84 | 37.37 | 505 |
| 2026-03 | 4 | Amazon.com Inc | 4.04 | 37.37 | 505 |
| 2026-03 | 5 | Meta Platforms | 2.81 | 37.37 | 505 |
| 2026-03 | 6 | BROADCOM LTD | 2.59 | 37.37 | 505 |
| 2026-03 | 7 | ALPHABET INC-CL A | 2.11 | 37.37 | 505 |
| 2026-03 | 8 | ALPHABET INC-CL C | 1.71 | 37.37 | 505 |
| 2026-03 | 9 | TESLA MOTORS | 1.67 | 37.37 | 505 |
| 2026-03 | 10 | BERKSHIRE HATHAWAY | 1.62 | 37.37 | 505 |

### D3: Kodex 미국나스닥100 ETF

| monthId | rank | name | weightPercent | top10TotalWeightPercent | totalHoldingCount |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | 1 | NVIDIA Corp | 9.54 | 50.60 | 102 |
| 2026-01 | 2 | MICROSOFT | 8.96 | 50.60 | 102 |
| 2026-01 | 3 | APPLE Inc | 7.52 | 50.60 | 102 |
| 2026-01 | 4 | Amazon.com Inc | 5.51 | 50.60 | 102 |
| 2026-01 | 5 | BROADCOM LTD | 5.08 | 50.60 | 102 |
| 2026-01 | 6 | Meta Platforms | 3.44 | 50.60 | 102 |
| 2026-01 | 7 | NETFLIX | 2.74 | 50.60 | 102 |
| 2026-01 | 8 | TESLA MOTORS | 2.82 | 50.60 | 102 |
| 2026-01 | 9 | ALPHABET INC-CL A | 2.57 | 50.60 | 102 |
| 2026-01 | 10 | ALPHABET INC-CL C | 2.42 | 50.60 | 102 |
| 2026-02 | 1 | NVIDIA Corp | 9.72 | 50.91 | 102 |
| 2026-02 | 2 | MICROSOFT | 8.89 | 50.91 | 102 |
| 2026-02 | 3 | APPLE Inc | 7.42 | 50.91 | 102 |
| 2026-02 | 4 | Amazon.com Inc | 5.59 | 50.91 | 102 |
| 2026-02 | 5 | BROADCOM LTD | 5.22 | 50.91 | 102 |
| 2026-02 | 6 | Meta Platforms | 3.48 | 50.91 | 102 |
| 2026-02 | 7 | NETFLIX | 2.78 | 50.91 | 102 |
| 2026-02 | 8 | TESLA MOTORS | 2.76 | 50.91 | 102 |
| 2026-02 | 9 | ALPHABET INC-CL A | 2.60 | 50.91 | 102 |
| 2026-02 | 10 | ALPHABET INC-CL C | 2.45 | 50.91 | 102 |
| 2026-03 | 1 | NVIDIA Corp | 9.92 | 51.27 | 102 |
| 2026-03 | 2 | MICROSOFT | 8.82 | 51.27 | 102 |
| 2026-03 | 3 | APPLE Inc | 7.31 | 51.27 | 102 |
| 2026-03 | 4 | Amazon.com Inc | 5.68 | 51.27 | 102 |
| 2026-03 | 5 | BROADCOM LTD | 5.36 | 51.27 | 102 |
| 2026-03 | 6 | Meta Platforms | 3.52 | 51.27 | 102 |
| 2026-03 | 7 | NETFLIX | 2.83 | 51.27 | 102 |
| 2026-03 | 8 | TESLA MOTORS | 2.71 | 51.27 | 102 |
| 2026-03 | 9 | ALPHABET INC-CL A | 2.64 | 51.27 | 102 |
| 2026-03 | 10 | ALPHABET INC-CL C | 2.48 | 51.27 | 102 |

### D4: Kodex 코리아배당성장채권혼합 ETF

| monthId | rank | name | weightPercent | top10TotalWeightPercent | totalHoldingCount |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | 1 | 국고02250-2806(25-4) | 20.52 | 89.30 | 58 |
| 2026-01 | 2 | KODEX 국고채3년 | 17.44 | 89.30 | 58 |
| 2026-01 | 3 | KODEX 코리아배당성장 | 16.86 | 89.30 | 58 |
| 2026-01 | 4 | 국고02500-3009(25-8) | 16.01 | 89.30 | 58 |
| 2026-01 | 5 | 국고02750-2812(25-10) | 15.21 | 89.30 | 58 |
| 2026-01 | 6 | 현대차 | 0.76 | 89.30 | 58 |
| 2026-01 | 7 | 키움증권 | 0.67 | 89.30 | 58 |
| 2026-01 | 8 | DB손해보험 | 0.63 | 89.30 | 58 |
| 2026-01 | 9 | NH투자증권 | 0.61 | 89.30 | 58 |
| 2026-01 | 10 | 기아 | 0.59 | 89.30 | 58 |
| 2026-02 | 1 | 국고02250-2806(25-4) | 20.68 | 89.57 | 58 |
| 2026-02 | 2 | KODEX 국고채3년 | 17.33 | 89.57 | 58 |
| 2026-02 | 3 | KODEX 코리아배당성장 | 16.98 | 89.57 | 58 |
| 2026-02 | 4 | 국고02500-3009(25-8) | 16.20 | 89.57 | 58 |
| 2026-02 | 5 | 국고02750-2812(25-10) | 15.27 | 89.57 | 58 |
| 2026-02 | 6 | 현대차 | 0.75 | 89.57 | 58 |
| 2026-02 | 7 | 키움증권 | 0.64 | 89.57 | 58 |
| 2026-02 | 8 | DB손해보험 | 0.61 | 89.57 | 58 |
| 2026-02 | 9 | NH투자증권 | 0.57 | 89.57 | 58 |
| 2026-02 | 10 | 기아 | 0.54 | 89.57 | 58 |
| 2026-03 | 1 | 국고02250-2806(25-4) | 20.84 | 90.00 | 58 |
| 2026-03 | 2 | KODEX 국고채3년 | 17.29 | 90.00 | 58 |
| 2026-03 | 3 | KODEX 코리아배당성장 | 17.12 | 90.00 | 58 |
| 2026-03 | 4 | 국고02500-3009(25-8) | 16.35 | 90.00 | 58 |
| 2026-03 | 5 | 국고02750-2812(25-10) | 15.32 | 90.00 | 58 |
| 2026-03 | 6 | 현대차 | 0.74 | 90.00 | 58 |
| 2026-03 | 7 | 키움증권 | 0.61 | 90.00 | 58 |
| 2026-03 | 8 | DB손해보험 | 0.59 | 90.00 | 58 |
| 2026-03 | 9 | NH투자증권 | 0.57 | 90.00 | 58 |
| 2026-03 | 10 | 기아 | 0.57 | 90.00 | 58 |

## 13. 리뷰 데이터


### D1: Kodex 미국 S&P500(H) ETF

| monthId | bulletNo | review.items[] |
| --- | --- | --- |
| 2026-01 | 1 | 미국 대형주 반등이 ETF 성과에 기여했으나 환헤지 비용과 금리 변동성이 일부 부담으로 작용 |
| 2026-01 | 2 | NVIDIA, MICROSOFT, APPLE 등 핵심 종목의 비중이 높은 수준을 유지하며 지수 추종 성과를 견인 |
| 2026-01 | 3 | 환헤지 시행 구조로 원달러 환율 변화에 따른 수익률 흔들림은 비헤지형 대비 제한 |
| 2026-01 | 4 | S&P500 내 우량 대형주 분산 효과가 월간 변동성 확대 구간에서 방어력을 제공 |
| 2026-02 | 1 | 미국 물가 지표와 금리 재평가로 주식시장 등락이 확대되며 1개월 성과는 완만한 플러스에 그침 |
| 2026-02 | 2 | 상위 기술주와 플랫폼 기업의 실적 기대는 유지되었지만 일부 소비재와 전기차 관련 종목은 조정 |
| 2026-02 | 3 | 환헤지 구조로 환율 상승 수혜는 제한되었으나 원화 변동에 따른 불확실성은 낮아짐 |
| 2026-02 | 4 | 3개월 성과는 두 자릿수 수준을 유지하며 미국 대형주 중심 투자 매력이 이어짐 |
| 2026-03 | 1 | 환헤지형 S&P500 ETF는 1개월 2.91%, 3개월 13.92%의 성과를 기록하며 미국 대형주 반등을 반영 |
| 2026-03 | 2 | NVIDIA, MICROSOFT, APPLE 등 상위 종목이 높은 비중을 유지하며 성과의 핵심 기여 요인으로 작용 |
| 2026-03 | 3 | 환헤지 시행으로 환율 변동 영향은 제한되었으나 비헤지형 대비 달러 강세 수혜는 낮게 반영 |
| 2026-03 | 4 | 507개 종목에 분산 투자하며 S&P500 Index 추종 구조와 대형주 중심 노출을 유지 |

### D2: Kodex 미국 S&P500 ETF

| monthId | bulletNo | review.items[] |
| --- | --- | --- |
| 2026-01 | 1 | 미국 대형주 실적 기대와 AI 인프라 투자 확대가 지수 성과를 견인 |
| 2026-01 | 2 | NVIDIA, MICROSOFT, APPLE 등 상위 편입 종목이 기술주 중심 상승 흐름을 주도 |
| 2026-01 | 3 | 환헤지 미시행 구조로 원달러 환율 등락이 단기 성과 변동성을 일부 확대 |
| 2026-01 | 4 | S&P500 전반의 업종 분산 효과가 개별 종목 변동성을 완화하며 1개월 수익률이 플러스 전환 |
| 2026-02 | 1 | 미국 물가와 금리 지표 확인 과정에서 성장주 변동성이 확대되었으나 대형주 중심 흐름은 유지 |
| 2026-02 | 2 | NVIDIA와 BROADCOM 등 반도체 관련 종목 비중 상승이 포트폴리오 성과를 방어 |
| 2026-02 | 3 | APPLE과 TESLA는 수요 우려로 상대적으로 부진했지만 지수 내 업종 분산이 하락 폭을 제한 |
| 2026-02 | 4 | 비헤지 구조의 환율 효과가 월중 성과 변동성을 키웠으나 누적 수익률은 견조한 수준을 유지 |
| 2026-03 | 1 | S&P500 지수가 대형 기술주와 플랫폼 기업 중심으로 반등하며 ETF의 1개월 수익률이 5.95%를 기록 |
| 2026-03 | 2 | NVIDIA, MICROSOFT, APPLE이 높은 편입 비중을 유지하며 포트폴리오 핵심 성과 요인으로 작용 |
| 2026-03 | 3 | 3개월 수익률은 11.97%로 기초지수와 유사한 흐름을 보이며 미국 대표지수 추종 특성이 확인 |
| 2026-03 | 4 | 환헤지 미시행 구조로 환율 변동 영향은 존재하나 장기 상장후 수익률은 101.13%로 높은 누적 성과를 유지 |

### D3: Kodex 미국나스닥100 ETF

| monthId | bulletNo | review.items[] |
| --- | --- | --- |
| 2026-01 | 1 | 미국 기술주 반등과 AI 인프라 투자 기대가 나스닥100 성과를 견인 |
| 2026-01 | 2 | NVIDIA, MICROSOFT, APPLE 등 상위 종목의 높은 비중이 월간 수익률 개선에 기여 |
| 2026-01 | 3 | 비헤지 구조로 환율 변동 영향이 일부 반영되며 원화 기준 성과 변동성이 확대 |
| 2026-01 | 4 | 반도체와 플랫폼 기업 중심의 성장주 노출이 S&P500 대비 높은 성과 민감도를 보임 |
| 2026-02 | 1 | 미국 금리 재평가와 기술주 차익실현으로 월중 변동성은 확대되었으나 누적 성과는 개선 |
| 2026-02 | 2 | NVIDIA와 BROADCOM 등 AI 반도체 관련 종목의 비중 상승이 성과 방어에 기여 |
| 2026-02 | 3 | APPLE과 TESLA는 수요 우려로 일부 부담을 주었으나 NETFLIX, Meta Platforms가 상대적으로 견조 |
| 2026-02 | 4 | 나스닥100 특유의 성장주 집중도가 상승 국면에서는 성과를 키우고 조정 국면에서는 변동성을 확대 |
| 2026-03 | 1 | 나스닥100 ETF는 1개월 6.45%, 3개월 16.72%를 기록하며 성장주 반등을 강하게 반영 |
| 2026-03 | 2 | NVIDIA, MICROSOFT, APPLE, Amazon.com 등 상위 기술주가 높은 비중을 유지하며 성과를 견인 |
| 2026-03 | 3 | 102개 종목으로 구성되지만 Top 10 비중이 51.27%로 높아 대형 기술주 영향력이 크게 나타남 |
| 2026-03 | 4 | NASDAQ 100 Index와 유사한 흐름을 보이며 상장후 수익률 113.70%의 높은 누적 성과를 기록 |

### D4: Kodex 코리아배당성장채권혼합 ETF

| monthId | bulletNo | review.items[] |
| --- | --- | --- |
| 2026-01 | 1 | 국고채 금리가 안정화되며 채권 비중이 월간 성과에 긍정적으로 기여 |
| 2026-01 | 2 | 현대차, 기아 등 완성차 종목과 주요 금융주의 배당 기대가 확대되며 주식 편입 종목 수익률이 개선 |
| 2026-01 | 3 | 채권 70% 수준의 방어적 배분과 배당성장주 반등이 맞물리며 1개월 수익률이 3.2% 수준으로 회복 |
| 2026-01 | 4 | 보험주와 증권주는 주주환원 기대가 이어지며 포트폴리오의 안정적인 인컴 성격을 보강 |
| 2026-02 | 1 | 국고채 금리가 재차 등락하며 채권 가격 변동성이 확대되어 월간 성과에 부담으로 작용 |
| 2026-02 | 2 | 현대차, 기아 등 완성차 종목은 통상 환경 불확실성으로 조정을 받았고, 증권주는 거래대금 둔화 우려로 수익률이 약세 |
| 2026-02 | 3 | 주식 편입 종목 조정에도 채권 중심 배분이 손실 폭을 제한하며 1개월 수익률 하락을 -1.4% 수준으로 방어 |
| 2026-02 | 4 | 보험주는 배당 안정성이 부각되며 상대적으로 견조한 흐름을 유지 |
| 2026-03 | 1 | 국고채권의 금리가 지정학적 리스크와 국제 유가 상승에 따른 인플레이션 우려로 상승 가격 하락 부정적 기여 |
| 2026-03 | 2 | 현대차, 기아 등 완성차 종목이 글로벌 통상 환경 불확실성으로 조정을 받았고, 키움증권, 삼성증권 등 금융주 또한 금리 변동성 확대와 거래대금 감소 우려에 수익률이 둔화 |
| 2026-03 | 3 | 급락세를 보인 주식 대비 70%의 채권 비중이 완충 작용을 하며 전체 손실 폭을 -4.9% 수준으로 방어 |
| 2026-03 | 4 | 보험주들이 상대적으로 견조한 배당 성향을 유지하며 하락장에서도 상대적인 주가 방어력을 시현 |

## 14. 전망 데이터


### D1: Kodex 미국 S&P500(H) ETF

| monthId | 구분 | number | text/lead | highlightText | closing |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | lead |  | 환율 변동을 줄이면서 미국 대표지수에 투자하려는 수요가 유지될 것으로 판단 |  |  |
| 2026-01 | numberedItem | ① | 미국 대형주의 실적 개선 기대가 이어지며 지수 기반 성과 회복 가능성 |  |  |
| 2026-01 | numberedItem | ② | 환헤지 전략은 원화 강세 전환 시 비헤지형 대비 상대 성과를 높일 수 있음 | 환헤지 전략 |  |
| 2026-01 | numberedItem | ③ | 금리 인하 시점에 대한 기대 변화가 단기 변동성의 핵심 변수로 작용할 전망 |  |  |
| 2026-01 | closing |  |  |  | 환율 리스크를 낮춘 미국 대형주 투자 수단으로 장기 포트폴리오 내 보완재 역할 가능 |
| 2026-02 | lead |  | 환헤지형 S&P500 익스포저는 환율 방향성보다 지수 자체 성과에 집중하는 투자자에게 유효할 것으로 판단 |  |  |
| 2026-02 | numberedItem | ① | 대형 기술주의 이익 전망이 유지될 경우 지수 상승 추세 재개 가능성 |  |  |
| 2026-02 | numberedItem | ② | 원화 강세 압력이 커지는 구간에서는 환헤지형의 상대 매력이 부각될 수 있음 | 환헤지형의 상대 매력 |  |
| 2026-02 | numberedItem | ③ | 헤지 비용과 금리 차는 비헤지형 대비 성과 차이를 만드는 주요 변수로 관리 필요 |  |  |
| 2026-02 | closing |  |  |  | 미국 대표지수 장기 투자와 환율 리스크 관리를 동시에 고려하는 포트폴리오에 적합 |
| 2026-03 | lead |  | 미국 대형주 상승 흐름과 원화 변동성 관리 수요가 맞물리며 환헤지형 상품의 활용도는 유지될 전망 |  |  |
| 2026-03 | numberedItem | ① | AI와 클라우드 투자 확대가 상위 기술주 이익 전망을 계속 지지할 가능성 |  |  |
| 2026-03 | numberedItem | ② | 원화 강세 또는 환율 안정 구간에서는 환헤지형의 성과 안정성이 부각될 수 있음 | 성과 안정성 |  |
| 2026-03 | numberedItem | ③ | 헤지 비용과 미국 금리 방향은 향후 비헤지형 대비 상대 성과의 핵심 변수 |  |  |
| 2026-03 | closing |  |  |  | 환율 방향성 부담을 낮추고 미국 대표 대형주에 접근하려는 투자자에게 적합한 선택지 |

### D2: Kodex 미국 S&P500 ETF

| monthId | 구분 | number | text/lead | highlightText | closing |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | lead |  | 미국 대형 우량주의 이익 개선 기대가 유지되며 완만한 상승 흐름을 이어갈 것으로 판단 |  |  |
| 2026-01 | numberedItem | ① | AI 투자와 클라우드 수요 확대가 대형 기술주의 이익 모멘텀을 지지할 전망 |  |  |
| 2026-01 | numberedItem | ② | 금리 인하 기대가 재부각될 경우 성장주와 경기민감주의 동반 회복 가능성 | 금리 인하 기대가 재부각 |  |
| 2026-01 | numberedItem | ③ | 환율 변동성은 남아 있으나 비헤지 구조가 달러 강세 구간에서 성과에 기여할 수 있음 |  |  |
| 2026-01 | closing |  |  |  | 미국 대표기업에 분산 투자하는 구조상 장기 핵심 자산 배분 수단으로 활용 가능 |
| 2026-02 | lead |  | 실적 시즌 이후 종목별 차별화가 커질 수 있으나 미국 대형주의 이익 체력은 유효한 것으로 판단 |  |  |
| 2026-02 | numberedItem | ① | AI 반도체와 클라우드 투자 확대가 상위 기술주 실적 추정치 상향을 이끌 가능성 |  |  |
| 2026-02 | numberedItem | ② | 금리 변동성이 완화되면 S&P500 밸류에이션 부담이 점진적으로 낮아질 전망 | 금리 변동성이 완화 |  |
| 2026-02 | numberedItem | ③ | 소비와 고용 지표 둔화 여부에 따라 경기민감 업종의 단기 등락은 확대될 수 있음 |  |  |
| 2026-02 | closing |  |  |  | 상위 대형주의 성장성과 업종 분산을 동시에 활용하는 장기 투자 포지션으로 접근 가능 |
| 2026-03 | lead |  | 미국 대표 대형주의 이익 성장과 AI 투자 사이클이 이어지며 중장기 성과 기반은 견조할 것으로 판단 |  |  |
| 2026-03 | numberedItem | ① | NVIDIA와 MICROSOFT 중심의 AI 생태계 확장이 상위 편입 종목 이익 전망을 지지 |  |  |
| 2026-03 | numberedItem | ② | S&P500 내 업종 분산 효과가 특정 테마 쏠림 리스크를 완화하는 역할 기대 | 업종 분산 효과 |  |
| 2026-03 | numberedItem | ③ | 금리와 환율 변동성은 단기 부담이나 미국 대형주의 현금흐름 안정성이 하방을 지지할 전망 |  |  |
| 2026-03 | closing |  |  |  | 핵심 미국 주식 익스포저를 확보하려는 투자자에게 장기 분산 투자 수단으로 적합한 후보 |

### D3: Kodex 미국나스닥100 ETF

| monthId | 구분 | number | text/lead | highlightText | closing |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | lead |  | AI와 클라우드 투자 사이클이 지속되며 기술주 중심의 성과 모멘텀이 이어질 것으로 판단 |  |  |
| 2026-01 | numberedItem | ① | AI 반도체 수요와 데이터센터 투자가 나스닥100 상위 종목 실적을 지지할 전망 |  |  |
| 2026-01 | numberedItem | ② | 금리 안정이 확인될 경우 성장주 밸류에이션 부담 완화 기대 | 성장주 밸류에이션 부담 완화 |  |
| 2026-01 | numberedItem | ③ | 상위 종목 집중도가 높아 개별 대형 기술주 실적 발표에 따른 변동성은 관리 필요 |  |  |
| 2026-01 | closing |  |  |  | 성장주 익스포저를 확대하려는 투자자에게 적합하나 단기 변동성은 S&P500 대비 높을 수 있음 |
| 2026-02 | lead |  | 대형 기술주의 실적 가시성이 유지되는 한 나스닥100의 상대 강세 가능성은 남아 있는 것으로 판단 |  |  |
| 2026-02 | numberedItem | ① | AI 서비스 확산과 반도체 공급망 투자가 상위 편입 종목의 이익 추정치를 지지 |  |  |
| 2026-02 | numberedItem | ② | 금리 상승 압력이 완화되면 장기 성장주에 대한 할인율 부담이 낮아질 전망 | 할인율 부담이 낮아질 전망 |  |
| 2026-02 | numberedItem | ③ | 상위 10개 종목 비중이 높아 단기적으로는 실적 발표와 규제 뉴스에 민감하게 반응 가능 |  |  |
| 2026-02 | closing |  |  |  | 기술 성장주 중심의 공격적 익스포저로 활용하되 분할 매수와 변동성 관리가 필요 |
| 2026-03 | lead |  | AI, 클라우드, 플랫폼 기업 중심의 성장 사이클이 유지되며 중장기 성과 기대는 유효한 것으로 판단 |  |  |
| 2026-03 | numberedItem | ① | NVIDIA와 BROADCOM을 중심으로 한 AI 반도체 수요가 지수 성과의 핵심 동력으로 작용할 전망 |  |  |
| 2026-03 | numberedItem | ② | 대형 플랫폼 기업의 광고, 클라우드, 구독 매출 회복이 이익 안정성을 높일 가능성 | 이익 안정성 |  |
| 2026-03 | numberedItem | ③ | 높은 성장주 집중도는 금리 상승 또는 규제 이슈 발생 시 단기 조정 폭을 키울 수 있음 |  |  |
| 2026-03 | closing |  |  |  | 공격적 성장주 노출을 원하는 투자자에게 적합하지만 S&P500 대비 변동성 관리가 중요 |

### D4: Kodex 코리아배당성장채권혼합 ETF

| monthId | 구분 | number | text/lead | highlightText | closing |
| --- | --- | --- | --- | --- | --- |
| 2026-01 | lead |  | 금리 안정과 배당성장주 강세가 이어질 경우 완만한 상승 흐름을 이어갈 것으로 판단 |  |  |
| 2026-01 | numberedItem | ① | 국고채 금리는 기준금리 인하 기대와 수급 안정으로 가격 회복세 지속 전망 |  |  |
| 2026-01 | numberedItem | ② | 자동차와 금융 업종의 주주환원 정책이 강화되며 배당성장주 저가 매수세 유입 기대 | 주주환원 정책이 강화 |  |
| 2026-01 | numberedItem | ③ | 현대차, 기아, 삼성생명 등 고배당 성향 종목의 이익 안정성이 포트폴리오 하방을 지지 |  |  |
| 2026-01 | closing |  |  |  | 글로벌 경기 둔화 우려가 남아 있으나, 채권과 배당성장주의 혼합 구조가 변동성 완화에 유효한 대안 |
| 2026-02 | lead |  | 금리 변동성이 남아 있으나 채권 비중의 방어력과 배당주의 주주환원 기대가 완만한 회복을 지지할 것으로 판단 |  |  |
| 2026-02 | numberedItem | ① | 국고채 금리는 물가와 환율 지표 확인 후 점진적으로 안정될 가능성 |  |  |
| 2026-02 | numberedItem | ② | 자동차와 금융 업종은 단기 조정 이후 배당 매력이 재부각되는 구간 진입 기대 | 배당 매력이 재부각 |  |
| 2026-02 | numberedItem | ③ | 보험 및 증권주는 주주환원 발표가 구체화될수록 포트폴리오 성과 기여도가 확대될 전망 |  |  |
| 2026-02 | closing |  |  |  | 매크로 불확실성은 이어지지만 채권 방어력과 고배당 종목의 인컴 기여를 함께 활용하는 전략이 유효 |
| 2026-03 | lead |  | 배당성장주의 가치 부각과 채권 가격 안정화가 맞물리며 완만한 회복세를 보일 것으로 판단 |  |  |
| 2026-03 | numberedItem | ① | 국고채 금리는 오버슈팅 구간을 지나 점진적으로 안정화되어 가격 반등 전망 |  |  |
| 2026-03 | numberedItem | ② | NH투자증권, 대신증권 등 주요 종목의 주주환원 정책이 구체화되는 시기로 저가 매수세 유입 기대 | 주주환원 정책이 구체화되는 시기 |  |
| 2026-03 | numberedItem | ③ | 현대차, 삼성생명 등의 자사주 소각 및 배당 확대 기조로 상방 압력은 여전히 유효 |  |  |
| 2026-03 | closing |  |  |  | 글로벌 경기 둔화 우려와 매크로 불확실성이 지속되는 구간에서 동 ETF는 변동성을 낮추며 꾸준한 인컴 수익을 추구하는 안정적인 대안 |

## 15. 검수 기준

| 검수 항목 | 기대값 |
| --- | --- |
| JSON 문법 | `python3 -m json.tool backend/data/etf_data.json` 통과 |
| datasetCount | `4` |
| datasets length | `4` |
| sourceFiles length | `4` |
| 단일 dataset schemaVersion | `poc.etfMonthlyIssueReport.dataset.v1` |
| 월별 스냅샷 | 각 ETF별 `2026-01`, `2026-02`, `2026-03` |
| Top 10 합계 | `rows[].weightPercent` 합계와 `top10TotalWeightPercent` 일치 |
| 기준/월별 데이터 분리 | 고정 정의는 `baseData`, 월별 수치/문구는 `monthlySnapshots` |

## 16. 전체 JSON path 목록

아래 목록은 현재 `etf_data.json`에서 관측된 모든 JSON path이다. 스키마 표의 누락 여부를 점검할 때 사용한다.

| JSON path |
| --- |
| $ |
| $.datasetCount |
| $.datasets |
| $.datasets[] |
| $.datasets[].baseData |
| $.datasets[].baseData.issuer |
| $.datasets[].baseData.issuer.brandName |
| $.datasets[].baseData.issuer.companyNameEn |
| $.datasets[].baseData.issuer.companyNameKo |
| $.datasets[].baseData.issuer.contactEmail |
| $.datasets[].baseData.issuer.teamName |
| $.datasets[].baseData.product |
| $.datasets[].baseData.product.benchmarkName |
| $.datasets[].baseData.product.brandPrefix |
| $.datasets[].baseData.product.fundName |
| $.datasets[].baseData.product.productName |
| $.datasets[].baseData.product.reportTitleSuffix |
| $.datasets[].baseData.salesChannel |
| $.datasets[].baseData.salesChannel.classificationLabel |
| $.datasets[].baseData.salesChannel.distributorName |
| $.datasets[].baseData.sectionDefinitions |
| $.datasets[].baseData.sectionDefinitions.footer |
| $.datasets[].baseData.sectionDefinitions.footer.note |
| $.datasets[].baseData.sectionDefinitions.outlook |
| $.datasets[].baseData.sectionDefinitions.outlook.numberLabels |
| $.datasets[].baseData.sectionDefinitions.outlook.numberLabels[] |
| $.datasets[].baseData.sectionDefinitions.outlook.renderType |
| $.datasets[].baseData.sectionDefinitions.outlook.title |
| $.datasets[].baseData.sectionDefinitions.performanceTrend |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.chartCategories |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.chartCategories[] |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.chartLegend |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.chartLegend[] |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.noteTemplates |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.noteTemplates[] |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.summaryColumns |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.summaryColumns[] |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.title |
| $.datasets[].baseData.sectionDefinitions.performanceTrend.unit |
| $.datasets[].baseData.sectionDefinitions.review |
| $.datasets[].baseData.sectionDefinitions.review.renderType |
| $.datasets[].baseData.sectionDefinitions.review.title |
| $.datasets[].baseData.sectionDefinitions.topHoldings |
| $.datasets[].baseData.sectionDefinitions.topHoldings.captionTemplates |
| $.datasets[].baseData.sectionDefinitions.topHoldings.captionTemplates[] |
| $.datasets[].baseData.sectionDefinitions.topHoldings.columns |
| $.datasets[].baseData.sectionDefinitions.topHoldings.columns[] |
| $.datasets[].baseData.sectionDefinitions.topHoldings.title |
| $.datasets[].baseData.sectionDefinitions.topHoldings.totalLabel |
| $.datasets[].monthlySnapshots |
| $.datasets[].monthlySnapshots[] |
| $.datasets[].monthlySnapshots[].asOf |
| $.datasets[].monthlySnapshots[].asOfKo |
| $.datasets[].monthlySnapshots[].monthId |
| $.datasets[].monthlySnapshots[].outlook |
| $.datasets[].monthlySnapshots[].outlook.closing |
| $.datasets[].monthlySnapshots[].outlook.lead |
| $.datasets[].monthlySnapshots[].outlook.numberedItems |
| $.datasets[].monthlySnapshots[].outlook.numberedItems[] |
| $.datasets[].monthlySnapshots[].outlook.numberedItems[].highlightText |
| $.datasets[].monthlySnapshots[].outlook.numberedItems[].number |
| $.datasets[].monthlySnapshots[].outlook.numberedItems[].text |
| $.datasets[].monthlySnapshots[].performanceTrend |
| $.datasets[].monthlySnapshots[].performanceTrend.chartSeries |
| $.datasets[].monthlySnapshots[].performanceTrend.chartSeries[] |
| $.datasets[].monthlySnapshots[].performanceTrend.chartSeries[].name |
| $.datasets[].monthlySnapshots[].performanceTrend.chartSeries[].values |
| $.datasets[].monthlySnapshots[].performanceTrend.chartSeries[].values[] |
| $.datasets[].monthlySnapshots[].performanceTrend.summaryValues |
| $.datasets[].monthlySnapshots[].performanceTrend.summaryValues[] |
| $.datasets[].monthlySnapshots[].periodLabel |
| $.datasets[].monthlySnapshots[].review |
| $.datasets[].monthlySnapshots[].review.items |
| $.datasets[].monthlySnapshots[].review.items[] |
| $.datasets[].monthlySnapshots[].sampleDataType |
| $.datasets[].monthlySnapshots[].topHoldings |
| $.datasets[].monthlySnapshots[].topHoldings.rows |
| $.datasets[].monthlySnapshots[].topHoldings.rows[] |
| $.datasets[].monthlySnapshots[].topHoldings.rows[].name |
| $.datasets[].monthlySnapshots[].topHoldings.rows[].rank |
| $.datasets[].monthlySnapshots[].topHoldings.rows[].weightPercent |
| $.datasets[].monthlySnapshots[].topHoldings.top10TotalWeightPercent |
| $.datasets[].monthlySnapshots[].topHoldings.totalHoldingCount |
| $.datasets[].datasetId |
| $.datasets[].schemaVersion |
| $.datasets[].styleCandidates |
| $.datasets[].styleCandidates.layout |
| $.datasets[].styleCandidates.layout.columns |
| $.datasets[].styleCandidates.layout.mainSections |
| $.datasets[].styleCandidates.layout.mainSections[] |
| $.datasets[].styleCandidates.layout.pageSize |
| $.datasets[].styleCandidates.theme |
| $.datasets[].styleCandidates.theme.benchmarkGray |
| $.datasets[].styleCandidates.theme.chartBlue |
| $.datasets[].styleCandidates.theme.paper |
| $.datasets[].styleCandidates.theme.primary |
| $.datasets[].styleCandidates.theme.ruleGray |
| $.datasets[].styleCandidates.theme.tableHeaderBlue |
| $.schemaVersion |
| $.sourceFiles |
| $.sourceFiles[] |
| $.sourceSchemaVersion |

## 17. Stage 2 파생 데이터 개요

`etf_data.json`은 Stage 2의 입력 데이터 소스 bundle이고, 아래 2개 파일은 Stage 2 컴포넌트 계약을 명시적으로 만족시키기 위해 생성한 파생 데이터이다.

| 파일 | schemaVersion | count | source | 역할 |
| --- | --- | ---: | --- | --- |
| `backend/data/etf_stage2_component_sources.json` | `poc.etfReport.stage2ComponentSources.v1` | 60 | `backend/data/etf_data.json` | LLM Stage 2 호출에 넘길 섹션 단위 입력 catalog |
| `backend/data/etf_stage2_components.sample.json` | `poc.etfReport.stage2Components.v1` | 60 | `backend/data/etf_stage2_component_sources.json` | Stage 2 출력 계약을 만족하는 무스타일 HTML 컴포넌트 sample |

| 산식 | 값 |
| --- | --- |
| ETF 수 | 4 |
| 월별 스냅샷 수 | 3 |
| componentKey 수 | 5 |
| 총 componentSources | 4 × 3 × 5 = 60 |
| 총 stage2Components | 4 × 3 × 5 = 60 |

## 18. Stage 2 componentKey 매핑

| componentKey | sectionKey | sourcePath | renderType | payload 핵심 필드 | component 수 |
| --- | --- | --- | --- | --- | ---: |
| `performance_chart` | `performanceTrend` | `monthlySnapshots[].performanceTrend.chartSeries` | `chart` | `unit`, `labels`, `series`, `noteTemplates` | 12 |
| `performance_summary` | `performanceTrend` | `monthlySnapshots[].performanceTrend.summaryValues` | `table` | `unit`, `columns`, `values`, `noteTemplates` | 12 |
| `top_holdings` | `topHoldings` | `monthlySnapshots[].topHoldings` | `table` | `columns`, `rows`, `totalLabel`, `top10TotalWeightPercent`, `totalHoldingCount`, `captionTemplates` | 12 |
| `review` | `review` | `monthlySnapshots[].review.items` | `list` | `items` | 12 |
| `outlook` | `outlook` | `monthlySnapshots[].outlook` | `article` | `lead`, `numberedItems`, `closing`, `numberLabels` | 12 |

## 19. componentSources 스키마 사전

| JSON path | type | 필수 여부 | 설명 |
| --- | --- | --- | --- |
| `$` | object | required | Stage 2 component source bundle 최상위 객체 |
| `$.schemaVersion` | string | required | 현재 `poc.etfReport.stage2ComponentSources.v1` |
| `$.sourceBundle` | string | required | 원천 bundle 파일. 현재 `backend/data/etf_data.json` |
| `$.sourceSchemaVersion` | string | required | 원천 bundle 스키마. 현재 `poc.etfMonthlyIssueReport.bundle.v1` |
| `$.datasetSchemaVersion` | string | required | 단일 ETF dataset 스키마. 현재 `poc.etfMonthlyIssueReport.dataset.v1` |
| `$.componentSourceCount` | number | required | componentSources 총 개수. 현재 60 |
| `$.componentKeys` | string[] | required | 생성 대상 componentKey 목록 |
| `$.componentKeys[]` | string | required | 단일 componentKey |
| `$.componentSources` | ComponentSource[] | required | Stage 2 LLM 호출 입력 단위 배열 |
| `$.componentSources[]` | object | required | 단일 Stage 2 입력 데이터 소스 |
| `$.componentSources[].dataSourceId` | string | required | `ds_{datasetId}_{monthId}_{componentKey}` 규칙의 안정 식별자 |
| `$.componentSources[].datasetRef` | object | required | ETF dataset 참조 정보 |
| `$.componentSources[].datasetRef.datasetId` | string | required | 원천 dataset의 `datasetId` |
| `$.componentSources[].datasetRef.productName` | string | required | ETF 상품명 |
| `$.componentSources[].datasetRef.distributorName` | string | required | 판매사명 |
| `$.componentSources[].snapshotRef` | object | required | 월별 snapshot 참조 정보 |
| `$.componentSources[].snapshotRef.monthId` | string | required | 월 식별자 |
| `$.componentSources[].snapshotRef.asOf` | string | required | 기준일 |
| `$.componentSources[].snapshotRef.sampleDataType` | string | required | 원천/샘플 데이터 성격 |
| `$.componentSources[].componentKey` | string | required | 생성할 컴포넌트 종류 |
| `$.componentSources[].sectionKey` | string | required | 원천 dataset의 섹션 키 |
| `$.componentSources[].sourcePath` | string | required | 원천 dataset에서 payload를 가져온 경로 |
| `$.componentSources[].renderType` | string | required | Stage 2 허용 렌더 타입. `chart`, `table`, `list`, `article` 중 하나 |
| `$.componentSources[].title` | string | required | 컴포넌트 제목 |
| `$.componentSources[].payload` | object | required | componentKey별 입력 데이터 본문 |
| `$.componentSources[].payload.unit` | string | conditional | 성과 차트/성과 요약 단위 |
| `$.componentSources[].payload.labels` | string[] | conditional | `performance_chart` 차트 라벨 |
| `$.componentSources[].payload.labels[]` | string | conditional | 차트 라벨 단일 항목 |
| `$.componentSources[].payload.series` | object[] | conditional | `performance_chart` 차트 series |
| `$.componentSources[].payload.series[]` | object | conditional | 단일 chart series |
| `$.componentSources[].payload.series[].name` | string | conditional | chart series 이름 |
| `$.componentSources[].payload.series[].values` | number[] | conditional | chart series 값 배열 |
| `$.componentSources[].payload.series[].values[]` | number | conditional | chart series 단일 값 |
| `$.componentSources[].payload.noteTemplates` | string[] | conditional | 성과 섹션 주석 템플릿 |
| `$.componentSources[].payload.noteTemplates[]` | string | conditional | 성과 섹션 주석 템플릿 단일 항목 |
| `$.componentSources[].payload.columns` | string[] | conditional | table 컬럼 |
| `$.componentSources[].payload.columns[]` | string | conditional | table 컬럼 단일 항목 |
| `$.componentSources[].payload.values` | number[] | conditional | `performance_summary` 성과표 값 |
| `$.componentSources[].payload.values[]` | number | conditional | 성과표 단일 값 |
| `$.componentSources[].payload.rows` | object[] | conditional | `top_holdings` Top 10 행 배열 |
| `$.componentSources[].payload.rows[]` | object | conditional | 단일 보유종목 행 |
| `$.componentSources[].payload.rows[].rank` | number | conditional | 보유종목 순위 |
| `$.componentSources[].payload.rows[].name` | string | conditional | 보유종목명 |
| `$.componentSources[].payload.rows[].weightPercent` | number | conditional | 보유비중 |
| `$.componentSources[].payload.totalLabel` | string | conditional | Top 10 합계 라벨 |
| `$.componentSources[].payload.top10TotalWeightPercent` | number | conditional | Top 10 보유비중 합계 |
| `$.componentSources[].payload.totalHoldingCount` | number | conditional | 총 보유종목 수 |
| `$.componentSources[].payload.captionTemplates` | string[] | conditional | Top 10 caption 템플릿 |
| `$.componentSources[].payload.captionTemplates[]` | string | conditional | Top 10 caption 템플릿 단일 항목 |
| `$.componentSources[].payload.items` | string[] | conditional | `review` bullet 문구 |
| `$.componentSources[].payload.items[]` | string | conditional | `review` bullet 단일 문구 |
| `$.componentSources[].payload.lead` | string | conditional | `outlook` 도입 문구 |
| `$.componentSources[].payload.numberedItems` | object[] | conditional | `outlook` numbered item 배열 |
| `$.componentSources[].payload.numberedItems[]` | object | conditional | 단일 numbered item |
| `$.componentSources[].payload.numberedItems[].number` | string | conditional | numbered item 번호 |
| `$.componentSources[].payload.numberedItems[].text` | string | conditional | numbered item 본문 |
| `$.componentSources[].payload.numberedItems[].highlightText` | string | optional | numbered item 강조 문자열 |
| `$.componentSources[].payload.closing` | string | conditional | `outlook` 마무리 문구 |
| `$.componentSources[].payload.numberLabels` | string[] | conditional | `outlook` 번호 라벨 목록 |
| `$.componentSources[].payload.numberLabels[]` | string | conditional | `outlook` 번호 라벨 단일 항목 |

## 20. stage2Components 스키마 사전

| JSON path | type | 필수 여부 | 설명 |
| --- | --- | --- | --- |
| `$` | object | required | Stage 2 output sample bundle 최상위 객체 |
| `$.schemaVersion` | string | required | 현재 `poc.etfReport.stage2Components.v1` |
| `$.sourceBundle` | string | required | 원천 bundle 파일. 현재 `backend/data/etf_data.json` |
| `$.sourceComponentSources` | string | required | Stage 2 입력 catalog 파일. 현재 `backend/data/etf_stage2_component_sources.json` |
| `$.componentCount` | number | required | stage2Components 총 개수. 현재 60 |
| `$.stage2Components` | Stage2Component[] | required | Stage 2 출력 컴포넌트 배열 |
| `$.stage2Components[]` | object | required | 단일 Stage 2 출력 컴포넌트 |
| `$.stage2Components[].componentId` | string | required | `comp_{datasetId}_{monthId}_{componentKey}` 규칙의 안정 식별자 |
| `$.stage2Components[].componentKey` | string | required | 생성된 컴포넌트 종류 |
| `$.stage2Components[].datasetId` | string | required | 원천 ETF dataset 식별자 |
| `$.stage2Components[].monthId` | string | required | 월 식별자 |
| `$.stage2Components[].dataSourceId` | string | required | 원천 componentSource의 `dataSourceId` |
| `$.stage2Components[].renderType` | string | required | `chart`, `table`, `list`, `article` 중 하나 |
| `$.stage2Components[].html` | string | required | CSS/inline style 없는 무스타일 HTML fragment |
| `$.stage2Components[].chartSpec` | object/null | required | chart 컴포넌트만 object, 나머지는 `null` |
| `$.stage2Components[].chartSpec.library` | string | conditional | chart library. 현재 `chartjs` |
| `$.stage2Components[].chartSpec.type` | string | conditional | chart type. 현재 `bar` |
| `$.stage2Components[].chartSpec.unit` | string | conditional | chart 단위 |
| `$.stage2Components[].chartSpec.labels` | string[] | conditional | chart x축 라벨 |
| `$.stage2Components[].chartSpec.labels[]` | string | conditional | chart x축 라벨 단일 항목 |
| `$.stage2Components[].chartSpec.series` | object[] | conditional | chart series 배열 |
| `$.stage2Components[].chartSpec.series[]` | object | conditional | 단일 chart series |
| `$.stage2Components[].chartSpec.series[].name` | string | conditional | chart series 이름 |
| `$.stage2Components[].chartSpec.series[].values` | number[] | conditional | chart series 값 배열 |
| `$.stage2Components[].chartSpec.series[].values[]` | number | conditional | chart series 단일 값 |
| `$.stage2Components[].styled` | boolean | required | Stage 2에서는 항상 `false` |

## 21. Stage 2 출력 규칙

| 규칙 | 내용 |
| --- | --- |
| `componentId` 생성 | `dataSourceId`의 `ds_` prefix를 `comp_`로 바꾼다. |
| `dataSourceId` 생성 | `ds_{datasetId}_{monthId}_{componentKey}` 형식이다. `monthId`의 하이픈은 `_`로 치환한다. |
| HTML 스타일 | Stage 2 HTML에는 `<style`, `style=`, `class=`를 넣지 않는다. |
| `styled` | 모든 `stage2Components[].styled`는 `false`이다. |
| `chartSpec` | `renderType=chart`인 `performance_chart`만 object이고, 나머지는 `null`이다. |
| footer note | componentSource로 분리하지 않고 템플릿 고정 문구로 유지한다. |

| renderType | componentKey | HTML 구조 | chartSpec |
| --- | --- | --- | --- |
| `chart` | `performance_chart` | `<section><h2>...<canvas ...></canvas></section>` | object |
| `table` | `performance_summary` | `<section><h2>...<table>...</table></section>` | `null` |
| `table` | `top_holdings` | `<section><h2>...<table>...</table></section>` | `null` |
| `list` | `review` | `<section><h2>...<ul><li>...</li></ul></section>` | `null` |
| `article` | `outlook` | `<article><h2>...<p>...<ol><li>...</li></ol><p>...</p></article>` | `null` |

## 22. Stage 3 입력 구성 방식

Stage 3는 선택된 ETF/month 조합의 Stage 2 컴포넌트 5개와 템플릿 preview image를 함께 입력으로 받는다.

| 입력 | 데이터 위치 |
| --- | --- |
| 템플릿 이미지 | `report_templates.json`의 선택된 `templateId` 항목의 `previewImage` |
| 성과 차트 컴포넌트 | `stage2Components[]` 중 `componentKey=performance_chart`에 대응하는 component |
| 성과 요약표 컴포넌트 | `stage2Components[]` 중 `componentKey=performance_summary`에 대응하는 component |
| Top 10 보유내역 컴포넌트 | `stage2Components[]` 중 `componentKey=top_holdings`에 대응하는 component |
| 리뷰 컴포넌트 | `stage2Components[]` 중 `componentKey=review`에 대응하는 component |
| 전망 컴포넌트 | `stage2Components[]` 중 `componentKey=outlook`에 대응하는 component |

## 23. Stage 2 검수 기준

| 검수 항목 | 기대값 |
| --- | --- |
| `componentSourceCount` | 60 |
| `componentCount` | 60 |
| ETF/month 조합 | 12 |
| 각 ETF/month의 componentKey | `performance_chart`, `performance_summary`, `top_holdings`, `review`, `outlook` |
| componentKey별 건수 | 각 12 |
| renderType 분포 | `chart` 12, `table` 24, `list` 12, `article` 12 |
| `dataSourceId` | 중복 없음 |
| `componentId` | 중복 없음 |
| `styled` | 모두 `false` |
| HTML 금지 항목 | `<style`, `style=`, `class=` 없음 |
| chart `chartSpec` | `performance_chart` 12건만 object |
| non-chart `chartSpec` | 48건 모두 `null` |
| 원본 bundle 오염 여부 | `etf_data.json`에는 `componentSources`, `stage2Components`, `componentId`, `dataSourceId`, `chartSpec` 없음 |

## 24. Stage 2 JSON path 목록

### etf_stage2_component_sources.json

| JSON path |
| --- |
| $ |
| $.componentKeys |
| $.componentKeys[] |
| $.componentSourceCount |
| $.componentSources |
| $.componentSources[] |
| $.componentSources[].componentKey |
| $.componentSources[].dataSourceId |
| $.componentSources[].datasetRef |
| $.componentSources[].datasetRef.distributorName |
| $.componentSources[].datasetRef.datasetId |
| $.componentSources[].datasetRef.productName |
| $.componentSources[].payload |
| $.componentSources[].payload.captionTemplates |
| $.componentSources[].payload.captionTemplates[] |
| $.componentSources[].payload.closing |
| $.componentSources[].payload.columns |
| $.componentSources[].payload.columns[] |
| $.componentSources[].payload.items |
| $.componentSources[].payload.items[] |
| $.componentSources[].payload.labels |
| $.componentSources[].payload.labels[] |
| $.componentSources[].payload.lead |
| $.componentSources[].payload.noteTemplates |
| $.componentSources[].payload.noteTemplates[] |
| $.componentSources[].payload.numberLabels |
| $.componentSources[].payload.numberLabels[] |
| $.componentSources[].payload.numberedItems |
| $.componentSources[].payload.numberedItems[] |
| $.componentSources[].payload.numberedItems[].highlightText |
| $.componentSources[].payload.numberedItems[].number |
| $.componentSources[].payload.numberedItems[].text |
| $.componentSources[].payload.rows |
| $.componentSources[].payload.rows[] |
| $.componentSources[].payload.rows[].name |
| $.componentSources[].payload.rows[].rank |
| $.componentSources[].payload.rows[].weightPercent |
| $.componentSources[].payload.series |
| $.componentSources[].payload.series[] |
| $.componentSources[].payload.series[].name |
| $.componentSources[].payload.series[].values |
| $.componentSources[].payload.series[].values[] |
| $.componentSources[].payload.top10TotalWeightPercent |
| $.componentSources[].payload.totalHoldingCount |
| $.componentSources[].payload.totalLabel |
| $.componentSources[].payload.unit |
| $.componentSources[].payload.values |
| $.componentSources[].payload.values[] |
| $.componentSources[].renderType |
| $.componentSources[].sectionKey |
| $.componentSources[].snapshotRef |
| $.componentSources[].snapshotRef.asOf |
| $.componentSources[].snapshotRef.monthId |
| $.componentSources[].snapshotRef.sampleDataType |
| $.componentSources[].sourcePath |
| $.componentSources[].title |
| $.datasetSchemaVersion |
| $.schemaVersion |
| $.sourceBundle |
| $.sourceSchemaVersion |

### etf_stage2_components.sample.json

| JSON path |
| --- |
| $ |
| $.componentCount |
| $.schemaVersion |
| $.sourceBundle |
| $.sourceComponentSources |
| $.stage2Components |
| $.stage2Components[] |
| $.stage2Components[].chartSpec |
| $.stage2Components[].chartSpec.labels |
| $.stage2Components[].chartSpec.labels[] |
| $.stage2Components[].chartSpec.library |
| $.stage2Components[].chartSpec.series |
| $.stage2Components[].chartSpec.series[] |
| $.stage2Components[].chartSpec.series[].name |
| $.stage2Components[].chartSpec.series[].values |
| $.stage2Components[].chartSpec.series[].values[] |
| $.stage2Components[].chartSpec.type |
| $.stage2Components[].chartSpec.unit |
| $.stage2Components[].componentKey |
| $.stage2Components[].componentId |
| $.stage2Components[].dataSourceId |
| $.stage2Components[].datasetId |
| $.stage2Components[].html |
| $.stage2Components[].monthId |
| $.stage2Components[].renderType |
| $.stage2Components[].styled |
