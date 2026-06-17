# SeulPick Vue + Django 구조

단일 HTML 와이어프레임을 Vue 3 프론트엔드와 Django REST API 백엔드로 분리한 MVP 골격입니다.

# 커밋 컨벤션

[Gitmoji](https://gitmoji.dev/)로 Commit Message 남기기  
ex) ✨ Feat: LLM에게 프롬프팅 설정 완료
|Icon|Feat||
|-----|----|---|
|✨|Feat|새로운 기능 추가|
|🐛|Fix|버그/기능에 따른 코드 변경 시|
|♻️|Refactor|코드의 가독성, 효율성을 위한 코드 변경 시 (기능의 문제 X)|
|📝|Docs|문서 추가/수정/삭제|
|🔧|Chore|설정 추가/변경|
|✅|Test|테스트 코드 추가/수정|

---

## 구조

```text
backend/
  manage.py
  requirements.txt
  seulpick_api/
  hyperlocal/
  finance/
  community/
  users/
frontend/
  package.json
  vite.config.js
  index.html
  src/
```

## 실행

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

프론트엔드는 Vite 프록시를 통해 기본적으로 `http://localhost:8001/api/v1`로 API를 호출합니다.
필요하면 `frontend/.env`에 `VITE_API_BASE_URL`을 지정하세요.

## 주요 API

- `POST /api/v1/hyperlocal/parse-image/`
- `POST /api/v1/hyperlocal/simulate/`
- `GET /api/v1/hyperlocal/map-summary/`
- `GET /api/v1/hyperlocal/weather-curation/`
- `GET /api/v1/finance/cards/`
- `GET /api/v1/community/posts/`
- `GET /api/v1/users/profile/`
