# 추천 계산 코어 설명

이 문서는 `backend/finance/recommendation.py`에 구현된 Phase 1 규칙 기반 추천
계산과 전체 추천·카테고리 추천 산식을 설명한다.

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

### 기존 MVP 산식과 한계

```text
store_weight = tanh(store_count / 2)
local_fit_score
= 100 × Σ(category_spending_ratio × store_weight)
```

`tanh`는 매장 수 증가 효과를 포화시키는 MVP 휴리스틱이다. 카드사가 공개한
공식이 아니며 향후 실제 사용 또는 방문 데이터로 보정해야 한다.

현재 산식은 `카페`, `편의점`, `마트`, `외식`과 같은 카테고리별 매장 수만
사용한다. 따라서 두 지역의 카테고리별 매장 수가 충분히 많으면
`store_weight`가 모두 1에 가까워지고, 주변 브랜드 구성이 달라도 비슷한
카드가 추천될 수 있다.

### 현재 브랜드 기반 위치 추천 산식

위치별 추천 차이를 설명 가능한 방식으로 만들기 위해 카카오 Local API에서
가져온 장소 이름을 브랜드 단위로 정규화하고, 카드 혜택의 `merchant_scope`와
비교한다.

전체 처리 흐름은 다음과 같다.

```text
1. 선택 위치 주변 장소를 카카오 카테고리 API로 수집
2. 장소 이름을 표준 브랜드명으로 정규화
3. 카드 혜택의 merchant_scope와 주변 브랜드를 매칭
4. 브랜드 접근성과 카테고리 밀집도를 추천 점수에 반영
```

예시는 다음과 같다.

```text
스타벅스 강남R점 -> 스타벅스
GS25 역삼점 -> GS25
씨유 강남점 -> CU
메가MGC커피 선릉점 -> 메가커피
```

카드 혜택 데이터는 다음과 같이 대상 브랜드를 가진다.

```json
{
  "category": "cafe",
  "merchant_scope": ["스타벅스", "커피빈"],
  "discount_type": "rate",
  "discount_rate": 0.1
}
```

#### 카카오 API 페이지네이션

카카오 카테고리 검색 API는 한 번의 요청에서 가까운 장소 일부만 반환한다.
현재 요청 크기가 15개라면 첫 요청만으로는 전체 브랜드 분포를 판단할 수 없다.
MVP에서는 카테고리별 최대 3페이지를 요청해 가까운 장소를 최대 45개까지
표본으로 수집한다.

```text
page 1 -> 가까운 장소 1~15
page 2 -> 가까운 장소 16~30
page 3 -> 가까운 장소 31~45
```

응답의 `meta.is_end`가 참이면 최대 페이지에 도달하기 전이라도 수집을
종료한다. 외부 API 호출량과 응답 지연을 제한하기 위해 무제한으로 페이지를
요청하지 않는다.

지역 인프라 응답에는 표본의 범위를 함께 표시한다.

```json
{
  "category": "cafe",
  "total_count": 200,
  "sample_count": 45,
  "is_sampled": true,
  "merchant_counts": {
    "스타벅스": 7,
    "메가커피": 5,
    "투썸플레이스": 4
  }
}
```

`total_count`는 카카오 API가 알려준 전체 검색 결과 수이고, `sample_count`는
브랜드명을 실제로 확인한 장소 수다. `merchant_counts`는 전체 모집단이 아니라
수집한 표본 기준 값이다.

#### 브랜드 접근성

브랜드 제한이 있는 카드 혜택은 다음과 같이 주변에서 실제로 이용할 수 있는
혜택 대상 브랜드의 비율을 계산한다.

```text
matched_merchant_count
= Σ merchant_counts[merchant]
   for merchant in merchant_scope

merchant_accessibility
= matched_merchant_count / sample_count
```

