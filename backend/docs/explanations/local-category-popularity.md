# 지역 + 카테고리 기반 인기 카드 로직

## 목적

`지역별 인기 카드`는 단순히 Graph DB 지역 적합도가 높은 카드가 아니라, 현재 지역의 주요 업종과 사용자 행동 로그가 함께 반영된 카드 순위다.

즉 다음을 함께 본다.

```text
현재 지역의 주요 업종
카드가 제공하는 혜택 업종
사용자가 그 카드에 보인 행동
```

## 사용 데이터

- Graph DB 기반 지역 신호
  - `area_id`
  - `graph_matched_categories`
  - `graph_category_shares`
  - `graph_rerank_score`
- Python 추천 코어 산출 결과
  - `seul_score`
  - `estimated_net_value`
- 행동 로그
  - `UserCardEvent.area_id`
  - `UserCardEvent.card_id`
  - `UserCardEvent.event_type`
  - `UserCardEvent.created_at`

## 행동 점수

```text
event_score =
viewed * 1
+ clicked * 3
+ liked * 5
+ applied_for * 10
- dismissed * 2
```

행동 점수는 단순 조회보다 클릭, 좋아요, 신청 의향을 더 강하게 반영한다.

## 지역 카테고리 적합도

```text
category_fit =
sum(area_category_share for card_matched_categories)
```

예를 들어 현재 지역의 업종 비중이 다음과 같다고 가정한다.

```text
cafe = 0.35
dining = 0.28
convenience = 0.18
```

카드가 `cafe`, `dining` 혜택과 매칭되면:

```text
category_fit = 0.35 + 0.28 = 0.63
```

## 최종 점수

```text
local_popularity_score =
event_score * (1 + category_fit)
```

행동 로그가 없는 카드는 `event_score = 0`이므로 최종 인기 점수도 0이다. 이 경우 fallback 점수를 만들지 않는다.

## 정렬 기준

```text
1. local_popularity_score desc
2. graph_rerank_score desc
3. seul_score desc
```

`local_popularity_score`가 가장 우선이다. 동점일 때만 Graph DB 지역 적합도와 Python 추천 코어 점수를 보조 정렬로 사용한다.

## API

```text
POST /api/v1/hyperlocal/area-card-popularity/
```

요청 예시:

```json
{
  "area_id": "geo_37_497_127_027",
  "cards": [
    {
      "card_id": 1,
      "graph_matched_categories": ["cafe", "dining"],
      "graph_category_shares": {
        "cafe": 0.35,
        "dining": 0.28
      },
      "graph_rerank_score": 59.9,
      "seul_score": 78.0
    }
  ]
}
```

응답 예시:

```json
{
  "area_id": "geo_37_497_127_027",
  "event_weights": {
    "viewed": 1,
    "clicked": 3,
    "liked": 5,
    "applied_for": 10,
    "dismissed": -2
  },
  "ranking": [
    {
      "card_id": 1,
      "event_score": 54,
      "category_fit": 0.63,
      "local_popularity_score": 88.02,
      "event_counts": {
        "viewed": 20,
        "clicked": 8,
        "liked": 2,
        "applied_for": 0,
        "dismissed": 0
      },
      "graph_rerank_score": 59.9,
      "seul_score": 78.0,
      "matched_categories": ["cafe", "dining"]
    }
  ]
}
```

## 화면 문구

권장 섹션명:

```text
이 지역 업종에서 반응이 좋은 카드
```

권장 설명:

```text
현재 지역의 주요 업종과 사용자 클릭/좋아요/신청 행동을 함께 반영한 순위입니다.
```

## 주의사항

- 행동 로그가 충분하지 않으면 점수가 0에 가까울 수 있다.
- 시연용 풍성한 순위를 원하면 별도 더미 행동 로그 seed가 필요하다.
- 추천 산출액 자체는 Python 추천 코어가 담당하고, 이 로직은 지역 기반 인기 정렬에만 사용한다.
