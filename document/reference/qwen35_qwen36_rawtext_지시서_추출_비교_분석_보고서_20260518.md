# qwen3.5-397B-A17B vs qwen3.6-27B Raw Text 지시서 추출 비교 분석 보고서

- 작성일: `2026-05-18`
- 분석 대상: `OCR + parser raw text 삽입` 방식의 5개 거래처 지시서 추출 테스트
- 비교 목적: qwen3.5-397B-A17B와 qwen3.6-27B의 정확도, 속도, token 사용량, prompt 민감도, calls 증가 원인을 운영 관점에서 비교한다.
- 결론 요약: 동일 API endpoint의 2cycle 최종 기준에서 두 모델 모두 `PASS 20 / FAIL 0 / BLOCKED 0`을 달성했다. 효율은 qwen3.6 non-thinking이 가장 좋고, qwen3.6 thinking은 정확도 이점 없이 시간과 token 비용이 크게 증가했다. qwen3.5는 초기에는 Cardiff/Hanwha에서 실패했지만 prompt 제외 규칙을 보강한 뒤 안정화됐다.

## 1. 비교 기준

| 구분 | 실행 조건 | Model | 용도 | 결과 |
| --- | --- | --- | --- | --- |
| qwen3.5 모델 최종 2cycle | 동일 API endpoint | `qwen/qwen3.5-397b-a17b` | 주 비교 기준 | `PASS 20 / FAIL 0 / BLOCKED 0` |
| qwen3.6 모델 최종 2cycle | 동일 API endpoint | `qwen/qwen3.6-27b` | 주 비교 기준 | `PASS 20 / FAIL 0 / BLOCKED 0` |
| qwen3.5 모델 초기 1cycle | 동일 API endpoint | `qwen/qwen3.5-397b-a17b` | 실패 보강 이력 | `PASS 9 / FAIL 1 / BLOCKED 0` |
| qwen3.5 모델 보강 중간 1cycle | 동일 API endpoint | `qwen/qwen3.5-397b-a17b` | 실패 보강 이력 | `PASS 9 / FAIL 1 / BLOCKED 0` |

비교 대상 문서는 KDB생명, 라이나생명, 한화생명, 동양생명, 카디프생명 5건이다. 각 최종 실행은 `non_thinking`과 `thinking` profile을 각각 2cycle 실행해 총 20개 결과를 생성했다.

## 2. 실행 구성

| 항목 | qwen3.5 raw text | qwen3.6 raw text |
| --- | --- | --- |
| 테스트 실행 방식 | 동일 raw-text 추출 절차 | 동일 raw-text 추출 절차 |
| 프롬프트 구성 | qwen3.5 전용 프롬프트 세트 | qwen3.6 전용 프롬프트 세트 |
| 기본 모델 | `qwen/qwen3.5-397b-a17b` | `qwen/qwen3.6-27b` |
| parser raw text 삽입 | 사용 | 사용 |
| non-thinking profile | `enable_thinking=false`, `temperature=0`, `max_tokens=16384` | 동일 |
| thinking profile | `enable_thinking=true`, `temperature=0.6`, `top_p=0.95`, `max_tokens=32768` | 동일 |
| JSON 안정화 | `response_format={"type":"json_object"}`, `PARSE_RETRIES=3` | 동일 |
| 동양생명 전략 | settlement/forecast 2-stage | 동일 |

두 raw-text 테스트의 실행 로직은 실질적으로 동일하다. 차이는 전용 프롬프트 세트와 기본 모델명 정도다. 따라서 최종 비교는 같은 입력 구성과 같은 validation 정책에서 모델과 prompt 세트의 차이를 보는 비교로 해석할 수 있다.

## 3. 전체 정확도

| Model | Total | PASS | FAIL | BLOCKED | Fund identity exact | JSON exact | CSV exact | Missing identities | Extra identities |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3.5 모델 | `20` | `20` | `0` | `0` | `20/20` | `20/20` | `20/20` | `0` | `0` |
| qwen3.6 모델 | `20` | `20` | `0` | `0` | `20/20` | `20/20` | `20/20` | `0` | `0` |

정확도 기준에서는 두 최종 실행 모두 동일하게 통과했다. 즉 최종 산출 JSON/CSV 기준에서는 펀드코드, 펀드명, 일자, 방향, 금액, row count 모두 정답셋과 일치했다.
두 최종 실행의 missing/extra identity 합계는 모두 `0 / 0`이다.

