# 더미 데이터 설계 계획

이 문서는 시연과 추천 검증을 위한 더미 데이터의 목적, 생성 원칙, 저장 테이블, Graph DB 활용 방식을 정리한다.

## 설계 원칙

더미 데이터는 완전 임의 숫자로 만들지 않는다.

```text
지역 상권 분포
= 카카오 Local API로 수집한 실제 반경 내 업종 표본 기반

사용자 소비/행동 데이터
= 실제 서비스 초기 데이터가 없으므로 통계적 가정을 둔 합성 데이터
```

발표용 설명:

```text
지역 상권 분포는 카카오 Local API에서 수집한 실제 반경 내 업종 데이터를 기반으로 구성했고,
사용자 행동 로그는 초기 서비스 데이터가 없기 때문에 상권 비중에 따라 확률적으로 생성한 시뮬레이션 데이터입니다.
```

## 더미 데이터가 필요한 이유

VLM에서 넘어오는 사용자 소비 내역만으로는 다음 기능을 충분히 검증하기 어렵다.

```text
1. 사용자별 소비 패턴 차이
2. 보유 카드 표시
3. 지역별 추천 결과 차이
4. 지역 인기카드
5. 유사 사용자 추천
6. Graph DB 사용자 행동 관계
```

따라서 다음 데이터가 함께 필요하다.

```text
회원 정보
사용자 소비 프로필
VLM 업로드 리포트
보유 카드
카드 행동 이벤트
지역 상권 통계
Graph DB 노드/관계
```

## Django DB 테이블

### 1. auth_user

Django 기본 사용자 테이블이다.

저장 목적:

```text
로그인/로그아웃
소비 프로필 연결
보유 카드 연결
카드 행동 이벤트 연결
```

필수 필드 예:

```text
id
username
email
password
first_name 또는 profile nickname
```

시연용으로는 8~12명의 사용자를 만든다.

예:

```text
gangnam_cafe_user
jamsil_mart_user
hongdae_light_user
balanced_user
```

### 2. users_userprofile

모델:

```text
users.models.UserProfile
```

역할:

```text
프로필 화면 표시용 사용자 부가 정보
선호 지역
예상 월 소비액
```

주요 필드:

```text
user_id
nickname
preferred_area
monthly_expected_spend
```

더미 의도:

```text
사용자마다 선호 지역을 다르게 주어
지역 기반 추천과 프로필 표시를 자연스럽게 만든다.
```

### 3. users_userconsumptionprofile

모델:

```text
users.models.UserConsumptionProfile
```

역할:

```text
추천 코어에 들어가는 사용자 소비 패턴의 기준 데이터
```

주요 필드:

```text
user_id
source
spending_json
is_cold_start
last_updated_at
```

예:

```json
{
  "cafe": 160000,
  "convenience": 70000,
  "dining": 240000,
  "delivery": 120000,
  "mart": 60000,
  "shopping": 90000,
  "etc": 30000
}
```

추천 코어 활용:

```text
spending_benefit_fit
estimated_gross_benefit
estimated_net_value
category_ranking_score
```

소비 유형은 최소 5개로 나눈다.

```text
카페/외식형
마트/생활형
배달/외식형
편의점/소액결제형
균형형
```

### 4. users_useruploadedreport

모델:

```text
users.models.UserUploadedReport
```

역할:

```text
VLM 이미지 파싱 결과와 업로드 이력 저장
```

주요 필드:

```text
user_id
file_url
file_type
parse_status
parsed_payload
```

더미 의도:

```text
VLM이 실제로 소비 카테고리를 추출한 것처럼 시연
프로필/대시보드에서 소비 내역 근거 제공
```

예:

```json
{
  "vlm_status": "success",
  "source": "gms_gemini",
  "categories": ["cafe", "dining", "mart"],
  "spending": {
    "cafe": 160000,
    "dining": 240000,
    "mart": 60000
  }
}
```

### 5. users_userownedcard

모델:

```text
users.models.UserOwnedCard
```

역할:

```text
사용자가 보유한 카드 저장
추천 결과의 보유 카드 배지 표시
Graph DB의 User - OWNS -> Card 관계 생성
```

주요 필드:

```text
user_id
card_id
```

더미 의도:

```text
사용자별 보유 카드가 다르게 보이게 한다.
유사 사용자 추천에서 보유 카드 관계를 활용할 수 있게 한다.
```

추천 코어 기준:

```text
보유 카드 여부는 현재 점수에 영향을 주지 않는다.
표시와 Graph 관계에만 사용한다.
```

### 6. users_usercardevent

모델:

```text
users.models.UserCardEvent
```

역할:

```text
카드 조회, 찜, 발급신청 등 사용자 행동 로그 저장
지역 인기카드와 Graph DB 행동 관계의 핵심 데이터
```

