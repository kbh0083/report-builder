# Handoff Map

> 목적: `document/handoff` 폴더에 누적되는 handoff 문서의 위치와 요약을 관리한다.
> 운영 방식: 새 handoff 문서를 만들 때 기존 문서는 보존하고, 이 문서의 최신 handoff와 목록 테이블에 새 항목을 추가한다.

## 최신 Handoff

- [handoff_20260528_report_engine_stage4_prompt_template_ready.md](handoff_20260528_report_engine_stage4_prompt_template_ready.md)

## Handoff 목록

| 작성일 | 문서 | 주제 | 상태 | 다음 세션 시작 포인트 |
|---|---|---|---|---|
| 2026-05-28 | [handoff_20260528_report_engine_stage4_prompt_template_ready.md](handoff_20260528_report_engine_stage4_prompt_template_ready.md) | Stage 4 chart/render/version store, LLM 감사 로그, prompt 파일화, report_template 경로 전환 상태 정리 | 진행 중 | Git 상태 확인 후 신규 파일 포함 범위를 검토하고 전체 테스트, live Novita Stage 4 CLI 검증, Stage 5 visual verification 구현을 이어간다 |
| 2026-05-27 | [handoff_20260527_report_engine_stage3_validator_stage4_ready.md](handoff_20260527_report_engine_stage3_validator_stage4_ready.md) | Stage 3 CSS 생성, correction retry, source preservation validator 보정, Stage 4 renderer/version store 후보 상태 정리 | 대체됨 | 현재 작업은 `handoff_20260528_report_engine_stage4_prompt_template_ready.md`에서 이어간다 |
| 2026-05-27 | [handoff_20260527_report_engine_task6_stage3_boundary_ready.md](handoff_20260527_report_engine_task6_stage3_boundary_ready.md) | Task 6 Novita adapter, Stage 2 병렬 component 생성, Stage 3 layout/chart 경계, footer overlap 방어 구현 | 대체됨 | 현재 작업은 `handoff_20260528_report_engine_stage4_prompt_template_ready.md`에서 이어간다 |
| 2026-05-27 | [handoff_20260527_report_engine_cli_task6_ready.md](handoff_20260527_report_engine_cli_task6_ready.md) | 리포트 엔진 CLI Task 1~5 구현, 로그 산출물, 입력 문서 정합화, Task 6 Novita 선행 계획 반영 | 대체됨 | 현재 작업은 `handoff_20260528_report_engine_stage4_prompt_template_ready.md`에서 이어간다 |
| 2026-05-27 | [handoff_20260527_report_engine_design.md](handoff_20260527_report_engine_design.md) | 리포트 엔진 설계 문서화, 국민은행 preview image 반영, 검수 결과 정리 | 완료 | 설계서/아키텍처 문서를 읽고 backend Stage 1~6 구현 계획부터 착수 |

## 관리 규칙

- 최신 handoff는 이 문서의 `최신 Handoff` 섹션에 명시한다.
- 새 handoff가 생기면 `Handoff 목록`에 한 줄을 추가한다.
- 이전 handoff 문서는 삭제하거나 덮어쓰지 않는다.
- handoff 문서에는 인증값 등 실제 민감정보를 기록하지 않는다.
