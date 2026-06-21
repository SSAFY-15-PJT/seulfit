# 하이퍼로컬 아키텍처

## 목적
하이퍼로컬 API는 사용자가 선택한 생활 반경을 분석하고, 추천 엔진에서 사용할 수 있는 인프라 데이터를 반환한다.

## API 엔드포인트

### POST `/api/v1/hyperlocal/simulate/`

입력:

- `spending`, 선택. 카테고리별 월 소비액
- `spending_source`, 선택. 예: `user`, `mydata`, `image_parser`
- `transactions`, 선택. 건당 조건 계산용 거래 목록
- `infrastructure`, 선택. 카테고리별 주변 매장 수
- `previous_month_spending`
- `owned_card_ids`
- `allow_mock_fallback`, 선택. 로컬 UI 테스트에서만 사용

`spending`이 없으면 추천 코어가 콜드스타트 소비 프로필을 사용한다.

책임:

- 카드 약관 규칙으로 월 예상 총혜택을 계산한다.
- 연회비를 월 단위로 차감해 예상 순혜택을 계산한다.
- 실제 혜택 금액과 분리된 지역 적합도를 계산한다.
- 계산 상세 내역과 소비 데이터 출처를 반환한다.
- 보유 카드는 점수 가산 없이 표시 정보만 반환한다.
- SQLite에서 `active`인 카드만 추천 후보로 사용한다.
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
  "fallback_reason": "no_active_cards"
}
```

`allow_mock_fallback=true`가 없으면 active 카드가 없는 경우 빈 추천 목록을
반환한다.

### GET `/api/v1/hyperlocal/map-summary/`

입력:
- `lat`
- `lng`
- `radius`, 기본값 `500`

책임:
- Kakao Local category search API를 호출한다.
- 카테고리별 매장 수를 집계한다.
- 지도 렌더링에 필요한 marker 데이터를 반환한다.
- Seul-Score 계산에 필요한 인프라 count를 반환한다.

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
| `food` | 음식점 | FD6 |

## 카테고리 확장 규칙
Kakao가 지원한다는 이유만으로 지도 카테고리를 늘리지 않는다.

크롤링한 카드 혜택 규칙이나 대시보드에서 실제로 사용하는 카테고리만 추가한다.

## 외부 API 규칙
외부 API 호출은 service 함수 내부로 격리한다.

추천 점수 계산 로직은 Kakao API나 날씨 API를 직접 호출하지 않는다.