## 4. Profile별 성능

| Model | Profile | Total | PASS | FAIL | BLOCKED | Avg elapsed(s) | Avg total tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3.5 모델 | `non_thinking` | `10` | `10` | `0` | `0` | `27.723` | `10,309.6` |
| qwen3.5 모델 | `thinking` | `10` | `10` | `0` | `0` | `25.313` | `10,511.7` |
| qwen3.6 모델 | `non_thinking` | `10` | `10` | `0` | `0` | `19.702` | `10,243.0` |
| qwen3.6 모델 | `thinking` | `10` | `10` | `0` | `0` | `69.722` | `17,770.5` |

동일 API endpoint 기준 qwen3.6 non-thinking은 qwen3.5 non-thinking보다 평균 처리시간이 `28.9%` 짧고 token 사용량은 `0.6%` 낮았다. 반대로 qwen3.6 thinking은 qwen3.5 thinking보다 평균 처리시간이 `175.4%`, token 사용량이 `69.1%` 증가했다.

## 5. Case/Profile별 평균 비교

| Profile | Case | qwen3.5 elapsed | qwen3.6 elapsed | qwen3.5 tokens | qwen3.6 tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| `non_thinking` | KDB생명 | `23.878` | `13.985` | `7,133.0` | `7,122.0` |
| `non_thinking` | 라이나생명 | `10.669` | `11.352` | `10,265.0` | `10,254.0` |
| `non_thinking` | 한화생명 | `10.933` | `8.551` | `6,517.0` | `6,376.0` |
| `non_thinking` | 동양생명 | `44.536` | `26.368` | `13,213.0` | `13,211.0` |
| `non_thinking` | 카디프생명 | `48.599` | `38.254` | `14,420.0` | `14,252.0` |
| `thinking` | KDB생명 | `23.343` | `44.404` | `7,130.0` | `11,046.0` |
| `thinking` | 라이나생명 | `13.840` | `50.604` | `10,262.0` | `19,745.5` |
| `thinking` | 한화생명 | `10.258` | `44.345` | `6,514.0` | `10,591.0` |
| `thinking` | 동양생명 | `40.563` | `144.284` | `14,235.5` | `29,856.0` |
| `thinking` | 카디프생명 | `38.560` | `64.977` | `14,417.0` | `17,614.0` |

non-thinking에서는 qwen3.6이 라이나를 제외한 모든 case에서 더 빨랐다. thinking에서는 qwen3.6이 모든 case에서 qwen3.5보다 느리고 token 사용량도 더 많았다.

## 6. 프롬프트 차이

qwen3.5/qwen3.6 raw-text prompt는 대부분 동일하다. 동일한 parser raw text 삽입 정책, 펀드코드/펀드명 parser 권위값 원칙, JSON object wrapper, 거래처별 출력 schema를 공유한다.

### 프롬프트 구조

raw text 프롬프트는 이미지 OCR과 parser raw text를 동시에 사용하되, 두 입력의 역할을 분리하는 구조로 작성됐다. 목적은 펀드코드/펀드명은 권위값으로 고정하고, 금액/방향/날짜는 표의 컬럼 위치와 업무 규칙으로 판단하게 하는 것이다.

| 구성 블록 | 역할 |
| --- | --- |
| parser raw text 블록 | 문서에서 추출한 raw text를 별도 블록으로 넣어 모델이 fund identity를 이미지 OCR에만 의존하지 않게 한다. |
| identity 우선 규칙 | 펀드코드와 펀드명은 parser raw text를 권위값으로 사용한다. 모델이 펀드명을 요약, 번역, 유사어로 보정하거나 코드 일부를 생략하지 못하게 한다. |
| 이미지와 raw text 역할 분리 | fund identity는 raw text 우선, 금액/방향/날짜는 이미지 표와 raw text의 row 및 컬럼 위치를 대조해 판단한다. |
| 거래처별 주문 생성 규칙 | KDB D+1, 동양생명 2-stage, 한화 익영업일/익익영업일, 카디프 0/blank/dash 제외처럼 거래처별 주문 생성 기준을 별도로 둔다. |
| 출력 계약/형식 guard | JSON 객체 하나만 출력하고 wrapper를 생략하지 않도록 한다. reasoning-only, empty content, 최상위 배열, markdown, 설명문 출력을 금지한다. |
| 최종 self-check | row count, fund identity exact, 0원 주문 제거, 중복 주문 제거, 금액/날짜 컬럼 선택을 마지막에 다시 확인하게 한다. |