예를 들어 주변 카페 표본 45개 중 스타벅스 7개와 커피빈 2개가 있고 카드가
두 브랜드에서 할인된다면 `merchant_accessibility`는 `9 / 45 = 0.2`다.

브랜드 제한이 없는 `모든 카페 할인` 혜택에는 특정 브랜드 비율을 적용하지
않고 카테고리 전체 접근성을 사용한다.

#### 카테고리 밀집도

기존 `tanh(store_count / 2)`의 빠른 포화를 줄이기 위해 카테고리 구성비와
로그 스케일 밀집도를 함께 사용한다.

```text
category_share
= category_store_count / total_store_count

density_score
= log(1 + category_store_count)
   / log(1 + 50)

local_accessibility
= 0.6 × category_share
   + 0.4 × density_score
```

`density_score`는 50개 이상에서 1로 제한한다. 고정 기준을 사용하므로 카드가
한 카테고리 혜택만 가지더라도 매장 1개와 20개의 차이를 유지할 수 있다.
모든 매장 수가 0이면 `density_score`와 `local_accessibility`는 0으로 처리한다.

#### 카테고리별 기초 점수

전체 추천에서 지역 정보가 중복 반영되지 않도록 카테고리 혜택 점수와
지역·브랜드 활용도는 별도로 계산한다.

```text
category_benefit_score
= normalized_category_benefit

category_local_brand_score
= 브랜드 제한 혜택이면
   0.625 × merchant_accessibility_score
   + 0.375 × local_accessibility_score

category_local_brand_score
= 브랜드 제한이 없으면
   local_accessibility_score
```

`0.625 / 0.375`는 기존 카테고리 추천의 브랜드 25%, 지역 15% 비율을
합계 40% 안에서 다시 정규화한 값이다.

```text
0.25 / (0.25 + 0.15) = 0.625
0.15 / (0.25 + 0.15) = 0.375
```

각 값은 최종 결합 전에 0~100점으로 변환한다. 모든 가중치는 카드사가 공개한
공식이 아니라 MVP 초기 휴리스틱이며 실제 추천 선택과 이용 데이터가 쌓이면
검증 후 조정한다.

#### 금액 계산과 위치 점수의 분리

브랜드 접근성과 지역 밀집도는 추천 순위에만 사용한다. 주변에 대상 브랜드가
많다는 이유로 카드 약관상 할인금액을 늘리지 않는다.

```text
estimated_gross_benefit
= 카드 약관, 소비액, 거래 조건, 월 한도로 계산

merchant_accessibility
local_accessibility
category_fit_score
= 위치별 추천 순위 보정에만 사용
```

따라서 `estimated_savings`와 `estimated_net_value`는 위치가 달라져도 동일한
소비 입력과 약관 조건이라면 동일하게 유지될 수 있다. 위치에 따라 달라지는
값은 접근성 점수와 최종 추천 순위다.

#### 예외와 fallback

- 카카오 API 호출에 실패하면 기존 카테고리 수 기반 지역 적합도로 fallback한다.
- 일부 페이지만 수집되면 수집한 표본으로 계산하고 `is_sampled=true`를 표시한다.
- `merchant_scope`가 있지만 주변 표본에서 대상 브랜드가 없으면
  `merchant_accessibility=0`으로 처리한다.
- 브랜드명을 정규화할 수 없는 장소는 카테고리 매장 수에는 포함하지만 특정
  브랜드 개수에는 포함하지 않는다.
- 카카오 API에 전용 카테고리가 없는 `delivery`는 지역 브랜드 접근성을
  임의로 만들지 않고 카드 혜택 금액 중심으로 평가한다.
- 주변 브랜드 구성이 비슷한 지역에서는 동일한 추천 결과가 나올 수 있다.
  위치마다 억지로 다른 카드를 노출하는 것은 목표가 아니다.

## 확정 추천 산식

추천 목적에 따라 `전체 추천`과 `카테고리 추천`을 분리한다.

