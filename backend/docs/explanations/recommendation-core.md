# 추천 계산 코어 설명

이 문서는 `backend/finance/recommendation.py`에 구현된 Phase 1 규칙 기반 추천
계산을 설명한다.

## 목적함수

SeulPick의 비즈니스 목표는 사용자의 설명 가능한 월 예상 순혜택을 최대화하는
것이다.

```text
monthly_net_value = monthly_gross_benefit - annual_fee / 12
```

카드사의 마진, 광고비 또는 발급 전환율은 현재 목적함수에 포함하지 않는다.
보유 카드 여부도 점수에 영향을 주지 않는다.

## 입력 데이터

계산 코어는 외부 API나 데이터베이스를 직접 호출하지 않는다.

```json
{
  "card": {
    "id": 1,
    "annual_fee": 15000,
    "previous_month_requirement": 300000,
    "monthly_discount_limit": 30000,
    "benefits": [
      {
        "category": "cafe",
        "discount_type": "rate",
        "discount_rate": 0.1,
        "minimum_transaction_amount": 5000,
        "per_transaction_limit": 3000,
        "monthly_usage_limit": 5,
        "category_monthly_limit": 10000
      }
    ]
  },
  "spending": {"cafe": 120000, "food": 180000},
  "transactions": [
    {
      "category": "cafe",
      "merchant_name": "스타벅스 강남역점",
      "amount": 6500
    }
  ],
  "infrastructure": {"cafe": 8, "food": 9},
  "previous_month_spending": 420000,
  "owned_card_ids": [1, 7]
}
```

`transactions`는 선택 입력이다. 거래 목록이 있으면 건당 조건을 계산하고,
없으면 카테고리별 월 소비 합계로 추정한다.

실제 API에서는 `CardProduct`, `BenefitRule`, `CardBenefitTier`와 대표
`CardImage`를 ORM 어댑터가 위 입력 구조로 변환한다. 추천 계산 코어는 Django
모델을 직접 조회하지 않으므로 순수 함수 테스트 구조를 유지한다.

## 소비 프로필과 콜드스타트

사용자 소비 데이터가 있으면 `source=user`, `is_cold_start=false`로 처리한다.
소비 데이터가 없으면 `DEFAULT_COHORT_SPENDING` 또는 호출자가 전달한
`fallback_spending`을 사용하고 `source=cohort_default`,
`is_cold_start=true`로 표시한다.

콜드스타트 결과는 개인의 실제 소비가 아닌 임시 추정치다. 향후 사용자군과
지역 평균 데이터가 확보되면 기본 프로필을 세분화한다.

## 거래별 혜택

거래 데이터가 있는 경우 최소 결제금액을 충족한 거래만 계산한다.

```text
rate 혜택 = min(transaction_amount × discount_rate, per_transaction_limit)
amount 혜택 = min(discount_amount, per_transaction_limit)
```

`daily_benefit_limit`이 있으면 `transaction_date`별 혜택을 합산한 뒤 일
한도를 적용한다. 같은 `benefit_group`의 여러 카테고리는 일 한도를 공유한다.
거래일자가 없으면 일 한도를 검증할 수 없으므로 해당 혜택은 계산에서 제외한다.

혜택의 `channel`이 `online` 또는 `offline`이면 거래 데이터의 `channel`과
일치하는 거래만 계산한다. 채널 정보가 없으면 채널 전용 혜택을 0원 처리한다.

`start_hour`와 `end_hour`가 있으면 거래의 `transaction_time`을 이용해
`start_hour <= 거래시각 < end_hour`인 거래만 계산한다. `daily_usage_limit`과
`monthly_usage_limit`은 거래일자별 횟수 제한을 적용한 뒤 월 횟수를 제한한다.

`monthly_usage_limit`이 있으면 적격 거래 중 지정 횟수까지만 계산한다.

거래 데이터가 없으면 다음처럼 월 집계액을 사용한다.

```text
rate 혜택 = category_spending × discount_rate
```

건당 한도가 있는 경우 `estimated_monthly_uses`로 최대 할인액을 근사한다.
이 결과의 `calculation_mode`는 `aggregate_estimate`이며 거래 원장 기반 결과보다
정확도가 낮다.

### 가맹점 범위

혜택에 `merchant_scope`가 있으면 거래의 `merchant_name`을 정규화해 대상
가맹점 여부를 확인한다. 공백, 기호와 영문 대소문자는 비교에서 제외한다.

```text
merchant_scope = ["스타벅스", "이디야"]
merchant_name = "스타벅스 강남역점"
결과 = 대상 거래
```

가맹점 범위가 있는 혜택은 카테고리 집계 소비액으로 대체 계산하지 않는다.
거래 상세가 없으면 혜택을 0원으로 처리하고 다음 값을 반환한다.

```json
{
  "calculation_mode": "merchant_scope_unavailable",
  "matched_transaction_count": 0,
  "excluded_transaction_count": 0,
  "exclusion_reason": "가맹점명이 포함된 거래 데이터가 필요함"
}
```

## 카테고리 한도와 통합 한도

```text
category_benefit
= min(raw_category_benefit, category_monthly_limit)

uncapped_gross_benefit
= sum(category_benefit)

estimated_gross_benefit
= min(uncapped_gross_benefit, monthly_discount_limit)
```