이 구조는 펀드명/펀드코드 exact match에 유리하다. 다만 raw text가 주문 생성 여부까지 자동으로 해결하는 것은 아니므로, 0원/blank/dash 제외와 컬럼 선택 같은 업무 규칙은 프롬프트에서 별도로 고정해야 한다.

### 프롬프트 예시

아래는 실제 운영 프롬프트 전문이 아니라, `OCR + parser raw text 삽입` 방식의 구조를 보여주는 축약 예시다. 펀드코드와 펀드명은 매번 바뀌는 값이므로 예시에 특정 값을 고정하지 않는다.

````text
이미지에 있는 {{거래처명}} 지시서 표를 OCR로 읽고, 표 안의 주문 데이터만 추출하세요.

parser raw text:
```text
{{PARSER_RAW_TEXT}}
```

identity 우선 규칙:
- 펀드코드와 펀드명은 parser raw text의 문서별 표 내용을 권위값으로 사용합니다.
- 특정 펀드코드 또는 펀드명을 외워서 쓰지 말고, 현재 parser raw text와 이미지에서 같은 row identity를 찾아 복사합니다.
- 이미지 OCR과 parser raw text가 다르면 펀드코드/펀드명은 parser raw text를 우선합니다.
- 펀드코드/펀드명을 보정, 번역, 축약, 띄어쓰기 변경하지 않습니다.
- parser raw text에 없는 펀드코드/펀드명을 추측해서 만들지 않습니다.

OCR 보강 규칙:
- 이미지 OCR과 parser raw text가 충돌하면 identity는 parser raw text 권위값을 우선합니다.
- 금액, 방향, 날짜는 이미지 OCR과 parser raw text의 row 및 컬럼 위치를 대조해 판단합니다.
- parser raw text에 있는 `<fund_code>`와 `<fund_name>`을 유사어로 바꾸거나 일부만 복사하지 않습니다.
- 특수문자, 로마숫자, 괄호, 하이픈, 공백 표기는 raw text와 문서 표기를 기준으로 유지합니다.
- 읽기 어려운 값은 추정하지 말고 row 단위 validation에서 불일치로 처리합니다.

OCR 민감어 사전:
- 거래처별 혼동쌍을 `<fund_code> -> <fund_name>` 기준으로 관리합니다.
- OCR 민감어 사전과 parser raw text가 같은 row에서 일치하면 그 값을 최종 identity로 사용합니다.
- 사전과 raw text가 충돌하면 임의 보정하지 말고 검증 대상으로 남깁니다.

주문 생성 규칙:
- 금액, 방향, 날짜는 이미지 표와 parser raw text의 row 및 컬럼 위치를 대조해 판단합니다.
- 설정/입금 금액이 0보다 크면 order_type="3" 주문입니다.
- 해지/출금 금액이 0보다 크면 order_type="1" 주문입니다.
- 0, blank, dash 금액은 주문으로 만들지 않습니다.
- 같은 row의 복수 금액 컬럼은 문서별 규칙에 따라 독립 주문 원천으로 검증합니다.

row 단위 validation:
- 같은 row의 펀드코드, 펀드명, 금액, 방향, 기준일이 서로 맞는지 확인합니다.
- fund identity와 금액/방향/날짜가 서로 다른 row에서 온 경우 오추출로 판단합니다.
- 최종 출력 전에 row count, fund identity exact, 0원 주문, 중복 주문, 금액/날짜 컬럼 선택을 다시 확인합니다.

오추출 방지 self-check:
- 최종 JSON의 모든 주문에 대해 `<fund_code>`, `<fund_name>`, `<amount>`, 방향, 기준일이 같은 row에서 왔는지 확인합니다.
- 0, blank, dash 금액 주문과 같은 identity/방향/금액의 중복 주문을 제거합니다.
- parser raw text에 없는 fund identity를 새로 만들지 않습니다.

출력 계약:
- 반드시 JSON 객체 하나만 출력합니다.
- wrapper를 생략하지 말고 orders 배열을 JSON 객체 내부에 포함합니다.
- reasoning-only, empty content, 최상위 배열, markdown, 설명문 출력은 금지합니다.