```text
전체 추천
= 내 전체 소비 생활에서 가장 적합한 카드

카테고리 추천
= 선택한 카테고리에서 가장 적합한 카드
```

### 공통 1단계: 사용자 소비 비중

사용자 전체 소비액은 카테고리별 소비액의 합이다.

```text
total_spending
= Σ category_spending

category_spending_ratio
= category_spending / total_spending
```

예를 들어 다음 소비 프로필이 있다.

```text
카페 100,000원
배달 300,000원
마트 100,000원
총소비 500,000원
```

소비 비중은 다음과 같다.

```text
카페 소비 비중 = 100,000 / 500,000 = 0.20
배달 소비 비중 = 300,000 / 500,000 = 0.60
마트 소비 비중 = 100,000 / 500,000 = 0.20
```

`food`와 `dining`이 동시에 있으면 같은 외식 소비를 중복 합산하지 않는다.
전체 소비액이 0원이면 소비 비중을 만들 수 없으므로 콜드스타트 프로필을
사용하거나 소비 적합도를 0점 처리한다.

### 공통 2단계: 카테고리 혜택 잠재액

카드가 실제로 혜택을 제공하는 카테고리만 계산한다.

정률 혜택:

```text
raw_category_benefit
= category_spending × discount_rate
```

정액 혜택:

```text
raw_category_benefit
= discount_amount × estimated_monthly_uses
```

건당 한도와 횟수 조건을 확인할 수 있으면 먼저 적용하고, 카테고리 월 한도를
마지막에 적용한다.

```text
category_benefit_potential
= min(raw_category_benefit, category_monthly_limit)
```

카테고리 한도가 없으면 `raw_category_benefit`을 그대로 사용한다.

예:

```text
카페 소비액 = 100,000원
카페 할인율 = 10%
카페 월 한도 = 8,000원

raw_category_benefit = 100,000 × 0.10 = 10,000원
category_benefit_potential = min(10,000, 8,000) = 8,000원
```

브랜드 전용 혜택은 VLM 월간 리포트만으로 실제 브랜드 소비액을 알 수 없다.
따라서 다음 두 값을 구분한다.

```text
estimated_benefit
= 거래 상세로 확정 가능한 예상 혜택

benefit_potential
= 해당 카테고리 소비가 대상 브랜드에서 발생했다고 가정한 혜택 잠재액
```

브랜드 거래 상세가 없으면 `estimated_benefit`은 0원일 수 있지만,
`benefit_potential`은 카테고리 추천 비교용으로 사용할 수 있다. API와 화면에서는
두 값을 혼동하지 않도록 각각 표시해야 한다.

### 공통 3단계: 카테고리 혜택 점수 정규화

금액을 다른 점수와 결합하기 위해 같은 카테고리 후보 카드 사이에서
0~100점으로 정규화한다.

```text
category_benefit_score(card, category)
= card_category_benefit_potential
   / max_candidate_category_benefit_potential
   × 100
```

예:

```text
카드 A 카페 혜택 잠재액 = 8,000원
카페 후보 중 최대 잠재액 = 10,000원

카드 A 카페 혜택 점수
= 8,000 / 10,000 × 100
= 80점
```

후보 전체의 잠재액이 0원이면 해당 카테고리 혜택 점수는 모두 0점으로 처리한다.

### 공통 4단계: 브랜드 접근성

브랜드 제한 혜택에만 적용한다.

```text
matched_merchant_count
= Σ merchant_counts[merchant]
   for merchant in merchant_scope

merchant_accessibility
= matched_merchant_count / sample_count × 100
```

예:

```text
카카오 카페 표본 = 45개
스타벅스 = 7개
커피빈 = 2개
카드 대상 브랜드 = 스타벅스, 커피빈

matched_merchant_count = 7 + 2 = 9
merchant_accessibility = 9 / 45 × 100 = 20점
```

브랜드명은 비교 전에 표준화한다.

