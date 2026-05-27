# 국민은행 월간 가이드북 3건 ETF 데이터셋 분석

> source guidebook: `document/ETF Reporting system 데이터/국민은행 월간 가이드북.pptx`  
> binding template: `document/report/우리은행_월간_리포트.html`  
> preview image: `document/report/국민은행_월간_리포트.png`  
> dataset schema: `poc.etfMonthlyIssueReport.dataset.v1`

## 1. 선별 기준

- PPTX 첫 슬라이드의 `TIGER 화장품`은 작성 예시로 판단하여 제외했다.
- 실제 데이터셋 대상은 가이드북 슬라이드 순서상 첫 3개 KODEX ETF로 선정했다.
- 기존 1건 데이터셋과 동일하게 ETF 1건당 JSON 1개 구조를 유지했다.
- 개별 데이터셋 내부의 월 선택 단위는 `monthId`이며, CLI 전체 실행에서는 `datasetId`, `templateId`, `monthId`를 독립 입력으로 받는다. 각 ETF는 `2026-01`, `2026-02`, `2026-03` 3개월 스냅샷을 가진다.
- PPTX에는 단일 기준월 스냅샷만 있으므로 `2026-03`의 성과와 Top 10은 source 값, `2026-01`과 `2026-02`는 synthetic sample이다.
- PPTX에 `ETF 리뷰`, `ETF 향후 전망` 원문은 없으므로 해당 문구는 월별 synthetic commentary로 작성했다.

## 2. 생성 파일

- `backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500.dataset.sample.json`
- `backend/data/국민은행_월간_가이드북_KODEX_미국_S&P500_H.dataset.sample.json`
- `backend/data/국민은행_월간_가이드북_KODEX_미국나스닥100.dataset.sample.json`

## 3. 데이터 구조 유지 기준

| 구분 | 저장 위치 | 포함 항목 | 비고 |
| --- | --- | --- | --- |
| 템플릿 메타 | `template` | 바인딩 대상 HTML, preview image, A4 Portrait 설정 | HTML은 기존 월간 리포트 바인딩 템플릿을 유지하고 preview image는 국민은행 월간 리포트 이미지를 사용 |
| 기준 데이터 | `baseData.issuer` | Kodex, 삼성자산운용, 팀명, 연락처 | ETF별 공통 발행사 정보 |
| 기준 데이터 | `baseData.salesChannel` | 국민은행, 월간 가이드북 | 판매사/문서 성격 |
| 기준 데이터 | `baseData.product` | 상품명, 리포트 제목 suffix, BM 명칭 | 월별 수치와 분리 |
| 기준 데이터 | `baseData.sectionDefinitions` | 섹션 제목, 컬럼명, 단위, 범례, 주석 템플릿 | 실제 값은 월별 데이터 |
| 월별 데이터 | `monthlySnapshots[].performanceTrend` | ETF/BM 차트 값, ETF 성과표 값 | `2026-03` 성과는 PPTX source |
| 월별 데이터 | `monthlySnapshots[].topHoldings` | Top 10 종목, 비중, 합계, 총 보유종목 수 | `2026-03` 보유내역은 PPTX source |
| 월별 데이터 | `monthlySnapshots[].review` | 월별 리뷰 bullet | PPTX 미제공으로 synthetic |
| 월별 데이터 | `monthlySnapshots[].outlook` | lead, numbered items, closing | PPTX 미제공으로 synthetic |

## 4. PPTX 성과 컬럼 매핑

| PPTX 컬럼 | JSON/템플릿 컬럼 | 처리 |
| --- | --- | --- |
| `1M` | `1개월` | source 값 사용 |
| `3M` | `3개월` | source 값 사용 |
| `6M` | `6개월` | source 값 사용 |
| `1Y` | `1년` | source 값 사용 |
| `설정이후` | `상장후`, `상장이후` | source 값 사용 |
| 없음 | `연초후` | `2026-03`은 `3개월` 값을 POC 파생값으로 사용 |
| `3Y` | 보류 | 현재 월간 리포트 템플릿 바인딩 대상이 아니므로 JSON 본문 제외 |
| `변동성` | 보류 | 현재 월간 리포트 템플릿 바인딩 대상이 아니므로 JSON 본문 제외 |

