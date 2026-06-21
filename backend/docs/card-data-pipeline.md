# 카드 데이터 파이프라인

## 방향
카드 데이터는 실제 카드 상품 페이지 또는 공개 카드 목록 페이지를 크롤링해서 확보한다.

정적 mock 데이터는 개발 초기 fallback 용도로만 사용한다.

## 수집 대상과 하루 목표

초기 수집 채널:

- 신한카드
- KB국민카드
- 삼성카드
- 현대카드
- 카카오뱅크
- 토스뱅크

하루 기준 기본정보, 이미지와 혜택 원문 40~80개 수집을 목표로 한다. 이 중
15~30개를 추천 계산 가능한 상태로 정규화하고, 복잡하거나 불명확한 상품은
`review_required`로 저장한다.

카카오뱅크와 토스뱅크의 제휴 신용카드는 플랫폼과 실제 발급사를 구분한다.
카드 디자인 변형은 상품 수에 중복 포함하지 않는다.

## 저장소

```text
크롤러
  -> Django ORM + SQLite
     카드 상품, 혜택 원문, 정규화 결과, 수집 상태, 이미지 경로
  -> Neo4j 동기화
     검증된 카드, 혜택, 카테고리 관계
  -> Python 추천 계산 코어
```

SQLite를 원본 및 정규화 데이터의 기준 저장소로 사용한다. Neo4j는 원본
저장소가 아니라 추천 후보 관계 탐색을 위한 파생 저장소다.

카드 이미지는 `backend/media/cards/{source_channel}/` 아래에 다운로드하고,
SQLite에는 로컬 경로, 원본 URL, 콘텐츠 타입, 체크섬과 다운로드 상태를 저장한다.

## 필수 정규화 필드

카드 상품:
- `id`
- `issuer`
- `provider`
- `source_channel`
- `card_type`
- `name`
- `image_path`
- `source_image_url`
- `image_content_type`
- `image_checksum`
- `image_download_status`
- `annual_fee`
- `annual_fee_source_url`
- `annual_fee_verified_at`
- `previous_month_requirement`
- `monthly_discount_limit`
- `source_url`

혜택 규칙:
- `card_id`
- `category`
- `discount_type`
- `discount_rate`
- `discount_amount`
- `minimum_transaction_amount`
- `maximum_transaction_amount`
- `per_transaction_limit`
- `daily_benefit_limit`
- `daily_usage_limit`
- `monthly_usage_limit`
- `estimated_monthly_uses`
- `category_monthly_limit`
- `total_monthly_limit`
- `merchant_scope`
- `channel`, `online` 또는 `offline`
- `start_hour`, `end_hour`
- `exclusion_text`
- `condition_text`
- `raw_text`

`estimated_monthly_uses`는 거래 단위 데이터가 없을 때 고정 금액 할인이나
건당 할인 한도를 월 집계 데이터로 근사하기 위한 값이다. 실제 거래 데이터가
들어오면 이 값보다 거래 목록을 우선 사용한다.

카드 전체 통합 할인 한도는 카드 상품의 `monthly_discount_limit`로 정규화한다.
혜택 규칙별 `category_monthly_limit`을 먼저 적용한 다음 카드 전체 한도를 적용한다.

현재 계산 코어가 자동 적용하는 거래 조건은 최소 결제금액, 건당 한도,
월 이용횟수, 카테고리 월 한도와 특정 가맹점 범위다. 가맹점 범위는 거래의
`merchant_name`과 혜택의 `merchant_scope`가 모두 있을 때만 적용한다.
일 이용횟수, 채널 및 제외 조건은 크롤링 시 원문과 구조화 필드로 보존하고
필요한 거래 정보가 확보된 뒤 계산 규칙을 추가한다. 지원하지 않는 조건을
임의로 계산하지 않는다.

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

같은 제휴 카드가 발급사와 플랫폼에서 중복 수집되면 공식 상품 식별자를 우선
사용한다. 식별자가 없으면 `issuer + normalized_name + card_type`을 중복 후보
키로 사용하고 출처별 원문은 모두 보존한다.

크롤링은 채널별로 독립 실행한다. 특정 채널 실패가 전체 수집을 중단하지 않으며,
재실행 시 같은 상품과 이미지를 중복 저장하지 않도록 멱등성을 유지한다.