```text
메가MGC커피 -> 메가커피
이디야커피 -> 이디야
씨유 -> CU
이마트 트레이더스 -> 이마트트레이더스
```

표본 수가 0이거나 카카오 API 호출이 실패하면 브랜드 접근성은 `null`로
처리하고 임의로 0점이나 평균값을 만들지 않는다.

### 공통 5단계: 지역 접근성

카테고리 매장 수는 할인금액을 변경하지 않고 해당 혜택을 주변에서 사용할
가능성만 나타낸다.

```text
category_share
= category_store_count / total_store_count

density_score
= min(
     log(1 + category_store_count) / log(1 + 50),
     1
   )

local_accessibility
= 0.6 × category_share
   + 0.4 × density_score

local_accessibility_score
= local_accessibility × 100
```

예:

```text
카페 100개
편의점 30개
외식 200개
마트 5개
수집 카테고리 매장 합계 335개
```

```text
카페 구성비
= 100 / 335
= 0.299

카페 밀집도
= min(log(101) / log(51), 1)
= 1

카페 지역 접근성
= 0.6 × 0.299 + 0.4 × 1
= 0.579
= 57.9점
```

`0.6 / 0.4`와 기준 매장 수 50은 공개된 카드사 공식이 아니다. 상권 내 업종
비중을 절대 매장 수보다 조금 더 우선하도록 정한 MVP 휴리스틱이다.

`total_store_count`는 카카오 API로 수집하는 카페, 편의점, 외식, 마트 등의
합계다. 실제 지역의 모든 사업체 수를 의미하지 않으므로 `category_share`는
절대적인 상권 점유율이 아니라 수집 대상 카테고리 안에서의 상대 비중이다.

카카오 API에 직접 대응하는 지역 정보가 없는 배달은 지역 접근성을 `null`로
처리하고 소비액과 카드 약관 중심으로 평가한다.

## 전체 추천 산식

`selected_category`가 없을 때 사용한다. 첫 화면의 종합 Top 3가 이 모드다.

### 1. 전체 예상 순혜택

카드가 제공하는 모든 카테고리 혜택을 합산한다.

```text
uncapped_gross_benefit
= Σ category_benefit
   for category supported by card

estimated_gross_benefit
= min(uncapped_gross_benefit, card_monthly_discount_limit)

estimated_net_value
= estimated_gross_benefit - annual_fee / 12
```

전월 실적 미충족이면 `estimated_gross_benefit=0`으로 처리한다.

후보 카드 중 최대 순혜택을 기준으로 정규화한다.

```text
net_value_score
= max(estimated_net_value, 0)
   / max_candidate_net_value
   × 100
```

### 2. 소비-혜택 적합도

지역 정보 없이 사용자가 많이 소비하는 카테고리와 카드 혜택이 얼마나
일치하는지만 평가한다.

```text
spending_benefit_fit
= Σ(
     category_spending_ratio
     × card_supports_category
     × category_benefit_score
   )
```

`card_supports_category`는 카드가 해당 카테고리 혜택을 제공하면 1, 아니면
0이다.

중요한 원칙은 카드가 지원하는 카테고리 안에서 소비 비중을 다시 100%로
정규화하지 않는 것이다. 항상 사용자의 전체 소비액 기준 비중을 사용한다.

예:

```text
사용자 소비 비중:
카페 20%, 배달 60%, 마트 20%

카드 A:
카페 혜택 점수 80
배달 혜택 점수 90
마트 혜택 없음

spending_benefit_fit
= 0.20 × 80
   + 0.60 × 90
   + 0.20 × 0
= 16 + 54
= 70점
```

카드가 카페 혜택만 제공한다면 카페 비중 20%만 기여하므로 단일 카테고리
카드가 과대평가되지 않는다.

### 3. 지역·브랜드 활용 가능성

사용자가 많이 소비하는 카테고리에서 카드 혜택을 주변에서 실제로 활용하기
쉬운지를 평가한다.