출력 형식:
{{OUTPUT_SHAPE}}
````

차이는 qwen3.5 prompt에만 존재하는 두 개의 보강이다.

| Case | qwen3.5 prompt 추가 규칙 | 보강 배경 |
| --- | --- | --- |
| 카디프생명 | `0`, blank, dash 금액 방향은 주문 생성 금지. 한 fund row에서 한쪽만 non-zero이면 주문은 정확히 1개. 최종 orders에서 0원/blank/중복 제거. | 초기 1cycle에서 thinking이 기대 46건 대신 92건을 출력했다. 반대 방향 0원 주문 46건이 extra order로 잡혔다. |
| 한화생명 | pipe-separated parser table에서 `수탁은행/수령금액` 다음 첫 번째 미래금액은 `익영업일/이체예상금액`으로 제외하고, 두 번째 미래금액만 `익익영업일/이체예상금액`으로 t_day=03 생성. | 보강 중간 1cycle에서 thinking이 제외해야 할 `익영업일` 금액을 `익익영업일` 청구분으로 잘못 해석해 extra order 1건이 발생했다. |

이 차이는 qwen3.5 모델이 펀드코드/펀드명 자체를 못 읽어서 생긴 문제가 아니라, 출력 제외 규칙과 인접 컬럼 해석을 덜 보수적으로 적용한 데서 생겼다. qwen3.6 raw-text prompt는 이 두 추가 보강 없이도 1cycle과 2cycle에서 모두 PASS했다.

## 7. 입력 방식 비교: OCR + 거래처 프롬프트 vs OCR + raw text + 거래처 프롬프트

이 보고서의 raw-text 방식은 기존 `OCR + 거래처 프롬프트` 방식과 완전히 동일 조건의 통제 A/B 실험은 아니다. 기존 OCR 방식 보고서는 이미지 OCR과 거래처별 업무 규칙 prompt를 중심으로 안정화했고, raw-text 방식은 동일 문서군에 parser raw text를 추가해 fund identity를 더 강하게 고정한 운영 개선안에 가깝다. 따라서 아래 비교는 순수 모델 성능 비교가 아니라 입력 구성, prompt guard, validation 정책까지 포함한 운영 관점 비교로 해석해야 한다.

기존 `OCR + 거래처 프롬프트` 방식의 초기 안정성 참고값은 qwen3.5가 `10 PASS / 10 FAIL`, qwen3.6이 `11 PASS / 9 FAIL`이었다. 최종 안정화 후에는 두 방식 모두 전체 PASS에 도달했지만, 실패를 줄이는 방식은 달랐다. OCR-only 방식은 거래처별 prompt에 OCR 민감어와 컬럼 규칙을 직접 더 많이 고정해야 했고, raw-text 방식은 parser raw text를 별도 권위 입력으로 제공해 펀드코드와 펀드명을 모델 추론 대상에서 복사 대상으로 바꿨다.

