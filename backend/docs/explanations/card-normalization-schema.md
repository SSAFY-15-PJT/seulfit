# 카드 데이터 정규화 스키마

## 문서 목적

이 문서는 카드사 웹페이지에서 수집한 카드 상품과 혜택 정보를 추천 계산 코어와
Neo4j에서 공통으로 사용할 수 있는 데이터로 변환하기 위한 정규화 계약을 정의한다.

이 문서는 설계 설명용 문서이며, 아직 정규화 코드나 크롤러 구현이 완료되었다는
의미는 아니다.

## 전체 데이터 흐름

```text
카드사 웹페이지
  -> 크롤링 원문
  -> 정규화
  -> 데이터 검증
  -> 승인된 카드 데이터
  -> Neo4j 적재
  -> 추천 계산 코어
```

크롤러는 데이터를 수집하고 원문을 보존한다. 정규화 계층은 문자열을 계산 가능한
값으로 변환하고, 추천 계산 코어는 검증된 숫자와 열거형만 사용한다.

## 데이터 계층

### 원본 데이터

카드사 페이지에서 수집한 값을 가능한 한 그대로 보존한다.

```json
{
  "source_url": "https://example.com/card/1",
  "collected_at": "2026-06-19T10:00:00+09:00",
  "raw_product_name": "카드명",
  "raw_annual_fee_text": "국내전용 1만원",
  "raw_benefit_text": "커피전문점 10% 할인"
}
```

원문은 파싱 오류 검토, 카드사 페이지 변경 감지와 재처리를 위해 삭제하지 않는다.

### 정규화 데이터

추천 계산 코어가 사용할 수 있도록 금액, 비율, 횟수와 상태값을 표준화한다.

```json
{
  "annual_fee": 10000,
  "previous_month_requirement": 300000,
  "monthly_discount_limit": 15000,
  "benefits": []
}
```

### 검증 결과

추천 계산에 사용할 수 있는지와 수동 검토가 필요한 이유를 기록한다.

```json
{
  "parse_status": "review_required",
  "validation_errors": [],
  "review_reasons": [
    "특정 가맹점 범위를 자동 판별할 수 없음"
  ],
  "unsupported_conditions": [
    "merchant_scope"
  ]
}
```

## 단위 규칙

| 값 | 단위 및 형식 |
| --- | --- |
| 금액 | 원 단위의 0 이상 정수 |
| 할인율·적립률 | 0 이상 1 이하의 실수 |
| 이용 횟수 | 0 이상의 정수 |
| 연회비 | 연 단위 원화 |
| 전월 실적 | 월 단위 원화 |
| 월 할인 한도 | 월 단위 원화 |
| 수집 시각 | 타임존을 포함한 ISO 8601 문자열 |

`null`은 조건이 없거나 확인되지 않았다는 뜻이다. `0`은 값이 명시적으로
0이라는 뜻이므로 동일하게 취급하지 않는다.

## 카드 상품 스키마

```text
CardProduct
  external_id: string
  issuer: string
  provider: string
  source_channel: string
  card_type: credit | debit
  name: string
  image_path: string | null
  source_image_url: string | null
  image_content_type: string | null
  image_checksum: string | null
  image_download_status: pending | success | failed
  source_url: string
  collected_at: datetime

  annual_fee: integer | null
  previous_month_requirement: integer
  monthly_discount_limit: integer | null

  focus: string[]
  benefits: BenefitRule[]

  parse_status: string
  raw_text: string
  validation_errors: string[]
  review_reasons: string[]
```

필수값:

- `external_id`
- `issuer`
- `provider`
- `source_channel`
- `card_type`
- `name`
- `source_url`
- `collected_at`
- `annual_fee`
- `previous_month_requirement`
- `benefits`
- `raw_text`

검증 규칙:

