# Handoff: Stage 3 보정, 템플릿 chart 계약, best-failed final, 문서 최신화

> 작성일: 2026-05-29
> 워크스페이스: `/Users/bhkim/Documents/Codex/poc_sam_etf_report`
> 브랜치: `codex/log-artifacts`
> 기준 커밋: `07cbe2d feat: add report verification and logging flow`
> 목적: 새 세션이 KB/Woori live 검증, Stage 3 local repair, template chart profile, Stage 5/6 반복 종료 정책, 문서 최신화 상태를 바로 이어받도록 정리한다.

## 1. 현재 상태 요약

- 현재 작업은 아직 커밋 전이며, 이번 handoff 작성 후 커밋/푸시할 예정이다.
- CLI는 Stage 0~6 경로를 실행하며 `componentMode=novita`에서는 `verificationMode=novita`만 허용한다.
- Stage 3는 initial HTML 생성 후 local validator를 수행하고, 실패 시 correction을 최대 3회 수행한다.
- correction 3회 후에도 non-chart source fragment가 누락/변형되면 local repair가 해당 component 내부 HTML을 Stage 2 원문으로 복원한 뒤 validator를 다시 수행한다.
- Stage 4 chart type은 Stage 2 `chartSpec.type`이 아니라 template `chartProfile` 기준으로 결정한다.
  - KB: template image에 chart가 없으므로 `fallbackChartType=bar`, `chartTypeSource=template_contract`.
  - Woori: template image 분석 chart가 있으므로 `detectedChartType=bar`, `chartTypeSource=template_image_analysis`.
- Stage 5는 템플릿 이미지를 layout/style 기준으로만 사용한다. 템플릿 이미지의 샘플 텍스트/수치/섹션명은 데이터 기준이 아니다.
- Stage 6는 passed version을 우선 final로 확정한다. max iteration 소진 후 passed version이 없으면 best failed version을 final로 복사하고 `verificationPassed=false`를 기록한다.

## 2. 완료된 구현/검증 작업

| 구분 | 상태 | 내용 |
|---|---|---|
| Template chart profile | 완료 | `report_templates.json`에 KB/Woori `chartProfile.performance_chart` 계약 추가 |
| Chart renderer | 완료 | `effectiveChartType`, `chartTypeSource`, `originalChartSpecType` 기록 및 template 기준 chart type 적용 |
| Stage 3 correction loop | 완료 | initial + correction 최대 3회 + `layout_validation_loop.json`/attempt HTML 기록 |
| Stage 3 local repair | 완료 | correction 반복 실패 시 source fragment 누락 component를 Stage 2 원문 HTML로 복원 |
| Stage 5 contract | 완료 | 템플릿 sample content와 Stage 2 데이터 역할 분리, `template_mismatch` 기준 강화 |
| Stage 5 revision guard | 완료 | best failed base 선택, regression tracking, minimal patch contract 기록 |
| Stage 6 fallback final | 완료 | `best_failed_after_max_iterations` finalization reason 추가 |
| README/plan docs | 완료 | `document/README.md`와 `document/plan` 5개 문서를 현재 계약/검증 결과로 갱신 |

## 3. Live 검증 결과

| 템플릿 | jobId | 조건 | 결과 |
|---|---|---|---|
| KB | `job_20260529_112832_03047792` | `component-mode=novita`, `verification-mode=novita`, `renderer-mode=playwright`, `--max-iterations 2` | CLI exit code `0`, v2 `passed=true`, final `sourceVersion=2`, `finalizationReason=passed_verification` |
| Woori | `job_20260529_113037_92510096` | `component-mode=novita`, `verification-mode=novita`, `renderer-mode=playwright`, `--max-iterations 2` | CLI exit code `0`, Stage 3 `local_repair` passed, v1/v2 Stage 5 fail, final `sourceVersion=1`, `verificationPassed=false`, `finalizationReason=best_failed_after_max_iterations` |

확인된 공통 조건:

- final HTML에 `data-chart-type="bar"`가 존재한다.
- final HTML에 `data-chart-placeholder`가 남지 않는다.
- Woori Stage 5 fail은 실행 오류가 아니라 header/footer logo, section marker, table/chart style의 템플릿 정합성 미수렴이다.

## 4. 문서 최신화 범위

| 파일 | 반영 내용 |
|---|---|
| `document/README.md` | Stage 3 local repair, Stage 4 chart metadata, Stage 6 best failed final, KB/Woori live 결과, log artifact 설명 |
| `document/plan/KB_Woori_템플릿_정합성_개선_계획-20260529.md` | 완료된 구현/검증과 남은 deterministic layout 후속안을 분리 |
| `document/plan/리포트 생성 Idea-20260526134517.md` | Stage 3/4/5/6 high-level 흐름을 현재 구현 계약으로 보정 |
| `document/plan/리포트_엔진_CLI_v1_개발_계획-20260527.md` | chart profile, manual-pass 제한, max iteration, best failed final 정책 반영 |
| `document/plan/리포트_엔진_상세_설계서-20260527.md` | Stage 3 local repair, Stage 4 chartProfile, Stage 5 데이터/템플릿 역할 분리, Stage 6 fallback final 반영 |
| `document/plan/리포트_엔진_아키텍처_문서-20260527.md` | component 책임, log 구조, issue flow, 장애 처리 정책 보정 |
| `document/handoff/handoff_sum.md` | 최신 handoff 라우팅을 이 문서로 갱신 |

## 5. 다음 세션 시작 포인트

1. `git status --short --branch --untracked-files=all`로 커밋/푸시 상태를 확인한다.
2. 최신 runtime 계약은 이 handoff와 `document/README.md`를 먼저 읽고 확인한다.
3. Woori 템플릿 정합성 개선은 LLM revision 반복보다 deterministic layout skeleton 또는 strict visual comparator 도입을 우선 검토한다.
4. KB는 `max-iterations=2` live 기준 v2 pass가 확인되었으므로, 후속 작업은 Woori template mismatch와 visual comparator 쪽에 집중한다.

## 6. 검증 명령

문서와 코드 상태 검증 명령:

```bash
git diff --check
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover tests -v
```

stale 표현 검색은 `document/plan`과 `document/README.md`를 대상으로 수행한다. 검색 패턴 자체가 handoff 본문에 남아 오탐을 만들지 않도록 이 문서에는 패턴 문자열을 직접 기록하지 않는다.

이번 handoff 작성 중 확인한 검증 결과:

| 검증 | 결과 |
|---|---|
| stale 표현 검색 | 출력 없음 |
| 민감정보 패턴 검색 | 출력 없음 |
| Markdown code fence balance | 문제 없음 |
| `git diff --check` | 통과 |
| backend unittest | `Ran 142 tests`, `OK (skipped=1)` |

handoff 검수 명령:

```bash
rg -n "handoff_|최신 Handoff|대체됨|superseded|replaced" document/handoff
rg -n "민감정보|인증값|base64 payload" document/handoff document/README.md document/plan
```

## 7. 보안/운영 주의

- 문서에는 실제 LLM 인증값, 인증 header 값, image base64 payload를 기록하지 않는다.
- `backend/log/*`, `backend/runs/*`, `/tmp/*.log`는 검증 artifact이며 repo 문서에는 필요한 job id와 결과 요약만 남긴다.
- prompt 파일을 수정하거나 새로 만들 때는 상단에 한국어 주석을 먼저 추가한다.
