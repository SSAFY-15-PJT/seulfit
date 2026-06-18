# 추천 엔진

## 현재 Seul-Score의 적합성
현재 Seul-Score 방향은 MVP에 적합하다. 슬픽의 핵심 아이디어인 아래 개념을 잘 반영하기 때문이다.

```text
실질 혜택 = 명목 카드 혜택을 주변에서 실제로 사용할 수 있는 매장 수로 보정한 값
```

현재 사용하는 `tanh(store_count / 2)` 가중치도 적절하다. 주변에 사용 가능한 매장이 생길수록 점수가 빠르게 올라가지만, 매장 수가 충분히 많아진 뒤에는 자연스럽게 포화되기 때문이다.

다만 실제 카드 추천으로 사용하려면 현재 점수만으로는 부족하다. 다음 버전에는 아래 조건이 반드시 포함되어야 한다.
- 전월 실적 조건.
- 월 할인 한도.
- 카테고리별 혜택 규칙.
- 보유 카드 여부.

## MVP 산식

```text
store_weight = tanh(store_count / 2)
category_discount = spending_amount * discount_rate * store_weight
expected_discount = min(sum(category_discount), monthly_discount_limit)
```

사용자가 전월 실적 조건을 충족하지 못한 경우:

```text
expected_discount = 0
eligibility_status = "전월 실적 미충족"
```

## 점수 응답
Seul-Score는 랭킹을 위한 정규화 점수로 사용한다.

사용자에게 보여줄 실제 금액은 `estimated_savings`에 담는다.

MVP 추천 응답 형태:

```json
{
  "id": 1,
  "name": "카드명",
  "issuer": "카드사",
  "image_url": "https://example.com/card.png",
  "focus": ["카페", "편의점"],
  "estimated_savings": 24500,
  "seul_score": 92.5,
  "monthly_discount_limit": 30000,
  "previous_month_requirement": 300000,
  "is_eligible": true,
  "is_owned": true,
  "badge": "보유중인 카드"
}
```

## 입력값

```json
{
  "spending": {
    "cafe": 120000,
    "convenience": 45000,
    "mart": 320000,
    "food": 180000,
    "shopping": 90000,
    "etc": 50000
  },
  "infrastructure": {
    "cafe": 8,
    "convenience": 12,
    "mart": 1,
    "food": 9
  },
  "previous_month_spending": 420000,
  "owned_card_ids": [1, 7, 12]
}
```

## 규칙
- 점수 계산은 결정적으로 동작해야 한다.
- 핵심 점수 계산 함수는 독립적으로 테스트할 수 있어야 한다.
- 점수 계산 로직 내부에서 외부 API를 호출하지 않는다.
- 프론트엔드 표시 형식을 알고리즘에 섞지 않는다. 단, `badge`처럼 API 응답에 필요한 단순 필드는 허용한다.
