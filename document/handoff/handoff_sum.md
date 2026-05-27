# Handoff Map

> 목적: `document/handoff` 폴더에 누적되는 handoff 문서의 위치와 요약을 관리한다.
> 운영 방식: 새 handoff 문서를 만들 때 기존 문서는 보존하고, 이 문서의 최신 handoff와 목록 테이블에 새 항목을 추가한다.

## 최신 Handoff

- [handoff_20260527_report_engine_cli_task6_ready.md](handoff_20260527_report_engine_cli_task6_ready.md)

## Handoff 목록

| 작성일 | 문서 | 주제 | 상태 | 다음 세션 시작 포인트 |
|---|---|---|---|---|
| 2026-05-27 | [handoff_20260527_report_engine_cli_task6_ready.md](handoff_20260527_report_engine_cli_task6_ready.md) | 리포트 엔진 CLI Task 1~5 구현, 로그 산출물, 입력 문서 정합화, Task 6 Novita 선행 계획 반영 | 진행 중 | Git 상태 확인 후 Task 6 계획 변경분 검수, Stage 2 `componentMode=novita` 선행 구현 착수 |
| 2026-05-27 | [handoff_20260527_report_engine_design.md](handoff_20260527_report_engine_design.md) | 리포트 엔진 설계 문서화, 국민은행 preview image 반영, 검수 결과 정리 | 완료 | 설계서/아키텍처 문서를 읽고 backend Stage 1~6 구현 계획부터 착수 |

## 관리 규칙

- 최신 handoff는 이 문서의 `최신 Handoff` 섹션에 명시한다.
- 새 handoff가 생기면 `Handoff 목록`에 한 줄을 추가한다.
- 이전 handoff 문서는 삭제하거나 덮어쓰지 않는다.
- handoff 문서에는 API key, token, secret 등 실제 비밀값을 기록하지 않는다.
