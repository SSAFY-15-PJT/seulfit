# Graph DB 추천 활용 구조

이 문서는 현재 백엔드 코드 기준으로 Neo4j Graph DB가 카드 추천에서 어떤 역할을 하는지와 `지역 인기카드`를 행동 로그 기반으로 정렬하는 기준을 설명한다.

## 책임 경계

추천 시스템은 Python 추천 코어와 Graph DB의 역할을 분리한다.

```text
Python 추천 코어
- 카드 약관, 소비액, 전월실적, 월 한도 기반 혜택 계산
- estimated_gross_benefit
- estimated_net_value
- ranking_score
- seul_score

Graph DB
- 지역 기반 카드 후보 생성
- 지역-카드 graph 신호 제공
- 사용자 행동 이벤트 저장
- 행동 로그 기반 인기/개인화 확장
```

중요한 원칙은 다음과 같다.

```text
Graph DB는 예상 혜택 금액을 직접 변경하지 않는다.
estimated_net_value는 항상 Python 추천 코어의 약관 계산 결과로 유지한다.
```

## 현재 추천 요청 흐름

슬세권 분석에서 위치를 확정하면 프론트는 `/api/v1/hyperlocal/simulate/`로 요청한다.

```text
프론트
-> area_id, lat, lng, radius, sync_area, selected_category 전송
-> backend hyperlocal SimulateView
-> simulate_cards()
-> load_recommendation_candidates(area_id)
-> rank_card_recommendations()
-> card_ranking_list 반환
```

관련 코드:

```text
backend/hyperlocal/views.py
- SimulateView.post

backend/hyperlocal/services.py
- simulate_cards

backend/finance/card_catalog.py
- load_recommendation_candidates

backend/finance/recommendation.py
- rank_card_recommendations
- calculate_card_recommendation
```

## 현재 Graph DB 노드와 관계 구조

현재 추천 로직에서 사용하는 Neo4j 구조는 `Category`를 중심으로 지역 상권과 카드 혜택을 연결하는 형태다.

```text
(User)
  ├─[:LIVES_IN]────────────▶ (Area)
  ├─[:OWNS]────────────────▶ (Card)
  ├─[:VIEWED]──────────────▶ (Card)
  ├─[:CLICKED]─────────────▶ (Card)
  ├─[:LIKED]───────────────▶ (Card)
  ├─[:DISMISSED]───────────▶ (Card)
  └─[:APPLIED_FOR]────────▶ (Card)

(Area) ◀─[:LOCATED_IN]─ (Store) ─[:BELONGS_TO]─▶ (Category)

(Card) ─[:HAS_BENEFIT]─▶ (Benefit) ─[:APPLIES_TO]─▶ (Category)
```

### 노드

```text
User
Area
Store
Category
Card
Benefit
```

### 관계

```text
(User)-[:LIVES_IN]->(Area)
(User)-[:OWNS]->(Card)

(User)-[:VIEWED]->(Card)
(User)-[:CLICKED]->(Card)
(User)-[:LIKED]->(Card)
(User)-[:DISMISSED]->(Card)
(User)-[:APPLIED_FOR]->(Card)

(Store)-[:LOCATED_IN]->(Area)
(Store)-[:BELONGS_TO]->(Category)

(Card)-[:HAS_BENEFIT]->(Benefit)
(Benefit)-[:APPLIES_TO]->(Category)
```

### 추천 후보 탐색 경로

카드 추천 후보를 찾을 때 실제로 사용하는 핵심 경로는 다음과 같다.

```text
Area
  <- LOCATED_IN - Store
  - BELONGS_TO -> Category
  <- APPLIES_TO - Benefit
  <- HAS_BENEFIT - Card
```

의미상으로는 다음 흐름이다.

```text
선택한 지역
-> 그 지역 주변 상점
-> 상점들의 업종 카테고리
-> 해당 카테고리에 적용되는 카드 혜택
-> 그 혜택을 가진 카드
```

현재 추천 후보 생성에 직접 사용되는 핵심 관계는 아래 4개다.

```text
(Store)-[:LOCATED_IN]->(Area)
(Store)-[:BELONGS_TO]->(Category)
(Card)-[:HAS_BENEFIT]->(Benefit)
(Benefit)-[:APPLIES_TO]->(Category)
```

사용자 행동 기반 기능과 지역 인기카드 확장에는 아래 관계를 사용한다.

