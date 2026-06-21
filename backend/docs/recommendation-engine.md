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

`review_required`, `invalid`, `inactive` 카드는 추천 후보에서 제외하고 제외
수량을 응답 메타데이터로 반환한다.

카드 상태가 `active`여도 연회비가 없거나 `active` 혜택이 하나도 없으면
`excluded_unready_count`로 제외한다.

```json
{
  "recommendation_source": "sqlite",
  "candidate_count": 0,
  "excluded_review_count": 3,
  "fallback_reason": "no_active_cards"
}
```

mock 카드는 기본 추천에 사용하지 않는다. 로컬 화면 테스트가 필요한 경우 요청에
`allow_mock_fallback=true`를 명시한 경우에만 `mock_fallback`으로 사용한다.

## 지역 적합도

주변 매장 수는 실제 할인액을 변경하지 않는다. 생활권에서 혜택을 사용할
가능성을 나타내는 별도 점수로 계산한다.

```text
store_weight(category) = tanh(store_count / 2)
local_fit_score = 100 × Σ(카테고리 소비 비중 × store_weight)
```

## 콜드스타트

사용자 소비 데이터가 있으면 `source=user`로 계산한다. 데이터가 없으면
초기 사용자군 평균 소비 프로필을 사용하고 `source=cohort_default`,
`is_cold_start=true`를 반환한다.

향후에는 연령대, 직업군, 가구 형태 또는 지역 평균 소비 프로필로 기본값을
세분화한다. 기본값은 실제 사용자 소비로 오해되지 않도록 출처를 함께 반환한다.

## 정렬 기준

1. 전월 실적 충족 여부
2. `estimated_net_value`
3. `local_fit_score`
4. `estimated_gross_benefit`

`seul_score`는 후보 카드 중 최대 순혜택을 100점으로 정규화한 비교용 값이다.
지역 적합도는 금액에 섞지 않고 동률 보조 기준으로 사용한다.

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
