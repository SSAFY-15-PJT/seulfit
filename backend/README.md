# 개발자 A 백엔드 인계사항

이 문서는 `feat/developer-a-backend` 브랜치에서 구현한 개발자 A 영역의 현재 상태와
실행 방법을 정리합니다. 백엔드 구현과 API 계약은 `backend/`를 기준으로 합니다.

## 담당 범위

- Kakao Local API 기반 하이퍼로컬 인프라 분석
- 카드 데이터 수집, 정규화, 검증 및 활성화
- Django ORM + SQLite 카드 운영 데이터
- Neo4j 추천 그래프 데이터 동기화
- 규칙 기반 카드 추천 및 Seul-Score 계산
- 프론트 지도 선택 결과와 추천 API 연결

## 구현 완료 사항

- 반경 500m 내 카페, 편의점, 마트, 음식점 조회
- 카테고리별 매장 수와 지도 마커 반환
- 카드 수집 작업의 재시도, 체크포인트, 중단 복구
- 카드 기본 정보, 이미지, 혜택 규칙 정규화
- 전월 실적, 카테고리 한도, 통합 한도, 연회비 반영
- 예상 총혜택, 예상 순혜택, 지역 적합도, Seul-Score 계산
- 보유 카드에 `is_owned`와 `보유중인 카드` 배지 표시
- 소비 데이터가 없는 사용자의 콜드 스타트 처리
- Neo4j `Card-Benefit-Category` 그래프 동기화
- 지도 위치 선택 후 추천 API 호출과 대시보드 이동

2026년 6월 21일 로컬 SQLite 기준:

| 항목 | 수량 |
| --- | ---: |
| 전체 카드 | 77 |
| 추천 활성 카드 | 35 |
| 활성 신용카드 | 26 |
| 활성 체크카드 | 9 |
| 전체 혜택 규칙 | 211 |
| Neo4j 동기화 대상 혜택 | 116 |
| 카드 이미지 레코드 | 112 |

`db.sqlite3`와 다운로드한 카드 이미지는 Git에 포함하지 않습니다. 팀원 환경의 실제
수량은 수집 및 정규화 실행 결과에 따라 달라질 수 있습니다.

## 남은 작업

- OpenWeatherMap 실제 API 연동
  - 현재 `/weather-curation/`은 고정 mock 응답입니다.
- Neo4j `User`, `Area`, `Store` 노드와 관계 확장
- Neo4j 조회 결과를 추천 후보 선정 단계에 적용
- 사용자 행동 데이터 축적 후 GDS 기반 Phase 2 재정렬
- 개발자 B의 VLM 소비 데이터와 추천 API 연결
- 체크카드와 배달 혜택 카드 데이터 확충
- 위치 변화에 따른 지역 적합도와 순위 변화를 대시보드에서 명확하게 표시

## 디렉터리

```text
backend/
  finance/
    adapters/            카드사 및 카드고릴라 수집 어댑터
    management/commands/ 수집, 검증, 활성화, Neo4j 명령
    models.py             카드 운영 DB 모델
    recommendation.py     규칙 기반 추천 계산
    graph_sync.py         Neo4j 동기화
  hyperlocal/
    services.py           지도 조회 및 추천 서비스
    views.py              하이퍼로컬 API
  users/
    models.py             프로필, 소비 정보, 보유 카드
  docs/
    plans/                작업 계획과 진행 결과
    explanations/         계산식 및 데이터 구조 설명
```

기준 문서:

- `docs/developer-a.md`
- `docs/hyperlocal-architecture.md`
- `docs/recommendation-engine.md`
- `docs/card-data-pipeline.md`
- `docs/graphdb-neo4j-plan.md`
- `docs/explanations/recommendation-core.md`
- `docs/explanations/main-db-normalization-schema.md`