```text
(User)-[:VIEWED]->(Card)
(User)-[:CLICKED]->(Card)
(User)-[:LIKED]->(Card)
(User)-[:APPLIED_FOR]->(Card)
(User)-[:DISMISSED]->(Card)
```

따라서 현재 Graph DB는 카드 점수를 직접 계산하는 저장소가 아니라, `Category`를 연결 허브로 사용해 `지역 상권 구조`와 `카드 혜택 구조`를 이어주는 관계형 후보 생성 계층이다.

## 1. 지역 기반 후보 생성

`area_id`가 있으면 `load_recommendation_candidates(area_id)`는 Neo4j에서 해당 지역과 연결된 카드 후보를 조회한다.

```text
area_id 있음
-> GraphRepository.find_card_candidates_by_area(area_id)
-> Neo4j 후보 카드 조회
-> 후보가 있으면 SQLite CardProduct queryset을 해당 후보로 필터링
-> recommendation_source = "neo4j"
-> graph_status = "matched"
```

후보가 없거나 Neo4j 장애가 있으면 SQLite 전체 후보로 fallback한다.

```text
graph_status = "no_candidates" 또는 "unavailable"
recommendation_source = "sqlite"
graph_fallback_reason = "no_graph_candidates" 또는 "neo4j_unavailable"
```

즉 Neo4j는 운영 DB를 대체하지 않는다. SQLite/Django ORM이 카드 원천 데이터의 기준이고, Neo4j는 후보 생성과 지역 신호 계층이다.

## 2. Graph 신호 부착

Neo4j 후보에서 받은 값은 추천 입력 카드에 graph 신호로 붙는다.

```json
{
  "graph_rerank_score": 52.0,
  "graph_top_category": "cafe",
  "graph_matched_categories": ["cafe", "dining"],
  "graph_category_store_counts": {
    "cafe": 12,
    "dining": 20
  },
  "graph_category_shares": {
    "cafe": 0.3,
    "dining": 0.5
  }
}
```

이 값들은 프론트에도 내려가며, 추천 이유나 지역 관련 설명에 사용할 수 있다.

## 3. Python 추천 코어 계산

Graph DB 후보와 신호가 붙은 뒤 실제 산술식 계산은 Python 추천 코어가 수행한다.

추천 코어가 계산하는 대표 값:

```text
estimated_gross_benefit
estimated_net_value
ranking_score
seul_score
spending_benefit_fit
local_brand_fit
category_fit_score
ranking_components
```

전체 추천 산식:

```text
overall_ranking_score
= 0.60 * net_value_score
  + 0.25 * spending_benefit_fit
  + 0.15 * local_brand_fit
```

카테고리 추천은 `selected_category`가 있을 때 백엔드에서 다시 계산한다.

```text
selected_category 없음 -> ranking_mode = "overall"
selected_category 있음 -> ranking_mode = "category"
```

## 4. Graph rerank의 현재 위치

현재 정렬에서 `graph_rerank_score`는 Python 추천 코어의 `ranking_score`를 대체하지 않는다.

정렬 우선순위는 다음과 같다.

```text
1. is_eligible
2. is_recommendation_ready
3. ranking_score
4. graph_rerank_score
5. local_fit_score
6. estimated_net_value
7. estimated_gross_benefit
```

따라서 Graph 점수는 현재 기준에서 주로 tie-break 성격이다.

```text
1순위: Python 추천 산식 ranking_score
2순위: graph_rerank_score
```

## 5. 사용자 행동 이벤트 저장

카드 상세 조회, 찜, 발급신청 같은 사용자 행동은 백엔드에 저장되고 Graph DB에도 동기화된다.

관련 API:

```text
POST /api/v1/hyperlocal/card-events/
```

저장 흐름:

```text
프론트 openDrawer / toggleFavorite / applyForCard
-> cardEvent API
-> UserCardEvent 저장
-> GraphRepository.create_user_card_event()
-> Neo4j 관계 생성
```

대표 이벤트 타입:

```text
viewed
clicked
liked
applied_for
dismissed
```

이 행동 데이터는 Phase 2 이후 다음 기능의 기반이다.

```text
지역 인기카드
유사 사용자 추천
개인화 추천
행동 기반 graph rerank
```

## 지역 인기카드 기준