주요 필드:

```text
user_id
card_id
area_id
event_type
metadata_json
is_demo
graph_sync_status
graph_sync_error
created_at
```

이벤트 타입:

```text
viewed
clicked
liked
applied_for
dismissed
```

지역 인기카드 산식:

```text
local_popularity_score
= viewed_count * 1
  + liked_count * 3
  + applied_for_count * 10
```

정렬 기준:

```text
1. local_popularity_score desc
2. applied_for_count desc
3. liked_count desc
4. ranking_score desc
```

더미 의도:

```text
추천 결과 중 실제 사용자 반응이 높은 카드가 지역 인기카드로 보이게 한다.
```

### 7. finance_cardproduct

모델:

```text
finance.models.CardProduct
```

역할:

```text
추천 후보 카드의 기준 테이블
```

주요 필드:

```text
id
issuer
provider
source_channel
card_type
name
annual_fee
previous_month_requirement
monthly_discount_limit
parse_status
```

더미 데이터에서는 새 카드를 무리하게 만들기보다, 이미 크롤링/정규화된 `parse_status=active` 카드들을 사용한다.

### 8. finance_benefitrule

모델:

```text
finance.models.BenefitRule
```

역할:

```text
카드별 혜택 약관
추천 코어 산술식의 직접 입력
```

주요 필드:

```text
card_id
category
discount_type
discount_rate
discount_amount
category_monthly_limit
merchant_scope
parse_status
```

추천 코어 활용:

```text
category_benefit_potential
estimated_gross_benefit
estimated_net_value
category_ranking_score
```

더미 사용자와 행동로그는 반드시 이 카드/혜택 데이터와 연결되어야 한다.

## 지역 상권 통계 데이터

지역 상권 통계는 별도 Django 모델에 저장하기보다, 현재 구조에서는 다음 두 경로로 활용한다.

```text
1. /hyperlocal/map-summary/
   - 카카오 Local API 기반 infrastructure 반환

2. Graph DB Area/Category/Store 관계
   - sync_area_graph_for_coordinates()
   - collect_area_graph_stores()
```

수집 대상 지역:

```text
강남역/역삼
잠실/송파
홍대/합정
```

수집 카테고리:

```text
cafe
convenience
mart
dining
```

수집 방식:

```text
1. 중심 좌표와 반경 설정
2. 카카오 Local API로 카테고리별 장소 검색
3. total_count, sample_count, merchant_counts 수집
4. category_share 계산
5. Graph DB에 Area, Store, Category 노드와 LOCATED_IN/BELONGS_TO 관계 저장
```

## Graph DB 노드와 관계

Graph DB에는 Django 테이블을 그대로 복제하는 것이 아니라 추천에 필요한 관계를 표현한다. 더미 적재는 현재 코드가 실제로 읽고 쓰는 스키마를 따라야 한다.

### 현재 실제 노드

```text
(:User)
(:Card)
(:Benefit)
(:Category)
(:Area)
(:Store)
```

### 현재 실제 관계

카드/혜택 동기화:

```text
(:Card)-[:HAS_BENEFIT]->(:Benefit)
(:Benefit)-[:APPLIES_TO]->(:Category)
```

지역 상권 동기화:

```text
(:Store)-[:LOCATED_IN]->(:Area)
(:Store)-[:BELONGS_TO]->(:Category)
```

사용자 프로필/보유 카드:

```text
(:User)-[:LIVES_IN]->(:Area)
(:User)-[:OWNS]->(:Card)
```

사용자 행동 이벤트:

```text
(:User)-[:VIEWED]->(:Card)
(:User)-[:CLICKED]->(:Card)
(:User)-[:LIKED]->(:Card)
(:User)-[:DISMISSED]->(:Card)
(:User)-[:APPLIED_FOR]->(:Card)
```

### 현재 추천 후보 탐색 방식

현재 추천 후보 탐색은 `Area -> Category -> Card` 직접 관계를 쓰지 않는다. 다음 간접 경로를 사용한다.

```text
Area <- LOCATED_IN - Store - BELONGS_TO -> Category
Card - HAS_BENEFIT -> Benefit - APPLIES_TO -> Category
```

즉, 현재 코드가 사용하는 Cypher 개념은 다음과 같다.

```cypher
MATCH (a:Area {id: $area_id})<-[:LOCATED_IN]-(s:Store)-[:BELONGS_TO]->(cat:Category)
MATCH (card:Card)-[:HAS_BENEFIT]->(b:Benefit)-[:APPLIES_TO]->(cat)
```

따라서 더미 Graph DB 적재 시 반드시 아래 관계를 만들어야 한다.

```text
Card -> Benefit -> Category
Store -> Area
Store -> Category
User -> Card 행동 관계
User -> Card 보유 관계
```

### 현재 코드에서 이미 사용하는 주요 Graph DB 흐름

