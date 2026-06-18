# 카드 데이터 파이프라인

## 방향
카드 데이터는 실제 카드 상품 페이지 또는 공개 카드 목록 페이지를 크롤링해서 확보한다.

정적 mock 데이터는 개발 초기 fallback 용도로만 사용한다.

## 필수 정규화 필드

카드 상품:
- `id`
- `issuer`
- `name`
- `image_url`
- `annual_fee`
- `previous_month_requirement`
- `monthly_discount_limit`
- `source_url`

혜택 규칙:
- `card_id`
- `category`
- `discount_type`
- `discount_rate`
- `discount_amount`
- `category_monthly_limit`
- `condition_text`
- `raw_text`

## 카테고리 규칙
소비 카테고리를 크롤링 전에 모두 확정하지 않는다.

먼저 카드 혜택 문구를 크롤링한 뒤, 반복적으로 등장하는 혜택 그룹을 내부 카테고리로 매핑한다.

개발자 A가 현재 확정한 초기 카테고리:
- `cafe`
- `convenience`
- `mart`
- `food`
- `shopping`
- `etc`

## 크롤링 경계
크롤러는 데이터를 수집하고 정규화하는 역할만 담당한다.

크롤러가 Seul-Score를 계산하지 않는다.

추천 점수 계산은 `hyperlocal` service 로직 또는 별도 recommendation 모듈에서 처리한다.

## 데이터 품질
크롤링한 카드 혜택은 반드시 `raw_text`를 보존한다.

파싱이 애매한 혜택 문구를 나중에 검토할 수 있어야 하기 때문이다.