카테고리별 활용 가능성:

```text
브랜드 제한 혜택:
category_local_brand_score
= 0.625 × merchant_accessibility_score
   + 0.375 × local_accessibility_score

브랜드 제한 없는 혜택:
category_local_brand_score
= local_accessibility_score
```

카드 전체 활용 가능성:

```text
local_brand_fit
= Σ(
     category_spending_ratio
     × card_supports_category
     × category_local_brand_score
   )
```

예:

```text
카페 소비 비중 = 20%
카페 브랜드 접근성 = 20점
카페 지역 접근성 = 57.9점

카페 브랜드 제한 카드의 활용 가능성
= 0.625 × 20 + 0.375 × 57.9
= 34.2점

전체 추천에서 카페 지역 기여도
= 0.20 × 34.2
= 6.84점
```

### 4. 최종 전체 추천 점수

```text
overall_ranking_score
= 0.60 × net_value_score
   + 0.25 × spending_benefit_fit
   + 0.15 × local_brand_fit

ranking_mode = "overall"
ranking_score = overall_ranking_score
seul_score = ranking_score
```

가중치 의미:

- 60%: 실제로 절약 가능한 월 순혜택을 가장 중요하게 평가한다.
- 25%: 사용자가 많이 쓰는 업종과 카드 혜택 구성이 맞는지 평가한다.
- 15%: 해당 위치에서 혜택 매장과 브랜드를 이용하기 쉬운지 보정한다.

지역·브랜드 정보는 `local_brand_fit`에서만 사용한다. 소비-혜택 적합도에는
지역 정보를 넣지 않아 중복 반영을 방지한다.

## 카테고리 추천 산식

`selected_category`가 있을 때 사용한다. 카페, 편의점, 외식, 배달, 마트 등의
탭별 Top 3가 이 모드다.

### 1. 선택 카테고리 소비액 반영

선택 카테고리의 사용자 소비액을 카드 혜택 규칙에 대입한다.

```text
selected_category_benefit_potential
= min(
     selected_category_spending × discount_rate,
     selected_category_monthly_limit
   )
```

따라서 같은 카페 탭에서도 사용자 카페 소비액에 따라 순위가 달라질 수 있다.

예:

```text
카드 A: 카페 10%, 월 최대 5,000원
카드 B: 카페 5%, 월 최대 20,000원
```

카페 소비 30,000원:

```text
카드 A = min(30,000 × 10%, 5,000) = 3,000원
카드 B = min(30,000 × 5%, 20,000) = 1,500원
카드 A 우위
```

카페 소비 200,000원:

```text
카드 A = min(200,000 × 10%, 5,000) = 5,000원
카드 B = min(200,000 × 5%, 20,000) = 10,000원
카드 B 우위
```

### 2. 카테고리 최종 점수

브랜드 제한 혜택:

```text
category_ranking_score
= 0.60 × selected_category_benefit_score
   + 0.25 × merchant_accessibility_score
   + 0.15 × local_accessibility_score
```

브랜드 제한 없는 혜택:

```text
category_ranking_score
= 0.75 × selected_category_benefit_score
   + 0.25 × local_accessibility_score
```

브랜드 제한 혜택이지만 브랜드 표본만 없는 경우:

```text
category_ranking_score
= 0.75 × selected_category_benefit_score
   + 0.25 × local_accessibility_score
```

지역 접근성만 없고 브랜드 표본은 있는 경우:

```text
category_ranking_score
= 0.75 × selected_category_benefit_score
   + 0.25 × merchant_accessibility_score
```

배달처럼 지역·브랜드 접근성을 모두 계산할 수 없는 경우:

```text
category_ranking_score
= selected_category_benefit_score
```

```text
ranking_mode = "category"
ranking_score = category_ranking_score
seul_score = ranking_score
```

