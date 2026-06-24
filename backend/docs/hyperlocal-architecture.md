# 하이퍼로컬 아키텍처

## 목적
하이퍼로컬 API는 사용자가 선택한 생활 반경을 분석하고, 추천 엔진에서 사용할 수 있는 인프라 데이터를 반환한다.

## API 엔드포인트

### POST `/api/v1/hyperlocal/simulate/`

입력:

- `spending`, 선택. 카테고리별 월 소비액
- `spending_source`, 선택. 예: `user`, `mydata`, `image_parser`
- `transactions`, 선택. 건당 조건 계산용 거래 목록
- `infrastructure`, 선택. 카테고리별 주변 매장 수와 브랜드 표본
- `area_id`, 선택. Neo4j에 동기화된 생활권 ID. 있으면 그래프 후보 탐색을 먼저 시도
- `previous_month_spending`, 선택. 생략 시 소비 프로필 합계로 추정
- `selected_category`, 선택. `cafe`, `convenience`, `dining`, `delivery`, `mart`, `shopping`
- `owned_card_ids`
- `allow_mock_fallback`, 선택. 로컬 UI 테스트에서만 사용

`spending`이 없으면 추천 코어가 콜드스타트 소비 프로필을 사용한다.

책임:

- 카드 약관 규칙으로 월 예상 총혜택을 계산한다.
- 연회비를 월 단위로 차감해 예상 순혜택을 계산한다.
- 실제 혜택 금액과 분리된 지역 적합도를 계산한다.
- 선택 카테고리와 주변 혜택 대상 브랜드를 추천 순위에 반영한다.
- `selected_category`가 없으면 전체 소비 기반 추천을 반환한다.
- `selected_category`가 있으면 다른 카테고리 혜택을 제외한 카테고리 추천을 반환한다.
- 계산 상세 내역과 소비 데이터 출처를 반환한다.
- 보유 카드는 점수 가산 없이 표시 정보만 반환한다.
- SQLite에서 `active`인 카드만 추천 후보로 사용한다.
- `area_id`가 있으면 Neo4j의 `Area-Store-Category-Card` 관계로 후보를 먼저 좁힌다.
- Neo4j는 후보 생성만 담당하며 월 혜택 정산과 Seul-Score 계산은 Python 추천 코어가 담당한다.
- Neo4j 후보가 없거나 Neo4j가 사용할 수 없으면 SQLite 후보 조회로 fallback한다.
- 추천 후보, 제외 카드 수와 fallback 사유를 메타데이터로 반환한다.

현재 추천 메타데이터:

```json
{
  "recommendation_source": "sqlite",
  "candidate_count": 0,
  "excluded_review_count": 3,
  "excluded_invalid_count": 0,
  "excluded_inactive_count": 0,
  "excluded_unready_count": 0,
  "graph_candidate_count": null,
  "graph_status": "not_requested",
  "graph_fallback_reason": null,
  "fallback_reason": "no_active_cards"
}
```

`graph_status`는 `not_requested`, `matched`, `no_candidates`, `unavailable` 중
하나다. `graph_fallback_reason`은 그래프 후보가 없어 SQLite로 fallback한 경우
`no_graph_candidates`, Neo4j 장애나 미설정으로 SQLite fallback한 경우
`neo4j_unavailable`을 반환한다.

`allow_mock_fallback=true`가 없으면 active 카드가 없는 경우 빈 추천 목록을
반환한다.

### GET `/api/v1/hyperlocal/map-summary/`

입력:
- `lat`
- `lng`
- `radius`, 기본값 `500`

책임:
- Kakao Local category search API를 호출한다.
- 카테고리별 최대 3페이지, 최대 45개 장소를 표본으로 수집한다.
- 카테고리별 전체 검색 수와 실제 표본 수를 구분해 반환한다.
- 장소명을 표준 브랜드명으로 정규화해 브랜드별 개수를 집계한다.
- 지도 렌더링에 필요한 marker 데이터를 반환한다.
- Seul-Score 계산에 필요한 인프라와 브랜드 분포를 반환한다.

인프라 항목 예시:

```json
{
  "key": "cafe",
  "category": "카페",
  "code": "CE7",
  "count": 215,
  "total_count": 215,
  "sample_count": 45,
  "is_sampled": true,
  "merchant_counts": {
    "스타벅스": 5,
    "메가커피": 2,
    "투썸플레이스": 1
  }
}
```

### GET `/api/v1/hyperlocal/weather-curation/`

입력:
- `lat`
- `lng`

책임:
- OpenWeatherMap에서 날씨 데이터를 가져온다.
- 추천 메시지에 활용할 수 있는 날씨 값과 문구 데이터를 반환한다.

## MVP 지도 카테고리

| Internal Key | Label | Kakao Code |
| --- | --- | --- |
| `cafe` | 카페 | CE7 |
| `convenience` | 편의점 | CS2 |
| `mart` | 마트 | MT1 |
| `dining` | 외식 | FD6 |

## 카테고리 확장 규칙
Kakao가 지원한다는 이유만으로 지도 카테고리를 늘리지 않는다.

크롤링한 카드 혜택 규칙이나 대시보드에서 실제로 사용하는 카테고리만 추가한다.

## 외부 API 규칙
외부 API 호출은 service 함수 내부로 격리한다.

추천 점수 계산 로직은 Kakao API나 날씨 API를 직접 호출하지 않는다.