## 중단 복구

크롤링 진행 상태는 `CrawlJob`과 `CrawlItem`에 저장한다. 카드 한 건을 완료할
때마다 SQLite에 체크포인트를 기록한다.

```text
인터넷 단절 또는 프로세스 종료
  -> 완료된 success 항목 유지
  -> fetching 항목을 retry_pending으로 복구
  -> pending, retry_pending 항목부터 재개
```

연결 오류는 2초, 5초, 15초 간격으로 최대 3회 재시도한다. 403과 429 응답은
해당 수집 채널만 일시 중단하고 다른 채널 작업에는 영향을 주지 않는다.

이미지는 `.part` 파일로 먼저 다운로드하고 콘텐츠 타입, 크기와 빈 응답 여부를
확인한 뒤 최종 경로로 이동한다. 실패한 부분 파일은 삭제한다.

현재 관리 명령:

```text
python manage.py crawl_cards --list-sources
python manage.py crawl_cards --issuer {source_channel}
python manage.py crawl_cards --issuer {source_channel} --resume
python manage.py crawl_cards --issuer {source_channel} --resume --retry-failed
```

현재 6개 채널이 등록되어 있다. 카카오뱅크는 파서와 적재 어댑터가 구현됐고,
나머지 채널은 아직 계획 상태다.

카카오뱅크 어댑터는 파서와 적재 구조까지 구현했지만, 2026-06-20 확인한 공식
`robots.txt`가 일반 크롤러의 `/` 접근을 허용하지 않아 실제 자동 수집은
`paused` 처리한다. 정책 변경이나 공식 사용 허가 전에는 우회 실행하지 않는다.

신한카드는 공식 `robots.txt`가 `/pconts/html/card/` 경로를 허용한다.
공식 메인의 JSON-LD 목록에서 현재 노출 상품을 발견하고, 허용된 상세 페이지와
공식 CDN 이미지 URL만 수집한다.

2026-06-20 제한 수집 결과:

```text
카드 상품: 3개
혜택 규칙: 7개
이미지: 11개
실패 항목: 0개
추천 활성 상태: 0개
검토 필요 상태: 3개
```

연회비가 정적 상세 HTML에 포함되지 않고 실적 구간별 통합 한도가 복잡해,
수집한 카드를 즉시 추천에 사용하지 않고 `review_required`로 유지한다.

공식 출처에서 수동 검증한 연회비는 출처 URL과 검증 시각을 함께 저장한다.
검증된 연회비와 활성 상태는 이후 정적 HTML 재크롤링에서 값이 누락돼도
덮어쓰지 않는다.

Discount Plan+의 카드 전체 통합 한도는 5개 실적 구간으로 정규화됐다.
연회비는 정확한 공식 값이 확보되지 않아 `null`로 저장한다. 연회비가
`null`인 카드는 총혜택은 계산하지만 순혜택을 확정하지 않고 추천 준비 상태를
`false`로 반환한다.

Deep Oil의 카페·편의점 혜택은 `life_service` 공유 그룹으로 정규화됐다.
전월 실적에 따라 생활서비스 이용금액과 할인 한도를 함께 적용한다. 다만
연회비와 특정 가맹점 조건이 아직 검토 대상이므로 추천 후보로 활성화하지 않는다.

모든 신규 채널은 다음 순서로 활성화한다.

```text
robots.txt 및 공개 수집 정책 확인
  -> 허용된 경로만 목록 수집
  -> 제한된 상세 페이지 수집
  -> 이미지 호스트 정책 확인
  -> SQLite 적재
```

## 비용과 운영 원칙

초기 구현은 유료 크롤링 API, 프록시, CAPTCHA 우회 서비스와 LLM API를 사용하지
않는다. 사이트가 자동 수집을 차단하면 우회하지 않고 해당 채널을 중단한다.

로컬 실행에는 별도 서비스 이용료가 없지만 운영 배포 시 서버 네트워크와 이미지
저장 공간 비용이 발생할 수 있다. 공식 사이트의 이용약관과 자동 수집 정책을
확인하고 낮은 요청 빈도를 유지한다.
