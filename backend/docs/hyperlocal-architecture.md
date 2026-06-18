# 하이퍼로컬 아키텍처

## 목적
하이퍼로컬 API는 사용자가 선택한 생활 반경을 분석하고, 추천 엔진에서 사용할 수 있는 인프라 데이터를 반환한다.

## API 엔드포인트

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