## 백엔드 실행

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_categories
python manage.py runserver 8001
```

PowerShell에서는 다음 명령으로 가상환경을 활성화합니다.

```powershell
.\.venv\Scripts\Activate.ps1
```

`backend/.env` 설정:

```dotenv
KAKAO_REST_API_KEY=your-kakao-rest-api-key
DJANGO_SECRET_KEY=replace-this-for-local-development
NEO4J_HTTP_URI=http://localhost:7474
NEO4J_DATABASE=neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-local-neo4j-password
```

API 키와 비밀번호는 Git에 커밋하지 않습니다.

## 프론트 연결

`frontend/.env.local`:

```dotenv
VITE_KAKAO_JAVASCRIPT_KEY=your-kakao-javascript-key
VITE_API_BASE_URL=http://localhost:8001/api/v1
```

실행:

```bash
cd frontend
npm install
npm run dev
```

지도에서 위치를 선택하면 `map-summary` 결과의 인프라 수를 `simulate` API에 전달하고,
결과를 `localStorage`의 `seulpick:last-simulation`에 저장한 뒤 대시보드로 이동합니다.

## 주요 API

| Method | Endpoint | 역할 |
| --- | --- | --- |
| GET | `/api/v1/hyperlocal/map-summary/` | 위치 반경 내 인프라 조회 |
| POST | `/api/v1/hyperlocal/simulate/` | 카드 추천 및 Seul-Score 계산 |
| GET | `/api/v1/hyperlocal/weather-curation/` | 날씨 큐레이션, 현재 mock |
| POST | `/api/v1/hyperlocal/parse-image/` | VLM 연결 진입점, 현재 mock |
| GET | `/api/v1/finance/cards/` | 카드 목록 조회 |
| GET/POST | `/api/v1/users/profile/` | 사용자 프로필 조회 및 저장 |
| POST | `/api/v1/users/owned-cards/` | 보유 카드 저장 |
| POST | `/api/v1/users/consumption-profile/` | 소비 프로필 저장 |
| POST | `/api/v1/users/reports/` | VLM 분석 결과 연결용 저장 |

추천 요청 예시:

```json
{
  "spending": {
    "cafe": 120000,
    "convenience": 45000,
    "mart": 320000,
    "dining": 130000,
    "delivery": 50000
  },
  "infrastructure": {
    "cafe": 12,
    "convenience": 8,
    "mart": 2,
    "dining": 15,
    "delivery": 0
  },
  "previous_month_spending": 500000,
  "owned_card_ids": [1, 3]
}
```

`spending`이 없으면 기본 소비 프로필을 사용하고 응답에 콜드 스타트 여부와 데이터
출처를 포함합니다.

## 카드 데이터 파이프라인

구현된 수집 어댑터:

- 카드고릴라
- 신한카드
- 현대카드
- 우리카드
- 카카오뱅크
- 토스뱅크

KB국민카드와 삼성카드는 소스만 등록되어 있고 어댑터는 아직 구현되지 않았습니다.

```bash
python manage.py crawl_cards --list-sources
python manage.py crawl_cards --issuer card_gorilla
python manage.py crawl_cards --issuer card_gorilla --resume --retry-failed
python manage.py normalize_card_gorilla
python manage.py activate_card_gorilla
python manage.py activate_card_gorilla --apply
python manage.py validate_cards
```

추천에는 `parse_status=active`이며 계산 가능한 혜택이 있는 카드만 들어갑니다.
검증이 부족한 카드는 `review_required` 상태로 유지합니다.

## Neo4j

현재 구현된 그래프:

```text
(Card)-[:HAS_BENEFIT]->(Benefit)-[:APPLIES_TO]->(Category)
```

SQLite가 기준 저장소이며 Neo4j는 활성 카드와 혜택 관계를 복제한 파생 저장소입니다.

```bash
python manage.py sync_cards_to_neo4j --dry-run
python manage.py sync_cards_to_neo4j
```

동기화 명령은 `parse_status=active`인 카드와 활성 혜택만 대상으로 하며, 재실행해도
중복 노드가 생성되지 않도록 `MERGE`를 사용합니다.

## 추천 로직

현재 구현은 머신러닝 모델이 아닌 Phase 1 규칙 기반 추천 엔진입니다. 공개된 카드
혜택 조건과 사용자 소비액을 교차 계산하기 때문에 추천 금액의 근거를 응답으로
설명할 수 있습니다.

비즈니스 목표는 카드사의 발급 전환이나 마진을 높이는 것이 아니라 다음 값을
기준으로 사용자에게 실질적으로 유리한 카드를 찾는 것입니다.

```text
월 예상 순혜택 = 월 예상 총혜택 - 연회비 / 12
```

### 입력값

| 입력 | 의미 |
| --- | --- |
| `cards` | 활성 카드와 카드별 혜택 조건 |
| `spending` | 카페, 편의점, 마트, 외식, 배달 등 월 소비액 |
| `transactions` | 가맹점명, 금액, 날짜, 시간, 온·오프라인 채널 |
| `infrastructure` | 선택 위치 반경 내 카테고리별 매장 수 |
| `previous_month_spending` | 전월 실적 조건 판정 금액 |
| `owned_card_ids` | 보유 카드 표시 대상 |

`transactions`는 선택 입력입니다. 거래 내역이 있으면 건별 최소 결제 금액, 건당
한도, 이용 횟수, 시간대, 채널 및 특정 가맹점 조건을 적용합니다. 거래 내역이
없으면 카테고리별 월 소비액을 사용해 예상 혜택을 계산합니다.

`spending`이 없으면 기본 소비 프로필을 사용하고 `is_cold_start=true`,
`source=cohort_default`를 반환합니다.

### 계산 순서

1. 전월 실적 충족 여부를 판정합니다.
2. 각 혜택 규칙에 적격한 거래 또는 카테고리 소비액을 선택합니다.
3. 할인율 또는 정액 할인과 건당 한도를 적용합니다.
4. 카테고리별 월 한도를 적용합니다.
5. 같은 `benefit_group`의 공유 서비스 한도를 적용합니다.
6. 카드 전체 월 통합 할인 한도를 적용합니다.
7. 연회비를 12개월로 나눠 예상 총혜택에서 차감합니다.
8. 주변 인프라를 이용해 지역 적합도를 별도로 계산합니다.
9. 순혜택과 지역 적합도를 정규화해 최종 추천 점수를 계산합니다.

핵심 혜택 계산식:

```text
비율 혜택 = 거래 금액 × 할인율
건별 최종 혜택 = min(비율 또는 정액 혜택, 건당 한도)
카테고리 혜택 = min(적격 혜택 합계, 카테고리 월 한도)
월 예상 총혜택 = min(카테고리 혜택 합계, 카드 월 통합 한도)
월 예상 순혜택 = 월 예상 총혜택 - round(연회비 / 12)
```

전월 실적이 부족하면 `estimated_gross_benefit`을 0으로 처리합니다. 연회비가
확인되지 않은 카드는 총혜택을 계산할 수 있어도 순혜택 기반 추천에는 포함하지
않으며 `is_recommendation_ready=false`를 반환합니다.

### 지역 적합도

주변 매장 수는 할인 금액에 직접 곱하지 않고 별도의 지역 적합도에만 사용합니다.

```text
store_weight = tanh(store_count / 2)
local_fit_score
  = 100 × Σ(카테고리 소비 비중 × store_weight)