카테고리별 한도를 먼저 적용하고 카드 전체 통합 한도를 마지막에 적용한다.

## 전월 실적

```text
is_eligible
= previous_month_spending >= previous_month_requirement
```

미충족 시 `estimated_gross_benefit=0`과
`eligibility_status="전월 실적 미충족"`을 반환한다.

## 연회비와 순혜택

```text
monthly_annual_fee = round(annual_fee / 12)
estimated_net_value = estimated_gross_benefit - monthly_annual_fee
```

현재는 대표 연회비 한 개를 사용한다. 국내전용, 해외겸용 등 유형이 여러 개면
사용자가 선택한 발급 유형에 맞는 값을 입력해야 한다.

연회비가 확인되지 않은 경우에는 다음처럼 처리한다.

```text
annual_fee = null
monthly_annual_fee = null
estimated_net_value = null
is_recommendation_ready = false
```

연회비 미확인 카드는 예상 총혜택은 보여줄 수 있지만 순혜택 기반 추천 순위에는
포함하지 않는다.

## 실적 구간별 통합 한도

`benefit_tiers`가 있으면 전월 실적에 맞는 `card_total` 구간을 선택한다.

```text
minimum_spending <= previous_month_spending < maximum_spending
```

선택된 구간의 `monthly_discount_limit`을 카드 전체 통합 한도로 사용한다.
구간이 없으면 카드의 단일 `monthly_discount_limit` 값을 사용한다.

## 공유 서비스 한도

여러 카테고리가 하나의 서비스 한도를 공유하면 혜택 규칙의 `benefit_group`과
`service_limit_tiers`를 사용한다.

```text
카페 혜택.benefit_group = life_service
편의점 혜택.benefit_group = life_service
```

전월 실적에 맞는 서비스 구간을 선택하고 그룹 혜택 합계에 한도를 적용한다.

```text
전월 30만~70만원
생활서비스 대상 소비 한도 = 15만원
할인율 = 5%
생활서비스 할인 한도 = 7,500원
```

카페와 편의점에서 각각 10만원을 소비해 명목 할인이 1만원이어도 최종 그룹
혜택은 7,500원으로 제한된다.

카드 전체 전월 실적은 충족했더라도 특정 서비스의 최소 실적 구간을 충족하지
못할 수 있다. 해당 서비스에 구간 데이터가 존재하지만 일치하는 구간이 없으면
혜택을 0원으로 처리한다.

```text
카드 전체 조건: 전월 30만원
마트 서비스 조건: 전월 50만원
사용자 전월 실적: 40만원
마트 서비스 혜택: 0원
```

## 지역 적합도

주변 매장 수는 실제 혜택 금액에 곱하지 않는다.

```text
store_weight = tanh(store_count / 2)
local_fit_score
= 100 × Σ(category_spending_ratio × store_weight)
```

`tanh`는 매장 수 증가 효과를 포화시키는 MVP 휴리스틱이다. 카드사가 공개한
공식이 아니며 향후 실제 사용 또는 방문 데이터로 보정해야 한다.

## Seul-Score와 정렬

```text
seul_score
= max(estimated_net_value, 0) / max_candidate_net_value × 100
```

최종 정렬 순서는 다음과 같다.

```text
1. is_eligible
2. estimated_net_value
3. local_fit_score
4. estimated_gross_benefit
```

지역 적합도가 실제 금액보다 먼저 순위를 뒤집지 않도록 순혜택을 우선한다.

## 보유 카드

보유 여부는 표시 전용이며 점수와 정렬 키에 들어가지 않는다.

```text
is_owned = card.id in owned_card_ids
badge = "보유중인 카드"
```

## 응답 예시

```json
{
  "estimated_savings": 18000,
  "estimated_gross_benefit": 18000,
  "uncapped_gross_benefit": 22000,
  "applied_total_monthly_limit": 18000,
  "annual_fee": 15000,
  "monthly_annual_fee": 1250,
  "estimated_net_value": 16750,
  "local_fit_score": 82.4,
  "seul_score": 100.0,
  "is_eligible": true,
  "is_owned": true,
  "badge": "보유중인 카드",
  "spending_profile": {
    "source": "user",
    "is_cold_start": false,
    "amounts": {"cafe": 120000}
  },
  "calculation_breakdown": []
}
```

`estimated_savings`는 기존 API 호환을 위해 유지하며
`estimated_gross_benefit`과 같은 값이다.

## Graph ML 고도화 경계

Neo4j GDS 재정렬은 추천 노출, 클릭, 상세 조회, 선호, 보유 카드, 발급 전환과
같은 행동 데이터가 쌓인 뒤 별도 단계로 추가한다.

```text
Neo4j 관계 기반 후보 생성
  -> Python 규칙 엔진으로 순혜택 계산
  -> 상위 후보 추출
  -> GDS 유사도 신호로 제한적 재정렬
```

GDS 점수는 예상 혜택 금액을 변경하지 않는다. `estimated_net_value`는 항상
약관 계산 결과로 유지하고, ML 신호는 별도의 `graph_similarity_score`와
재정렬 사유로 노출한다.