```text
CardProduct -> Card 노드 동기화
BenefitRule -> Benefit 노드 동기화
BenefitRule.category -> Category 노드 동기화
Area 주변 상권 -> Area/Store/Category 관계 동기화
UserCardEvent -> User-Card 행동 관계 동기화
UserOwnedCard -> User-Card 보유 관계 동기화
```

관련 코드:

```text
backend/finance/graph_sync.py
- Card, Benefit, Category
- HAS_BENEFIT
- APPLIES_TO

backend/finance/graph_repository.py
- User
- Area
- Store
- LIVES_IN
- OWNS
- VIEWED / CLICKED / LIKED / DISMISSED / APPLIED_FOR
- LOCATED_IN
- BELONGS_TO
```

### 현재 더미 적재에서 만들면 안 되는 관계

아래 관계들은 향후 확장 아이디어지만 현재 코드가 직접 사용하지 않는다.

```text
(:User)-[:SEARCHED_IN]->(:Area)
(:Area)-[:HAS_STORE_CATEGORY]->(:Category)
(:Area)-[:HAS_STORE]->(:Store)
(:Card)-[:BENEFITS]->(:Category)
(:Card)-[:MATCHED_IN]->(:Area)
```

현재 상태에서 이 관계만 만들어도 추천 API는 읽지 않는다. 더미 적재는 반드시 현재 실제 관계를 기준으로 한다.

### 향후 확장 가능 관계

Phase 2 이후 추천 설명이나 Graph ML을 고도화할 때는 아래 관계를 추가할 수 있다.

```text
(:User)-[:SEARCHED_IN]->(:Area)
(:Area)-[:HAS_STORE_CATEGORY]->(:Category)
(:Area)-[:HAS_STORE]->(:Store)
(:Card)-[:BENEFITS]->(:Category)
(:Card)-[:MATCHED_IN]->(:Area)
```

다만 이 관계를 추가하려면 후보 조회 Cypher와 sync 로직도 함께 변경해야 한다.

기존 권장 모델과 현재 실제 모델의 차이는 다음과 같다.

```text
권장/확장 모델:
Area -> Category
Card -> Category

현재 실제 모델:
Area <- Store -> Category <- Benefit <- Card
```

현재 구조는 중간 노드인 `Store`와 `Benefit`을 유지하기 때문에, 장소 표본과 카드 약관 정보를 더 자세히 보존할 수 있다.

## 행동로그 합성 방식

행동로그는 완전 무작위로 만들지 않는다. 지역 상권 통계와 카드 혜택 카테고리를 함께 사용한다.

예:

```text
강남역/역삼에서 cafe, dining 비중이 높음
-> cafe/dining 혜택 카드의 viewed/liked/applied_for 확률 증가

잠실/송파에서 mart, dining 비중이 높음
-> mart/dining 혜택 카드의 viewed/liked/applied_for 확률 증가

홍대/합정에서 cafe, dining, convenience 비중이 높음
-> cafe/dining/convenience 혜택 카드의 viewed/liked 확률 증가
```

이렇게 하면 더미 행동로그도 실제 상권 통계와 연결된 설명을 가질 수 있다.

## 최소 더미 데이터 규모

시연용 최소 규모:

```text
사용자: 8~12명
소비 프로필: 5유형
지역: 3개
보유 카드: 사용자당 1~3개
카드 행동 이벤트: 150~300개
```

지역별 이벤트는 추천 결과 카드에 집중해서 생성한다.

```text
현재 위치 추천 결과 card_ranking_list
-> 그 안의 카드에 viewed/liked/applied_for를 분산 생성
-> 지역 인기카드 순위가 행동 반응 기반으로 형성
```

## 생성 순서

권장 작업 순서:

```text
1. active 카드 데이터 확인
2. 시연 사용자 생성
3. UserConsumptionProfile 생성
4. UserUploadedReport 생성
5. UserOwnedCard 생성
6. 지역별 카카오 Local API 상권 통계 수집
7. Area/Store/Category Graph DB 동기화
8. 추천 결과 card_ranking_list 생성
9. 추천 결과 안의 카드에 UserCardEvent 생성
10. UserCardEvent를 Graph DB에 동기화
```

## 발표용 요약

```text
더미 데이터는 완전 임의로 만들지 않고,
지역 상권 분포는 카카오 Local API 기반 실제 표본을 사용했습니다.

다만 초기 서비스라 실제 사용자 행동 로그가 충분하지 않기 때문에,
사용자 클릭/찜/발급신청 이벤트는 지역 상권 비중과 카드 혜택 카테고리를 반영해
합성 데이터로 생성했습니다.

이를 통해 추천 코어의 소비 기반 산술식과
Graph DB의 지역/행동 관계 추천을 함께 검증할 수 있습니다.
```