| 비교 항목 | OCR + 거래처 프롬프트 | OCR + raw text + 거래처 프롬프트 | 운영 해석 |
| --- | --- | --- | --- |
| 입력 권위값 | 이미지 OCR 결과와 prompt 내 사전/규칙이 주 입력이다. 펀드명/펀드코드도 이미지에서 다시 읽고 보정해야 한다. | 이미지 OCR과 별도로 parser raw text를 넣고, 펀드명/펀드코드는 raw text를 권위값으로 사용한다. | raw text 방식은 fund identity exact match 안정화에 유리하다. |
| 프롬프트 부담 | 거래처별 prompt가 OCR 민감어, 펀드명 후보, 제외 row, 금액 컬럼 규칙을 모두 강하게 떠안는다. | prompt는 raw text 우선순위와 row 대조 규칙을 명시하고, identity 값 자체는 raw text에서 복사하게 한다. | raw text가 들어가도 업무 규칙 prompt는 필요하지만, 고유명사 추론 부담은 줄어든다. |
| OCR 오추출 리스크 | `유니버셜/유니버설`, `종신/증권`, `Ⅱ/II`, `디폴트/디프트` 같은 표기 흔들림이 바로 exact mismatch로 이어질 수 있다. | 같은 row의 raw text 값이 있으면 이미지 OCR이 흔들려도 identity는 raw text 기준으로 고정할 수 있다. | 고유명사와 특수문자는 모델의 시각 추론보다 parser raw text 권위값으로 잠그는 편이 안전하다. |
| 업무 규칙 의존도 | D+1, 익영업일/익익영업일, 0원/blank/dash 제외 같은 주문 생성 규칙은 prompt가 직접 고정해야 한다. | 동일하게 prompt가 고정해야 한다. raw text는 주문 생성 여부, 날짜 컬럼 선택, 제외 금액 판단을 자동으로 해결하지 않는다. | raw text는 identity 안정화 장치이지 업무 규칙 엔진이 아니다. |
| token/latency 영향 | raw text 삽입이 없어 입력은 상대적으로 짧지만, OCR 불확실성을 prompt와 retry로 보강해야 한다. | parser raw text가 추가되어 입력 token은 늘 수 있으나, identity 재추론과 mismatch feedback 비용을 줄일 수 있다. | 운영 비용은 문서 길이와 raw text 품질에 따라 달라지며, 안정성 이점과 함께 평가해야 한다. |
| 검증/운영 적합성 | 초기 안정화 전에는 OCR-sensitive field와 출력 wrapper 실패가 반복될 수 있다. | 최종 raw-text 2cycle 기준 두 모델 모두 `PASS 20 / FAIL 0 / BLOCKED 0`, missing/extra identity `0 / 0`을 달성했다. | 신규 거래처 온보딩에서는 raw text 삽입, row 단위 validation, 거래처별 제외 규칙을 함께 적용하는 구성이 더 재현 가능하다. |

핵심 인사이트는 두 가지다. 첫째, raw text는 펀드코드와 펀드명을 권위값으로 고정하는 데 강하지만, 주문 생성 규칙과 컬럼 선택 규칙을 대체하지 않는다. Cardiff의 0원 주문 제외, Hanwha의 익영업일/익익영업일 구분, KDB의 D+1 금액 생성처럼 업무 규칙은 여전히 거래처별 prompt와 validation이 담당해야 한다.

둘째, 최종 `20/20 PASS`는 모델 단독 성능이 아니라 입력 설계, 거래처별 prompt guard, JSON wrapper 계약, parser raw text 권위값, 정답셋 기반 validation이 결합된 시스템 성능이다. 따라서 운영 평가는 “어떤 모델이 더 잘 읽었는가”보다 “어떤 입력과 검증 구조가 반복 가능한 exact match를 만드는가”에 초점을 둬야 한다.

## 8. OCR 오추출 해결 방안

raw text 방식의 핵심 목적은 OCR 결과만으로 흔들릴 수 있는 펀드코드와 펀드명을 parser raw text의 권위값으로 안정화하는 것이다. 최종 결과에서는 두 모델 모두 fund identity exact `20/20`을 달성했지만, 운영에서는 새 문서와 새 펀드명이 계속 들어오므로 OCR 오추출 방지 규칙을 명시적으로 유지해야 한다.

| 해결 항목 | 구체 방안 |
| --- | --- |
| parser raw text 권위값 사용 | 펀드코드와 펀드명은 이미지에서 다시 추론하지 않고 parser raw text에서 발견한 값을 그대로 복사한다. 모델이 비슷한 이름으로 보정하거나, 한글 음절을 유사어로 바꾸거나, 코드 일부를 생략하지 못하게 “raw text 값 우선, 임의 수정 금지”를 프롬프트에 둔다. |
| 펀드코드/펀드명 row 단위 validation | 같은 row의 펀드코드, 펀드명, 금액, 방향, 기준일을 하나의 묶음으로 검증한다. 펀드코드는 맞지만 펀드명이 옆 row의 값이거나, 펀드명은 맞지만 금액이 다른 컬럼에서 온 경우 모두 오추출로 본다. |
| OCR 민감어 사전 | 거래처별로 자주 흔들리는 고유명사, 특수문자, 로마숫자, 괄호, 하이픈, 공백 표기를 관리한다. 예를 들어 `유니버셜/유니버설`, `종신/증권`, `Ⅱ/II`, `디폴트/디프트` 같은 혼동쌍은 사전에 기록하고, parser raw text와 충돌할 때는 정답셋 기준 표기를 우선한다. |
| 금액/날짜 컬럼 검증 | 금액은 숫자만 맞으면 통과시키지 않고 컬럼 위치와 기준일을 함께 확인한다. KDB D+1, 한화 익영업일/익익영업일처럼 한 row에 복수 금액 컬럼이 있는 경우 각 컬럼을 독립 원천으로 보고, 제외해야 할 컬럼은 주문 생성 대상에서 명확히 제외한다. |
| 프롬프트 guard | “펀드명/펀드코드는 raw text에서 찾은 값을 그대로 복사”, “요약/번역/유사어 보정 금지”, “읽기 어려운 값은 추정하지 않음”, “코드와 이름이 충돌하면 row 전체를 재검토” 같은 규칙을 거래처별 prompt에 포함한다. |
| validation feedback loop | exact mismatch가 발생하면 해당 항목을 OCR 민감어 사전, 거래처별 제외 규칙, 프롬프트 guard에 반영한다. 반복 mismatch는 모델 실패로만 보지 말고 raw text 추출 품질, row 매핑, 금액/날짜 컬럼 검증 로직까지 함께 점검한다. |