`지역 인기카드`는 추천 산식 점수가 높은 카드가 아니라, 현재 위치 추천 결과 안에서 사용자 반응이 좋은 카드 순위로 정의한다.

후보군:

```text
현재 area_id, lat/lng, radius, 소비패턴으로 계산된 card_ranking_list
```

정렬 점수:

```text
local_popularity_score
= viewed_count * 1
  + liked_count * 3
  + applied_for_count * 10
```

정렬 우선순위:

```text
1. local_popularity_score desc
2. applied_for_count desc
3. liked_count desc
4. ranking_score desc
```

이 기준을 쓰면 `지역 인기카드`의 의미가 명확해진다.

```text
추천 코어
-> 이 위치와 소비패턴에서 추천 가능한 카드 후보 산출

행동 로그 / Graph DB
-> 그 후보들 중 실제 사용자 반응이 좋은 순서로 정렬
```

## 기존 지역 카테고리 적합도와의 차이

기존 `local-category-popularity.md`는 다음처럼 지역 카테고리 적합도를 함께 곱하는 방식이었다.

```text
local_popularity_score = event_score * (1 + category_fit)
```

변경 기준에서는 `지역 인기카드`를 더 직관적으로 만들기 위해 카테고리 적합도 가중을 제거하고 행동 점수 중심으로 둔다.

```text
지역 인기카드 = 현재 추천 후보 안에서 사용자 행동 반응이 높은 카드
```

카테고리/지역 적합도는 이미 Python 추천 코어와 Graph 후보 생성 단계에서 반영되므로, 인기 정렬에서 다시 강하게 곱하면 지역 정보가 중복 반영될 수 있다.

## 화면 문구

권장 섹션명:

```text
지역 인기카드
```

권장 설명:

```text
해당 지역 추천 결과 중 사용자 반응이 높은 카드
```

또는:

```text
해당 지역에서 많이 조회되고 찜/발급신청 반응이 높은 카드
```

## 프론트 확인 포인트

추천 요청 후 콘솔에서 다음 값이 확인되면 Graph DB 연동이 반영된 상태다.

```json
{
  "recommendation_source": "neo4j",
  "graph_status": "matched",
  "selected_category": null,
  "ranking_mode": "overall",
  "graph_rerank_score": 59.9
}
```

카테고리 탭을 누르면:

```json
{
  "selected_category": "cafe",
  "ranking_mode": "category"
}
```

## 요약

현재 Graph DB 활용은 다음과 같다.

```text
1. 지역 기반 카드 후보 찾기
2. 지역-카드 graph 신호 제공
3. Python 추천 점수의 보조 정렬 신호 제공
4. 사용자 행동 이벤트 저장
5. 지역 인기카드와 유사 사용자 추천으로 확장
```

추천 시스템의 기준은 다음처럼 유지한다.

```text
추천 후보와 기본 순위:
Python 추천 코어 산술식

지역성과 행동 반응:
Graph DB + 행동로그

예상 혜택 금액:
항상 Python 추천 코어 계산값
```

## Graph DB 사용 이점

Graph DB는 Python 추천 코어를 대체하기 위해 사용하는 것이 아니라, 추천 코어가 계산한 결과에 지역성, 관계성, 행동 데이터를 붙이기 위해 사용한다.

```text
Python 추천 코어 = 정확한 혜택 계산
Graph DB = 관계 기반 후보 탐색과 행동 신호 확장
```

### 1. 지역 기반 추천 후보를 빠르게 좁힐 수 있다

카드는 수십~수백 개가 될 수 있고, 각 카드는 여러 혜택 카테고리와 브랜드 조건을 가진다. 일반 RDB만으로도 조회는 가능하지만, 다음 관계가 많아질수록 조인과 조건이 복잡해진다.

```text
지역 -> 상권 카테고리
지역 -> 브랜드
브랜드 -> 카드 혜택
카드 -> 혜택 카테고리
사용자 -> 행동 이벤트
```

Graph DB를 사용하면 특정 지역과 연결된 카드 후보를 관계 탐색으로 먼저 좁힐 수 있다.

```text
선택 위치
-> 주변 상권/브랜드
-> 해당 브랜드 또는 카테고리에 혜택이 있는 카드
-> 후보 카드
```

서비스 이점:

```text
사용자가 선택한 위치와 무관한 카드를 줄이고,
해당 지역에서 실제로 쓸 가능성이 높은 카드 후보를 먼저 보여줄 수 있다.
```