- 연회비와 전월 실적은 0 이상이어야 한다.
- 통합 할인 한도는 `null` 또는 0 이상이어야 한다.
- 혜택 규칙이 하나 이상 있어야 한다.
- 카드명에 `체크` 또는 `CHECK`가 있는데 `card_type=credit`이면 오류로 처리한다.
- 알 수 없는 카테고리를 임의로 `etc`로 확정하지 않는다.
- 출처 URL과 원문이 없으면 추천에 활성화하지 않는다.
- 원문에 월 최대 이용 횟수가 있는데 구조화된 횟수 한도가 없으면
  `review_required`로 유지한다.

`issuer`는 약관과 정산 책임을 가진 실제 발급사다. `provider`는 상품을
소개하거나 중개하는 서비스이며, `source_channel`은 실제로 크롤링한 사이트다.

예를 들어 카카오뱅크에서 안내하는 제휴 신용카드는 다음처럼 저장할 수 있다.

```json
{
  "issuer": "제휴 카드 발급사",
  "provider": "카카오뱅크",
  "source_channel": "kakaobank",
  "card_type": "credit"
}
```

## 이미지 저장

카드 이미지는 공식 상품 페이지의 원본 URL을 보존하면서 로컬 파일로
다운로드한다.

```text
backend/media/cards/{source_channel}/{external_id}.{extension}
```

저장 예시:

```json
{
  "image_path": "cards/kakaobank/friends-check.webp",
  "source_image_url": "https://example.com/card.webp",
  "image_content_type": "image/webp",
  "image_checksum": "sha256:...",
  "image_download_status": "success"
}
```

이미지 다운로드 실패는 카드 상품 데이터 전체를 무효화하지 않는다.
`image_download_status=failed`로 기록하고 원본 URL 또는 기본 이미지를 사용한다.

동일한 카드 상품의 색상이나 캐릭터 디자인은 별도 상품으로 계산하지 않는다.
상품 식별자는 혜택과 약관 단위로 유지하고, 이미지 변형은 별도 목록으로
보존할 수 있다.

## 중복 제거

제휴 카드는 발급사 홈페이지와 플랫폼 홈페이지에서 중복 수집될 수 있다.
가능하면 공식 상품 식별자를 우선 사용하고, 식별자가 없으면 다음 조합으로
중복 후보를 탐지한다.

```text
issuer + normalized_name + card_type
```

출처가 여러 개인 경우 레코드를 무조건 삭제하지 않고 출처별 원문과 URL을
보존한 뒤 하나의 정규화 상품에 연결한다.

## 실적 구간별 통합 한도

카드 전체 월 할인 한도가 전월 실적에 따라 달라지면 `CardBenefitTier`로
저장한다.

```text
CardBenefitTier
  card: CardProduct
  scope: card_total
  minimum_spending: integer
  maximum_spending: integer | null
  monthly_discount_limit: integer
  raw_text: string
  parse_status: validated | invalid
```

구간은 최소값을 포함하고 최대값은 포함하지 않는다.

```text
minimum_spending <= previous_month_spending < maximum_spending
```

`maximum_spending=null`이면 상한이 없는 마지막 구간이다.

업종별 이용금액 한도나 월 제공 횟수 한도는 카드 전체 할인액 한도와 의미가
다르므로 `CardBenefitTier`로 변환하지 않는다.

공유 서비스 한도는 `CardServiceLimitTier`로 저장한다.

```text
CardServiceLimitTier
  card: CardProduct
  benefit_group: string
  minimum_spending: integer
  maximum_spending: integer | null
  monthly_spending_limit: integer | null
  monthly_discount_limit: integer | null
  monthly_usage_limit: integer | null
```

같은 `benefit_group`을 가진 여러 카테고리 혜택은 선택된 서비스 구간의 한도를
공유한다.

## 연회비 미확인

연회비를 공식 출처에서 확인하지 못하면 `0`이 아니라 `null`로 저장한다.

```text
annual_fee = null
estimated_net_value = null
is_recommendation_ready = false
```

총혜택 계산과 검토는 가능하지만 순혜택 기준 최종 추천에는 포함하지 않는다.

