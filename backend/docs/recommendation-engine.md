# 추천 엔진

## 비즈니스 목표

SeulPick은 카드사 수익이나 발급 전환율이 아니라 사용자의 월 예상 순혜택을
최대화한다.

```text
사용자의 소비 패턴과 생활권에서 사용할 수 있는 카드 중,
전월 실적과 할인 한도, 연회비를 반영한 월 예상 순혜택이 가장 큰 카드를
설명 가능한 계산 근거와 함께 추천한다.
```

## Phase 1: 규칙 기반 추천

공개된 카드 상품 정산 규칙과 사용자 소비 데이터를 교차 계산한다.

```text
거래 혜택 = min(거래 금액 × 할인율, 건당 할인 한도)
카테고리 혜택 = min(적격 거래 혜택 합계, 카테고리 월 한도)
월 예상 총혜택 = min(카테고리 혜택 합계, 카드 월 통합 할인 한도)
월 예상 순혜택 = 월 예상 총혜택 - 연회비 / 12
```

전월 실적을 충족하지 못하면 월 예상 총혜택은 0원이다. 연회비는 카드 유지
비용이므로 순혜택에는 계속 반영한다.

## 추천 후보 저장소

추천 API는 Django ORM + SQLite의 `CardProduct`를 기준 후보로 사용한다.
카드와 혜택 규칙이 모두 `active`인 데이터만 계산 코어로 전달한다.

```text
SQLite active 카드
  -> ORM 추천 입력 변환
  -> Python 규칙 기반 계산
  -> 추천 API 응답
```

`area_id`가 있는 요청에서는 Neo4j가 후보 생성 레이어로 먼저 사용된다.

```text
Neo4j Area-Store-Category-Card 후보 조회
  -> SQLite active 카드 매칭
  -> ORM 추천 입력 변환
  -> Python 규칙 기반 계산
  -> 추천 API 응답
```

Neo4j는 최종 혜택 정산이나 Seul-Score 산식을 계산하지 않는다. 전월 실적,
카테고리 한도, 카드 통합 한도, 거래 조건과 연회비 차감은 항상 Python 추천
코어에서 계산한다. Neo4j 후보가 없거나 사용할 수 없으면 SQLite 후보 조회로
fallback한다.

`review_required`, `invalid`, `inactive` 카드는 추천 후보에서 제외하고 제외
수량을 응답 메타데이터로 반환한다.

카드 상태가 `active`여도 연회비가 없거나 `active` 혜택이 하나도 없으면
`excluded_unready_count`로 제외한다.

```json
{
  "recommendation_source": "sqlite",
  "candidate_count": 0,
  "excluded_review_count": 3,
  "graph_candidate_count": null,
  "graph_status": "not_requested",
  "graph_fallback_reason": null,
  "fallback_reason": "no_active_cards"
}
```

mock 카드는 기본 추천에 사용하지 않는다. 로컬 화면 테스트가 필요한 경우 요청에
`allow_mock_fallback=true`를 명시한 경우에만 `mock_fallback`으로 사용한다.

## 지역 적합도

주변 매장 수는 실제 할인액을 변경하지 않는다. 생활권에서 혜택을 사용할
가능성을 나타내는 별도 점수로 계산한다.

```text
category_share = category_store_count / total_store_count
density_score = min(log(1 + category_store_count) / log(1 + 50), 1)
local_accessibility
= 0.6 × category_share + 0.4 × density_score
```

카카오 Local API는 카테고리별 최대 3페이지, 최대 45개 장소를 표본으로
수집한다. 장소명을 표준 브랜드명으로 정규화한 뒤 카드 혜택의
`merchant_scope`와 비교해 `merchant_accessibility`를 계산한다.

```text
merchant_accessibility
= 혜택 대상 브랜드 매장 수 / 수집한 카테고리 장소 수
```

브랜드 접근성과 지역 밀집도는 추천 점수에만 사용하며
`estimated_gross_benefit`과 `estimated_net_value`를 변경하지 않는다.

## 콜드스타트

사용자 소비 데이터가 있으면 `source=user`로 계산한다. 데이터가 없으면
초기 사용자군 평균 소비 프로필을 사용하고 `source=cohort_default`,
`is_cold_start=true`를 반환한다.