```

`tanh`를 사용해 매장이 몇 개 이상 존재할 때 매장 수 증가 효과가 과도하게
커지지 않도록 포화시킵니다. 이 값은 카드사가 공개한 공식이 아니라 SeulPick의
MVP 지역 적합도 휴리스틱입니다.

따라서 위치가 달라져도 소비액이 같으면 `estimated_savings`와
`estimated_net_value`는 동일할 수 있습니다. 위치 변화는 `local_fit_score`,
`ranking_score`, 최종 순위에 영향을 줍니다.

### Seul-Score와 정렬

추천 가능한 카드 후보 안에서 순혜택과 지역 적합도를 각각 0~100으로 정규화합니다.

```text
net_value_score
  = max(estimated_net_value, 0) / 후보 중 최대 순혜택 × 100

normalized_local_fit
  = local_fit_score / 후보 중 최대 지역 적합도 × 100

ranking_score
  = net_value_score × 0.6 + normalized_local_fit × 0.4

seul_score = ranking_score
```

최종 정렬 키는 다음 순서로 적용됩니다.

```text
1. 전월 실적 충족 여부
2. 추천 계산 준비 완료 여부
3. ranking_score
4. local_fit_score
5. estimated_net_value
6. estimated_gross_benefit
```

같은 API 호출의 후보 카드끼리 상대 평가하므로 카드 데이터나 후보군이 바뀌면 같은
카드의 Seul-Score도 달라질 수 있습니다.

### 보유 카드

보유 카드 여부는 추천 가산점으로 사용하지 않습니다.

```json
{
  "is_owned": true,
  "badge": "보유중인 카드"
}
```

보유 카드가 원래 계산 결과에서 상위권에 포함된 경우에만 동일한 순위를 유지한 채
배지를 표시합니다.

### 주요 응답 필드

| 필드 | 의미 |
| --- | --- |
| `estimated_savings` | `estimated_gross_benefit`과 동일한 월 예상 총혜택 |
| `estimated_gross_benefit` | 한도를 모두 적용한 월 예상 혜택 |
| `monthly_annual_fee` | 월 단위로 환산한 연회비 |
| `estimated_net_value` | 연회비를 차감한 월 예상 순혜택 |
| `local_fit_score` | 선택 위치와 소비 패턴의 적합도 |
| `ranking_score` | 순혜택 60%, 지역 적합도 40%의 최종 점수 |
| `seul_score` | 현재 `ranking_score`와 동일 |
| `is_eligible` | 전월 실적 충족 여부 |
| `is_recommendation_ready` | 순혜택 기반 추천 가능 여부 |
| `calculation_breakdown` | 카테고리별 소비액, 할인율, 한도 및 최종 혜택 |

세부 계산 조건과 예시는 `docs/explanations/recommendation-core.md`에서 확인할 수
있습니다. 실제 구현은 `finance/recommendation.py`를 기준으로 합니다.

## 검증

```bash
python manage.py check
python manage.py test finance hyperlocal users
python manage.py sync_cards_to_neo4j --dry-run
```

2026년 6월 21일 기준 백엔드 테스트 137개가 통과했습니다.

## Git 인계

- 작업 브랜치: `feat/developer-a-backend`
- 현재 단계에서는 `main`에 push하지 않습니다.
- 기능 단위로 커밋한 뒤 브랜치에서 상태를 확인합니다.
- `.env`, `db.sqlite3`, `media/cards/`, `frontend/.env.local`,
  `frontend/node_modules/`는 커밋하지 않습니다.
