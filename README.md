# SeulPick

SeulPick은 사용자의 소비 내역, 현재 생활권 지도 데이터, 카드 혜택 데이터를 함께 분석해 지역 맞춤 카드 추천을 제공하는 Vue 3 + Django REST 프로젝트입니다.

현재 구현 기준 소스는 `backend/`입니다. 프론트엔드는 백엔드 API 계약을 소비하는 방식으로 동작합니다.

## 주요 기능

- Kakao Map 기반 지역 선택
  - 지도 클릭 또는 주소 검색으로 위치 선택
  - 반경 100m-400m 내 카페, 편의점, 마트, 음식점/배달 장소 표시
  - 지역 변경 시 추천 재계산
- 소비 내역 자동 분석
  - 이미지 업로드 VLM 분석
  - PDF 카드 명세서 텍스트 파싱
  - 여러 페이지 PDF의 `이용일자 / 가맹점명 / 금액` 행 전체 합산
  - 카테고리: `cafe`, `convenience`, `mart`, `dining`, `delivery`, `shopping`, `transport`, `etc`
  - 분류 불가 항목은 `etc`로 처리
- 카드 추천
  - SQLite 카드 혜택 데이터 기반 추천
  - Graph DB 후보군이 있으면 지역-상권-혜택 관계를 반영
  - Seul-Score, 예상 혜택, 지역 적합도 표시
- 카드 이미지 표시
  - `CardImage` 데이터를 `image_url`로 API 응답에 포함
  - 카드 대시보드, 추천 리포트, 상세 drawer에서 실제 카드 이미지 렌더링
- 외부 API 연동
  - Kakao Map
  - YouTube API
  - GMS/Gemini VLM API

## 프로젝트 구조

```text
backend/
  manage.py
  requirements.txt
  seulpick_api/
  core/
  hyperlocal/
  finance/
  users/
  community/

frontend/
  package.json
  vite.config.js
  index.html
  src/
```

## 실행 방법

### Backend

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

현재 개발 서버는 다음 주소를 기준으로 사용합니다.

```text
http://127.0.0.1:8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

프론트 주소:

```text
http://127.0.0.1:5173
```

## 환경 변수

운영 키는 코드에 하드코딩하지 않습니다. 로컬에서는 아래 파일을 사용합니다.

```text
backend/.env
frontend/.env.local
```

### backend/.env

```dotenv
DJANGO_SECRET_KEY=your-local-secret

KAKAO_REST_API_KEY=your-kakao-rest-key
KAKAO_JAVASCRIPT_KEY=your-kakao-js-key
KAKAOMAP_API_KEY=your-kakao-rest-key

YOUTUBE_API_KEY=your-youtube-api-key

GMS_KEY=your-gms-key
VLM_API_KEY=${GMS_KEY}
VLM_MODEL=gemini-3.5-flash
VLM_API_TYPE=gemini_generate_content
VLM_API_URL=https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent

NEO4J_HTTP_URI=http://localhost:7474
NEO4J_DATABASE=neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-local-password
```

### frontend/.env.local

```dotenv
VITE_API_BASE=http://127.0.0.1:8001/api/v1
VITE_BACKEND_ORIGIN=http://127.0.0.1:8001
VITE_KAKAO_JAVASCRIPT_KEY=your-kakao-js-key
```

## 주요 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/api/v1/health/` | 백엔드 및 주요 API 키 설정 상태 |
| GET | `/api/v1/config/` | 프론트 설정 |
| GET | `/api/v1/videos/` | YouTube 카드 추천 영상 검색 |
| POST | `/api/v1/hyperlocal/parse-image/` | 이미지/PDF 소비 내역 분석 |
| GET | `/api/v1/hyperlocal/map-summary/` | 위치 반경 내 지역 인프라 조회 |
| POST | `/api/v1/hyperlocal/simulate/` | 카드 추천 및 Seul-Score 계산 |
| GET | `/api/v1/finance/cards/` | 카드 목록 조회 |
| POST | `/api/v1/users/reports/` | 업로드 분석 결과 저장 |
| GET | `/api/v1/users/profile/` | 사용자 프로필 및 소비 프로필 조회 |

## PDF 소비 분석

PDF 업로드는 먼저 로컬 파서를 시도합니다. 다음 구조의 카드 명세서는 VLM 호출 없이도 처리됩니다.

```text
이용일자
가맹점명
금액
2026.05.01
스타벅스 강남역점
7,900원
```

동작 방식:

1. PyMuPDF로 PDF 전체 페이지 텍스트 추출
2. 날짜, 가맹점명, 금액 3줄 패턴을 거래 1건으로 인식
3. 가맹점명 기반 카테고리 분류
4. 분류 불가 항목은 `etc`
5. 카테고리별 금액 합산 후 프론트 소비 테이블에 적용

샘플 검증 결과:

```text
source: local_pdf_statement_parser
vlm_status: ok
거래 96건
총합 2,067,450원
```

## 소비 카테고리 매핑

| UI 표시 | Backend key |
| --- | --- |
| 카페 | `cafe` |
| 편의점 | `convenience` |
| 마트/슈퍼 | `mart` |
| 음식점/배달 | `dining` + `delivery` |
| 의류/소품 | `shopping` |
| 교통 | `transport` |
| 기타 | `etc` |

예시:

- 스타벅스, 공차, 메가커피, 파리바게뜨 → `cafe`
- CU, GS25, 세븐일레븐, 이마트24 → `convenience`
- 마켓컬리, 이마트, 홈플러스 → `mart`
- 맥도날드, 한솥도시락, 샐러디 → `dining`
- 배달의민족, 우아한형제들, 쿠팡이츠 → `delivery`
- 무신사, 올리브영, 백화점, 오늘의집, 쿠팡 → `shopping`
- 쏘카, 카카오택시, 버스/지하철 → `transport`
- 네이버페이, 토스페이, 유튜브프리미엄, 넷플릭스, 약국 → `etc`

## 카드 이미지 데이터

카드 이미지는 `finance.CardImage` 모델을 사용합니다.

추천 API는 다음 우선순위로 `image_url`을 내려줍니다.

1. `download_status=success`이고 `is_primary=True`인 이미지
2. `download_status=success`인 이미지
3. `is_primary=True`인 이미지
4. 첫 번째 이미지

`local_path`가 있으면 `/media/...` URL로 변환하고, 프론트는 `VITE_BACKEND_ORIGIN`을 붙여 이미지를 렌더링합니다.

## 검증 명령

```bash
cd backend
python manage.py check
python manage.py test hyperlocal.tests.VlmConsumptionParserTests
python manage.py test finance.test_card_catalog.CardCatalogTests finance.test_views.CardProductListApiTests
```

```bash
cd frontend
npm run build
```

최근 확인한 상태:

```text
Django check 통과
VLM/PDF 파서 테스트 통과
카드 이미지 카탈로그 테스트 통과
frontend build 통과
```

## 작업 메모

- `backend/seulpick_api/settings.py`는 `backend/.env`를 우선 읽도록 설정되어 있습니다.
- PDF 분석 성공 source는 `local_pdf_statement_parser`입니다.
- 프론트 업로드 성공 source allowlist:
  - `vlm`
  - `local_sample_parser`
  - `local_pdf_statement_parser`
- GMS/Gemini VLM이 실패해도, 텍스트 추출 가능한 PDF 명세서는 로컬 파서로 성공 처리됩니다.
- 카드 이미지가 없는 경우 기존 카드 목업 UI가 fallback으로 표시됩니다.