카페 탭에서는 카페 소비액과 카페 혜택, 주변 카페 브랜드·매장 수만 사용한다.
배달·마트·외식 소비와 혜택은 카페 Top 3 정렬에 포함하지 않는다.

다만 전월 실적은 카드 전체 혜택의 자격 조건이므로 사용자의 전체 월 소비
합계로 계속 판정한다. 카드 상세에는 전체 예상 순혜택과 다른 카테고리 혜택도
참고 정보로 표시할 수 있다.

## 전체 추천 계산 예시

사용자:

```text
카페 100,000원
배달 300,000원
마트 100,000원
```

카드 A:

```text
카페 혜택 점수 = 80
배달 혜택 점수 = 90
마트 혜택 없음
순혜택 점수 = 85

카페 지역·브랜드 활용도 = 60
배달 지역·브랜드 활용도 = 데이터 없음
```

```text
spending_benefit_fit
= 0.20 × 80 + 0.60 × 90 + 0.20 × 0
= 70
```

지역 데이터가 없는 배달은 전체 지역 활용도 합산에서 제외하고 임의 점수를
부여하지 않는다.

```text
local_brand_fit
= 0.20 × 60
= 12
```

```text
overall_ranking_score
= 0.60 × 85
   + 0.25 × 70
   + 0.15 × 12
= 51 + 17.5 + 1.8
= 70.3점
```

같은 카드라도 카페 탭에서는 배달 혜택을 제외한다.

```text
카페 혜택 점수 = 80
카페 브랜드 접근성 = 40
카페 지역 접근성 = 60

category_ranking_score
= 0.60 × 80 + 0.25 × 40 + 0.15 × 60
= 48 + 10 + 9
= 67점
```

## 구현 상태

2026-06-22 기준 다음 항목이 추천 코어에 반영됐다.

- 전체 추천: 순혜택 60%, 소비-혜택 적합도 25%, 지역·브랜드 활용도 15%
- 소비 비중: 사용자 전체 소비액 기준
- 지역 정보: `local_brand_fit`에 한 번만 반영
- 카테고리 추천: 선택 카테고리 소비액과 혜택·브랜드·지역만 반영
- 브랜드 전용 혜택: 확정 예상 혜택과 혜택 잠재액 분리
- 정액 혜택: 해당 카테고리 소비가 0원이면 예상 혜택도 0원

응답에는 다음 설명용 필드가 포함된다.

```text
category_benefit_score
local_brand_score
spending_benefit_fit
local_brand_fit
ranking_components
```

### 공통 정렬 순서

두 모드 모두 다음 순서를 사용한다.

```text
1. is_eligible
2. is_recommendation_ready
3. ranking_score
4. estimated_net_value
5. estimated_gross_benefit
```

보유 카드 여부는 정렬에 포함하지 않는다.

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
  "category_fit_score": 91.2,
  "selected_category": "cafe",
  "ranking_mode": "category",
  "ranking_score": 77.4,
  "ranking_components": {
    "net_value_score": 88.1,
    "category_fit_score": 77.4,
    "local_fit_score": 82.4,
    "spending_benefit_fit": 0,
    "local_brand_fit": 0
  },
  "category_scores": {
    "cafe": {
      "estimated_benefit": 10000,
      "benefit_potential": 12000,
      "normalized_benefit_score": 100.0,
      "category_benefit_score": 100.0,
      "local_accessibility": 82.5,
      "merchant_accessibility": 20.0,
      "local_brand_score": 43.4,
      "merchant_scope": ["스타벅스", "커피빈"],
      "category_fit_score": 77.4
    }
  },
  "seul_score": 77.4,
  "is_eligible": true,
  "is_owned": true,
  "badge": "보유중인 카드",
  "spending_profile": {
    "source": "user",
    "is_cold_start": false,
    "amounts": {"cafe": 120000}
  },
  "previous_month_spending_profile": {
    "amount": 120000,
    "source": "user",
    "is_estimated": false
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