## 5. 대상 ETF 기준 정보

| ETF | 코드 | 슬라이드 | 기초지수 | 투자종목수 | 순자산총액 | 상장일 | 총보수 | 환헤지 |
| --- | --- | ---: | --- | ---: | --- | --- | --- | --- |
| KODEX 미국 S&P500 | 379800 | 2 | S&P500 Index | 505 | 48,436억원 | 2021년 4월 9일 | 연 0.0062% | 미시행 |
| KODEX 미국 S&P500(H) | 449180 | 2 | S&P500 Index | 507 | 7,689억원 | 2022년 12월 2일 | 연 0.0099% | 시행 |
| KODEX 미국나스닥100 | 379810 | 3 | NASDAQ 100 Index | 102 | 28,851억원 | 2021년 4월 9일 | 연 0.0062% | 미시행 |

## 6. 2026년 3월 PPTX source 성과값

| ETF | 구분 | 1개월 | 3개월 | 6개월 | 1년 | 연초후 | 상장후 | 비고 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| KODEX 미국 S&P500 | ETF 성과표 | 5.95 | 11.97 | 0.56 | 19.09 | 11.97 | 101.13 | `연초후`는 PPTX 미제공으로 `3개월` 값 사용 |
| KODEX 미국 S&P500(H) | ETF 성과표 | 2.91 | 13.92 | 3.94 | 15.37 | 13.92 | 50.20 | `연초후`는 PPTX 미제공으로 `3개월` 값 사용 |
| KODEX 미국나스닥100 | ETF 성과표 | 6.45 | 16.72 | 3.86 | 25.70 | 16.72 | 113.70 | `연초후`는 PPTX 미제공으로 `3개월` 값 사용 |

| ETF | 차트 구분 | 1개월 | 3개월 | 6개월 | 1년 | 상장이후 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| KODEX 미국 S&P500 | Kodex 미국 S&P500 | 6.0 | 12.0 | 0.6 | 19.1 | 101.1 |
| KODEX 미국 S&P500 | BM | 5.7 | 11.7 | 0.4 | 19.2 | 104.2 |
| KODEX 미국 S&P500(H) | Kodex 미국 S&P500(H) | 2.9 | 13.9 | 3.9 | 15.4 | 50.2 |
| KODEX 미국 S&P500(H) | BM | 3.1 | 14.4 | 4.8 | 17.0 | 56.1 |
| KODEX 미국나스닥100 | Kodex 미국나스닥100 | 6.5 | 16.7 | 3.9 | 25.7 | 113.7 |
| KODEX 미국나스닥100 | BM | 6.2 | 16.5 | 3.7 | 25.8 | 116.6 |

## 7. 2026년 3월 PPTX source Top 10

### KODEX 미국 S&P500

| No. | 종목명 | 보유비중(%) |
| ---: | --- | ---: |
| 1 | NVIDIA Corp | 7.93 |
| 2 | MICROSOFT | 7.05 |
| 3 | APPLE Inc | 5.84 |
| 4 | Amazon.com Inc | 4.04 |
| 5 | Meta Platforms | 2.81 |
| 6 | BROADCOM LTD | 2.59 |
| 7 | ALPHABET INC-CL A | 2.11 |
| 8 | ALPHABET INC-CL C | 1.71 |
| 9 | TESLA MOTORS | 1.67 |
| 10 | BERKSHIRE HATHAWAY | 1.62 |
| 합계 |  | 37.37 |

### KODEX 미국 S&P500(H)

| No. | 종목명 | 보유비중(%) |
| ---: | --- | ---: |
| 1 | NVIDIA Corp | 7.71 |
| 2 | MICROSOFT | 6.87 |
| 3 | APPLE Inc | 5.69 |
| 4 | Amazon.com Inc | 3.93 |
| 5 | Meta Platforms | 2.74 |
| 6 | iShares S&P500 Index Fund | 2.67 |
| 7 | BROADCOM LTD | 2.52 |
| 8 | ALPHABET INC-CL A | 2.05 |
| 9 | ALPHABET INC-CL C | 1.66 |
| 10 | TESLA MOTORS | 1.62 |
| 합계 |  | 37.46 |