운영 절차는 `parser raw text 추출 -> 펀드코드/펀드명 권위값 지정 -> row 단위 validation -> 금액/날짜 컬럼 검증 -> mismatch feedback` 순서가 적절하다. 이 흐름을 유지하면 모델이 OCR 결과를 추정해서 고치는 비중을 줄이고, 검증 가능한 raw text와 업무 규칙으로 값을 고정할 수 있다.

## 9. calls 분석

`calls`는 사용자가 수동으로 재실행한 횟수가 아니라, 테스트 절차 내부에서 한 case 결과를 만들기 위해 수행한 LLM API 호출 수다. 동양생명은 settlement table과 forecast table을 따로 추출하므로 정상이어도 기본 `calls=2`다.

| 실행 단계 | Call distribution | 해석 |
| --- | --- | --- |
| qwen3.5 최종 2cycle | `1 call: 16건`, `2 calls: 4건` | multi-call 4건은 모두 동양생명 2cycle × 2profile의 2-stage 호출이다. parse retry는 발생하지 않았다. |
| qwen3.6 최종 2cycle | `1 call: 15건`, `2 calls: 4건`, `3 calls: 1건` | 동양생명 2-stage가 기본 multi-call이고, thinking에서 reasoning-only/empty content로 인한 parse retry가 일부 발생했다. |

qwen3.6의 추가 calls 상세는 다음과 같다.

| Model | Case/Profile | Calls | Finish reasons | 원인 |
| --- | --- | ---: | --- | --- |
| qwen3.6 모델 | 라이나생명 cycle 1 thinking | `2` | `extract_attempt_1: null`, `extract_attempt_2: stop` | 첫 응답이 reasoning-only/empty content라 JSON parse가 실패했고 retry에서 성공했다. |
| qwen3.6 모델 | 동양생명 cycle 2 thinking | `3` | `settlement_attempt_1: stop`, `forecast_attempt_1: null`, `forecast_attempt_2: stop` | settlement는 성공했지만 forecast 첫 응답이 empty content라 forecast만 retry했다. |

따라서 calls 증가는 대부분 문서 난이도보다 출력 형식 안정성 또는 backend 응답 정책에서 기인했다. 정확도는 최종 retry 후 모두 PASS였지만, 운영 비용과 지연 측면에서는 중요한 리스크다.

## 10. 실패/보강 이력

| 실행 단계 | 결과 | 실패 내용 | 후속 처리 |
| --- | --- | --- | --- |
| qwen3.5 초기 1cycle | `PASS 9 / FAIL 1` | 카디프 thinking에서 0원 반대 방향 주문 46건 extra. | qwen3.5 Cardiff prompt에 0/blank/dash 주문 금지와 중복 제거 규칙 추가. |
| qwen3.5 보강 중간 1cycle | `PASS 9 / FAIL 1` | 한화 thinking에서 `익영업일` 금액을 `익익영업일` 청구분으로 오해해 extra order 1건. | qwen3.5 Hanwha prompt에 pipe-separated raw text 컬럼 위치 규칙 추가. |
| qwen3.5 보강 후 1cycle 검증 | `PASS 10 / FAIL 0` | 1cycle smoke 기준 clean. | 최종 2cycle에서 `PASS 20`. |
| qwen3.6 1cycle 검증 | `PASS 10 / FAIL 0` | 1cycle smoke 기준 clean. | 최종 2cycle에서 `PASS 20`. |