`previous_month_spending`이 생략되면 같은 소비 프로필의 카테고리 합계를 추정
전월 실적으로 사용하고 `is_estimated=true`를 반환한다. 사용자가 `0`을
명시하면 추정값으로 대체하지 않는다.

향후에는 연령대, 직업군, 가구 형태 또는 지역 평균 소비 프로필로 기본값을
세분화한다. 기본값은 실제 사용자 소비로 오해되지 않도록 출처를 함께 반환한다.

## 추천 모드와 정렬 기준

### 전체 추천

`selected_category`가 없으면 전체 소비 성향을 사용한다.

```text
overall_ranking_score
= 0.60 × normalized_net_value
   + 0.25 × spending_benefit_fit
   + 0.15 × local_brand_fit
```

`spending_benefit_fit`은 사용자 전체 소비 비중과 카테고리 혜택 점수만
사용한다. `local_brand_fit`은 주변 브랜드와 매장 접근성을 별도로 계산한다.
지역 정보는 두 점수에 중복해서 넣지 않는다.

### 카테고리 추천

`selected_category`가 있으면 선택 카테고리의 소비액, 약관 혜택, 주변 브랜드와
밀집도만 정렬 점수에 사용한다.

```text
category_ranking_score = selected_category_fit_score
```

카페 추천에는 배달·마트·외식 혜택을 넣지 않는다. 전체 예상 순혜택은 카드
상세 참고 정보로 유지하지만 카테고리 Top 3 순위를 바꾸지 않는다.

전월 실적 충족 여부는 카드 전체 자격 조건이므로 전체 월 소비 합계로 계속
판정한다.

### 공통 정렬

1. 전월 실적 충족 여부
2. 추천 계산 가능 여부
3. `ranking_score`
4. `local_fit_score`
5. `estimated_net_value`
6. `estimated_gross_benefit`

`ranking_mode`는 `overall` 또는 `category`이며, `seul_score`는 해당 모드의
`ranking_score`와 같은 값이다.

보유 카드는 점수 가산 없이 `is_owned`와 `badge`만 반환한다.

## 설명 가능성

응답에는 카테고리별 계산 내역, 한도 적용 전 총혜택, 통합 한도, 월 환산
연회비와 소비 데이터 출처를 포함한다.

```json
{
  "estimated_gross_benefit": 18000,
  "monthly_annual_fee": 1250,
  "estimated_net_value": 16750,
  "local_fit_score": 82.4,
  "category_fit_score": 91.2,
  "ranking_mode": "category",
  "ranking_score": 91.2,
  "ranking_components": {
    "net_value_score": 88.1,
    "category_fit_score": 91.2,
    "local_fit_score": 82.4,
    "spending_benefit_fit": 0,
    "local_brand_fit": 0
  },
  "category_scores": {
    "cafe": {
      "benefit_potential": 12000,
      "category_benefit_score": 100.0,
      "merchant_accessibility": 20.0,
      "local_accessibility": 82.5,
      "local_brand_score": 43.4,
      "category_fit_score": 77.4
    }
  },
  "calculation_breakdown": [
    {
      "category": "cafe",
      "spending": 120000,
      "discount_rate": 0.1,
      "raw_benefit": 12000,
      "category_monthly_limit": 10000,
      "final_benefit": 10000,
      "calculation_mode": "aggregate_estimate"
    }
  ]
}
```

특정 가맹점 전용 혜택은 거래의 `merchant_name`을 정규화한 뒤
`merchant_scope` 항목과 비교한다. 예를 들어 `스타벅스 강남역점`은
`스타벅스` 범위에 포함된다. 거래 상세가 없으면 과대 추정을 막기 위해 해당
혜택을 0원 처리하고 `calculation_mode=merchant_scope_unavailable`을 반환한다.

## Phase 2: Graph 재정렬

```text
Neo4j 후보 생성
  -> Python 약관 계산 및 상위 후보 선정
  -> GDS 유사 사용자 신호
  -> 제한된 가중치로 후보 재정렬
```

클릭, 상세 조회, 선호, 보유 카드와 발급 전환 데이터가 없을 때는 GDS 점수를
사용하지 않는다. Phase 1의 설명 가능한 순혜택 계산이 항상 기준선이다.