### KODEX 미국나스닥100

| No. | 종목명 | 보유비중(%) |
| ---: | --- | ---: |
| 1 | NVIDIA Corp | 9.92 |
| 2 | MICROSOFT | 8.82 |
| 3 | APPLE Inc | 7.31 |
| 4 | Amazon.com Inc | 5.68 |
| 5 | BROADCOM LTD | 5.36 |
| 6 | Meta Platforms | 3.52 |
| 7 | NETFLIX | 2.83 |
| 8 | TESLA MOTORS | 2.71 |
| 9 | ALPHABET INC-CL A | 2.64 |
| 10 | ALPHABET INC-CL C | 2.48 |
| 합계 |  | 51.27 |

## 8. 월별 샘플 구성

| ETF | monthId | asOf | 데이터 성격 | Top 10 합계 | 총 보유종목 수 |
| --- | --- | --- | --- | ---: | ---: |
| KODEX 미국 S&P500 | `2026-01` | `2026.01.31` | `synthetic` | 37.11 | 505 |
| KODEX 미국 S&P500 | `2026-02` | `2026.02.28` | `synthetic` | 37.27 | 505 |
| KODEX 미국 S&P500 | `2026-03` | `2026.03.31` | `source_numeric_with_synthetic_commentary` | 37.37 | 505 |
| KODEX 미국 S&P500(H) | `2026-01` | `2026.01.31` | `synthetic` | 37.12 | 507 |
| KODEX 미국 S&P500(H) | `2026-02` | `2026.02.28` | `synthetic` | 37.29 | 507 |
| KODEX 미국 S&P500(H) | `2026-03` | `2026.03.31` | `source_numeric_with_synthetic_commentary` | 37.46 | 507 |
| KODEX 미국나스닥100 | `2026-01` | `2026.01.31` | `synthetic` | 50.60 | 102 |
| KODEX 미국나스닥100 | `2026-02` | `2026.02.28` | `synthetic` | 50.91 | 102 |
| KODEX 미국나스닥100 | `2026-03` | `2026.03.31` | `source_numeric_with_synthetic_commentary` | 51.27 | 102 |

## 9. 후속 DB 매핑 시 확인할 항목

- 실제 DB에서 국민은행 가이드북 기준일과 월별 스냅샷을 조회하는 키를 확인해야 한다.
- PPTX 원본은 `3Y`, `변동성`, 분배금 지급 현황을 제공하지만 현재 월간 이슈 리포트 템플릿에는 직접 바인딩 영역이 없다.
- `연초후` 값은 PPTX에 없으므로 실제 DB 적용 시 별도 YTD 필드가 있는지 확인해야 한다.
- 리뷰/전망 문구는 PPTX source가 아니라 POC synthetic이므로 실제 운영에서는 애널리스트 코멘트 DB 또는 생성형 LLM 출력 필드와 연결해야 한다.
- Top 10 표는 PPTX의 2단 표를 보유비중 순위 기준 단일 리스트로 정규화했다.

## 10. 검수 결과

- JSON 문법 검수: 통과
- 기존 데이터셋 대비 최상위 키 구조: `schemaVersion`, `template`, `baseData`, `monthlySnapshots`, `styleCandidates` 일치
- 월별 스냅샷 구성: 각 JSON에 `2026-01`, `2026-02`, `2026-03` 3개 확인
- `2026-03` PPTX source 대조: 상품명, 상품코드, 성과값, Top 10 종목명/비중 일치
- Top 10 합계 검수: 각 월의 rows 합계와 `top10TotalWeightPercent` 일치
- 기준 데이터와 월별 데이터 분리: 섹션 제목/컬럼/범례는 `baseData`, 월별 숫자/문구는 `monthlySnapshots`에 분리