### 2. 지역성과 카드 혜택의 연결을 설명하기 쉽다

추천 결과를 단순히 "점수가 높아서"라고 설명하면 사용자가 납득하기 어렵다. Graph DB는 추천 결과가 어떤 관계를 통해 나온 것인지 설명하기 좋다.

예:

```text
이 지역에는 카페와 외식 매장이 많음
이 카드는 카페/외식 혜택을 제공함
따라서 이 지역에서 활용 가능성이 높음
```

서비스 이점:

```text
"왜 이 지역에서 이 카드인가?"를 관계 기반으로 설명할 수 있다.
```

발표 포인트:

```text
Graph DB를 통해 추천 결과의 설명 가능성을 높였다.
단순 점수 추천이 아니라 지역-상권-혜택 관계를 기반으로 추천 근거를 제공한다.
```

### 3. 사용자 행동 데이터를 추천에 자연스럽게 확장할 수 있다

카드 추천 서비스에서는 사용자가 어떤 카드를 조회했는지, 찜했는지, 발급신청을 눌렀는지가 중요하다.

Graph DB에서는 이런 행동을 관계로 저장할 수 있다.

```text
User -[VIEWED]-> Card
User -[LIKED]-> Card
User -[APPLIED_FOR]-> Card
User -[SEARCHED_IN]-> Area
Area -[HAS_STORE_CATEGORY]-> Category
Card -[BENEFITS]-> Category
```

서비스 이점:

```text
지역 인기카드
유사 사용자 추천
개인화 추천
최근 관심 지역 기반 추천
```

같은 기능을 RDB만으로 구현할 수도 있지만, 관계가 많아질수록 Graph DB가 더 직관적인 모델이 된다.

### 4. 지역 인기카드를 실제 반응 기반으로 만들 수 있다

기존 추천 점수가 높은 카드와 사용자가 실제로 많이 반응한 카드는 다를 수 있다.

Graph DB와 행동 로그를 사용하면 현재 추천 결과 안에서 사용자 반응이 높은 카드를 따로 정렬할 수 있다.

```text
지역 인기카드
= 현재 위치 추천 후보 중
  조회, 찜, 발급신청 반응이 높은 카드
```

서비스 이점:

```text
추천 코어는 "나에게 유리한 카드"를 계산하고,
지역 인기카드는 "이 지역 사용자들이 실제로 반응한 카드"를 보여준다.
```

발표 포인트:

```text
정확한 혜택 계산과 실제 사용자 반응을 분리해서 보여줌으로써
추천의 신뢰성과 사회적 증거를 함께 제공한다.
```

### 5. 추천 코어의 정확성을 해치지 않는다

Graph DB를 쓴다고 해서 카드 혜택 금액이 임의로 바뀌면 안 된다. 혜택 금액은 카드 약관과 사용자 소비액으로 계산해야 한다.

현재 구조는 이 원칙을 지킨다.

```text
estimated_net_value:
Python 추천 코어가 계산

graph_rerank_score:
지역/관계 기반 보조 신호

local_popularity_score:
행동 기반 인기 정렬 신호
```

서비스 이점:

```text
혜택 계산의 신뢰성은 유지하면서
지역성과 사용자 반응을 추천 경험에 추가할 수 있다.
```

### 6. 향후 개인화 추천으로 확장하기 쉽다

행동 로그가 쌓이면 Graph DB는 유사 사용자 추천으로 확장할 수 있다.

예:

```text
나와 비슷한 소비 카테고리를 가진 사용자
나와 비슷한 지역을 검색한 사용자
나와 같은 카드를 찜한 사용자
그 사용자들이 많이 발급신청한 카드
```

서비스 이점:

```text
초기에는 규칙 기반 추천으로 안정성을 확보하고,
데이터가 쌓이면 유사 사용자/행동 기반 추천으로 고도화할 수 있다.
```

발표 포인트:

```text
Graph DB는 현재 추천 기능뿐 아니라
향후 유사 사용자 추천과 개인화 추천을 위한 확장 기반이다.
```

### 발표용 한 문장 요약

```text
SeulPick은 Python 추천 코어로 카드 혜택을 정확히 계산하고,
Graph DB로 지역-상권-카드-사용자 행동의 관계를 연결해
위치 기반 설명 가능성과 행동 기반 개인화를 확장한다.
```