## 혜택 규칙 스키마

```text
BenefitRule
  category: string
  discount_type: rate | amount

  discount_rate: number | null
  discount_amount: integer | null

  minimum_transaction_amount: integer
  maximum_transaction_amount: integer | null
  per_transaction_limit: integer | null
  daily_benefit_limit: integer | null
  daily_usage_limit: integer | null
  monthly_usage_limit: integer | null
  estimated_monthly_uses: integer | null
  category_monthly_limit: integer | null

  merchant_scope: string[]
  channel: all | online | offline
  start_hour: integer | null
  end_hour: integer | null
  condition_text: string
  exclusion_text: string
  raw_text: string

  parse_status: string
  unsupported_conditions: string[]
```

예시:

```json
{
  "category": "cafe",
  "discount_type": "rate",
  "discount_rate": 0.1,
  "discount_amount": null,
  "minimum_transaction_amount": 5000,
  "per_transaction_limit": 3000,
  "daily_usage_limit": 1,
  "monthly_usage_limit": 5,
  "estimated_monthly_uses": null,
  "category_monthly_limit": 10000,
  "merchant_scope": [
    "스타벅스",
    "투썸플레이스"
  ],
  "channel": "offline",
  "condition_text": "전월 실적 30만원 이상",
  "exclusion_text": "상품권 구매 제외",
  "raw_text": "커피전문점 10% 할인",
  "parse_status": "review_required",
  "unsupported_conditions": [
    "daily_usage_limit",
    "merchant_scope"
  ]
}
```

## 할인 유형 검증

할인율 혜택:

```text
discount_type = rate
discount_rate 필수
discount_amount = null
0 <= discount_rate <= 1
```

정액 혜택:

```text
discount_type = amount
discount_amount 필수
discount_rate = null
discount_amount >= 0
```

할인율과 정액 할인값이 동시에 존재하거나 필요한 값이 누락되면 `invalid`로
처리한다.

## 카테고리

초기 지원 카테고리는 다음과 같다.

- `cafe`
- `convenience`
- `mart`
- `food`
- `shopping`
- `etc`

카드사 혜택 문구에서 새로운 업종이 반복적으로 발견되면 내부 카테고리 추가를
검토한다. 파싱할 수 없는 업종을 즉시 `etc`로 변환하지 않고
`review_required`로 분류한다.

## 계산 지원 범위

현재 추천 계산 코어가 지원하는 조건:

- 할인율
- 정액 할인
- 최소 결제금액
- 건당 할인 한도
- 월 이용횟수
- 카테고리 월 한도
- 카드 월 통합 할인 한도
- 전월 실적
- 연회비
- 거래 가맹점명과 명시된 가맹점 범위

필드로 보존하지만 아직 계산하지 않는 조건:

- 일 이용횟수
- 온라인·오프라인 제한
- 요일 또는 시간대 조건
- 간편결제 수단 조건
- 할인 제외 거래
- 전월 실적 제외 항목
- 실적 구간별 차등 한도

특정 가맹점 제한은 구체적인 `merchant_scope` 목록이 추출된 경우에만 지원한다.
목록을 추출하지 못했거나 미지원 조건이 존재하는 혜택을 정상 데이터처럼
조용히 계산하지 않는다.
해당 혜택에 `review_required`와 `unsupported_conditions`를 기록한다.

## 상태값

```text
raw
  -> normalized
  -> validated
  -> active
```

예외 상태:

- `review_required`: 해석이 모호하거나 미지원 조건이 존재함
- `invalid`: 필수값 누락 또는 값 충돌로 계산할 수 없음
- `inactive`: 단종 또는 운영 정책에 의해 추천에서 제외됨

카드 전체 상태와 개별 혜택 규칙 상태를 분리한다. 카드에 검토 대상 혜택이
있더라도 다른 혜택이 정확히 계산 가능하다면 계산 가능한 규칙만 별도로 사용할
수 있도록 한다.