qwen3.5의 초기 실패는 prompt 보강 후 해소됐다. qwen3.6은 같은 raw-text 방식에서 1cycle과 2cycle 모두 정확도 실패 없이 통과했지만, thinking에서 parse retry와 높은 reasoning token 사용이 관찰됐다.

## 11. 인사이트

1. 기본 운영 profile은 non-thinking이 적합하다.

두 최종 실행 모두 non-thinking으로 정확도 100%를 달성했다. 특히 qwen3.6 모델 non-thinking은 평균 `19.702s`, `10,243.0 tokens`로 이번 raw-text 최종 비교 중 가장 효율적이다.

2. qwen3.6 thinking은 정확도 이점 없이 비용 리스크가 크다.

qwen3.6 모델 thinking은 PASS는 유지했지만 qwen3.5 thinking 대비 평균 처리시간이 `175.4%`, token이 `69.1%` 증가했다. 라이나와 동양생명에서는 reasoning-only/empty content retry도 발생했다.

3. qwen3.5는 더 명시적인 제외 규칙이 필요했다.

qwen3.5 초기 실패는 펀드명/펀드코드 인식 실패가 아니라 0원 주문 제외와 인접 컬럼 선택 문제였다. qwen3.5 prompt에 negative rule을 더 구체화하자 2cycle 최종에서 안정화됐다.

4. 최종 PASS는 모델 단독 성능이 아니라 시스템 성능이다.

이번 raw-text 방식의 성공 요인은 모델 자체뿐 아니라 parser raw text 삽입, 거래처별 prompt guard, JSON object response format, parse retry, 정답셋 기반 validation이 결합된 결과다. 운영 평가는 모델명만이 아니라 endpoint, profile, prompt, retry 정책을 함께 봐야 한다.

5. raw text는 OCR 오추출 방지에 유리하지만 업무 규칙을 대체하지는 않는다.

raw text는 펀드명/펀드코드 exact match 안정화에 유리하다. 다만 주문 생성 여부, 0원/blank/dash 제외, 금액/날짜 컬럼 선택은 별도 업무 규칙으로 판단해야 한다. 따라서 raw text 권위값과 거래처별 제외 규칙을 함께 적용해야 누락과 오추출을 동시에 줄일 수 있다.

6. 입력 방식 선택은 안정성과 비용을 함께 봐야 한다.

`OCR + 거래처 프롬프트` 방식은 입력이 짧고 단순하지만, OCR 민감 고유명사와 특수문자가 많은 문서에서는 prompt 사전과 후속 보강 부담이 커진다. `OCR + raw text + 거래처 프롬프트` 방식은 입력 token이 늘 수 있지만 fund identity를 권위값으로 고정해 반복 mismatch를 줄일 수 있다. 운영에서는 신규 거래처와 신규 펀드명이 계속 들어오는 문서일수록 raw text 병행 방식이 더 방어적이다.

## 12. 운영 권고

| 목적 | 권고 |
| --- | --- |
| 기본 운영 후보 | qwen3.6 모델 non-thinking 우선. 정확도와 평균 처리시간이 가장 좋다. |
| qwen3.5 사용 | prompt 보강 후 정확도는 충분하다. 다만 Cardiff/Hanwha 같은 제외 규칙은 명시적으로 유지해야 한다. |
| thinking 상시 사용 | 권장하지 않는다. 정확도 이점은 없고 token, latency, retry 리스크가 커진다. |
| 신규 문서 온보딩 | 모델 교체보다 먼저 parser raw text 삽입, OCR 민감어 사전, row 단위 validation, 금액/날짜 컬럼 검증, row 제외 규칙, JSON wrapper guard를 확정한다. |

## 13. 결론

동일 API endpoint의 최종 2cycle 기준에서 qwen3.5-397B-A17B와 qwen3.6-27B는 모두 5개 거래처 지시서 20개 결과를 전부 통과했다. 운영 관점에서는 qwen3.6 모델 non-thinking이 가장 효율적이며, qwen3.5는 prompt 보강 후 안정적인 대안으로 볼 수 있다.

다만 qwen3.6 thinking은 정확도는 같아도 token과 처리시간이 크게 증가했다. 따라서 추출 품질을 높이기 위해 무조건 thinking을 켜기보다는, parser raw text와 거래처별 제외 규칙을 강화하고 non-thinking을 기본값으로 쓰는 접근이 더 실용적이다.