## 정규화 결과 계약

```json
{
  "is_valid": true,
  "parse_status": "review_required",
  "normalized_data": {
    "external_id": "issuer-card-001",
    "issuer": "카드사",
    "provider": "카드사",
    "source_channel": "issuer_site",
    "card_type": "credit",
    "name": "카드명",
    "annual_fee": 10000,
    "previous_month_requirement": 300000,
    "monthly_discount_limit": 15000,
    "benefits": []
  },
  "validation_errors": [],
  "review_reasons": [
    "일 이용횟수 조건은 현재 계산 미지원"
  ]
}
```

`is_valid=true`는 구조적으로 유효하다는 뜻이다. `parse_status=review_required`인
경우 검토 없이 모든 혜택을 추천 계산에 사용해도 된다는 뜻은 아니다.

## 추천 계산 코어 연결

```text
크롤링 데이터
  -> 카드 정규화 및 검증
  -> active 또는 계산 가능한 혜택 규칙 선택
  -> calculate_card_recommendation()
```

추천 계산 코어는 `"카페 10% 할인"`과 같은 문장을 직접 해석하지 않는다.
정규화된 `category="cafe"`, `discount_rate=0.1`만 입력받는다.

잘못되거나 미검증된 데이터가 계산기로 들어왔을 때 임의 기본값으로 정상 결과를
만들지 않도록 입력 경계를 둔다.

## Neo4j 연결

정규화가 완료된 데이터는 다음 노드와 관계로 변환할 수 있다.

```text
(Card)-[:HAS_BENEFIT]->(Benefit)
(Benefit)-[:APPLIES_TO]->(Category)
```

원본 텍스트와 검증 상태는 관계 검색에 사용하는 값과 분리해 보존한다.
`invalid` 데이터는 Neo4j 추천 후보로 활성화하지 않는다.

SQLite가 카드 원본과 정규화 결과의 기준 저장소다. Neo4j에는 SQLite에서
검증된 `active` 카드와 계산 가능한 혜택 규칙만 동기화한다.

## 예정 검증 인터페이스

구현 시 다음과 같은 순수 Python 인터페이스를 사용한다.

```python
result = validate_card_product(card_data)

result.is_valid
result.parse_status
result.errors
result.review_reasons
result.normalized_data
```

추천 계산, 크롤러와 Neo4j 저장 계층이 같은 검증 함수를 재사용하도록 한다.

## 현재 구현 상태

다음 Django 모델과 검증 계층이 구현됐다.

- `CardProduct`
- `BenefitRule`
- `CardImage`
- `CrawlSnapshot`
- `CardBenefitTier`
- `CardServiceLimitTier`
- `validate_card_product()`
- `validate_benefit_rule()`

제휴 카드의 `issuer`와 `provider`를 분리하고, 혜택 원문과 검토 사유를
SQLite에 보존한다. 구조화할 수 없는 혜택이 있으면 `review_required`로 저장한다.

카카오뱅크 HTML 파서는 구현됐지만 공식 자동 수집 정책에 의해 실제 실행은
차단된 상태다. 테스트용 HTML로 파싱과 SQLite 적재 동작만 검증했다.

## 예정 테스트 범위

1. 정상 할인율 카드
2. 정상 정액 할인 카드
3. 필수 필드 누락
4. 음수 연회비 또는 한도
5. 할인율과 정액 할인 동시 입력
6. 0에서 1 범위를 벗어난 할인율
7. 알 수 없는 카테고리
8. 미지원 조건 탐지
9. 원문과 출처 보존
10. 검토 대상 혜택의 추천 계산 유입 차단

## 구현 제외 범위

이 문서를 작성하는 단계에서는 다음 작업을 수행하지 않는다.

- 정규화 Python 코드
- 실제 카드사 크롤러
- Django 모델과 마이그레이션
- Neo4j 적재
- LLM 기반 약관 파싱
- 미지원 거래 조건의 계산 로직
