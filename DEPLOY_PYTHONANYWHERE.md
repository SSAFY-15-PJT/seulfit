# PythonAnywhere 배포 가이드

이 프로젝트는 Django REST 백엔드와 Vite/Vue 프론트엔드로 구성되어 있습니다. PythonAnywhere에서는 Vite dev 서버를 띄우지 않고, `frontend/dist`를 빌드한 뒤 Django WSGI 앱이 API와 Vue 앱을 함께 서빙하는 방식으로 배포합니다.

## 1. PythonAnywhere에 코드 올리기

PythonAnywhere Bash 콘솔에서:

```bash
cd ~
git clone <your-repo-url> seulfit
```

이미 업로드했다면 `~/seulfit` 아래에 `backend/`, `frontend/`가 있어야 합니다.

## 2. Python 가상환경 만들기

```bash
mkvirtualenv --python=/usr/bin/python3.12 seulfit-venv
cd ~/seulfit/backend
pip install -r requirements.txt
```

PythonAnywhere 공식 문서도 기존 Django 프로젝트는 virtualenv를 만들고 requirements를 설치한 뒤 Web 탭에서 Manual Configuration을 쓰는 흐름을 안내합니다.

## 3. backend/.env 만들기

```bash
cd ~/seulfit/backend
cp .env.example .env
nano .env
```

필수로 바꿀 값:

```dotenv
DJANGO_SECRET_KEY=<긴 랜덤 문자열>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<yourusername>.pythonanywhere.com
CORS_ALLOWED_ORIGINS=https://<yourusername>.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://<yourusername>.pythonanywhere.com

KAKAO_REST_API_KEY=<카카오 REST 키>
KAKAO_API_KEY=<카카오 REST 키>
KAKAO_JAVASCRIPT_KEY=<카카오 JavaScript 키>
YOUTUBE_API_KEY=<유튜브 키>

GMS_KEY=<GMS 키>
VLM_API_KEY=<GMS 키>
VLM_MODEL=gemini-3.5-flash
VLM_API_TYPE=gemini_generate_content
VLM_API_URL=https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent
```

Neo4j는 PythonAnywhere 안에서 Docker를 띄우기 어렵습니다. 외부 Neo4j AuraDB나 별도 서버를 쓰는 경우에만 아래 값을 외부 주소로 넣으세요. 비워두면 앱은 SQLite 추천 fallback으로 동작합니다.

```dotenv
NEO4J_HTTP_URI=https://your-neo4j-http-endpoint
NEO4J_DATABASE=neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>
```

## 4. DB 준비

기존 로컬 `backend/db.sqlite3`를 그대로 업로드할 수도 있고, 새로 만들 수도 있습니다.

새 DB를 만들 때:

```bash
cd ~/seulfit/backend
python manage.py migrate
python manage.py seed_demo_data --skip-neo4j
```

카드 크롤링/활성화 데이터가 필요하면 로컬에서 만든 `db.sqlite3`와 `backend/media/cards/`를 같이 업로드하는 편이 빠릅니다.

## 5. 프론트엔드 빌드

PythonAnywhere에서 Node가 없거나 낮으면 NVM을 설치해 Node 18+를 사용하세요.

```bash
cd ~
git clone --depth 1 https://github.com/nvm-sh/nvm.git ~/nvm
source ~/nvm/nvm.sh
nvm install 20
nvm alias default 20
```

빌드:

```bash
cd ~/seulfit/frontend
npm ci
npm run build
```

프론트 API 주소는 기본값이 `/api/v1`이라 같은 도메인 배포에서는 별도 `VITE_API_BASE`가 필요 없습니다. Kakao Map 키도 `/api/v1/config/`에서 백엔드가 내려줍니다.

## 6. PythonAnywhere Web 앱 설정

PythonAnywhere Web 탭:

1. Add a new web app
2. Manual configuration 선택
3. Python 버전은 가상환경과 같은 버전 선택
4. Virtualenv에 `seulfit-venv` 입력
5. Source code와 Working directory:

```text
/home/<yourusername>/seulfit/backend
```

## 7. WSGI 파일 설정

Web 탭의 WSGI file 링크를 열고 내용을 아래처럼 바꿉니다.

```python
import os
import sys

USERNAME = "<yourusername>"
PROJECT_DIR = f"/home/{USERNAME}/seulfit/backend"

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "seulpick_api.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

같은 예시는 `deploy/pythonanywhere_wsgi.py.example`에도 있습니다.

## 8. Static files mapping

PythonAnywhere Web 탭의 Static files 섹션에 아래를 추가합니다.

```text
URL: /static/
Directory: /home/<yourusername>/seulfit/backend/staticfiles
```

```text
URL: /assets/
Directory: /home/<yourusername>/seulfit/frontend/dist/assets
```

```text
URL: /media/
Directory: /home/<yourusername>/seulfit/backend/media
```

그리고 Django admin/static 수집:

```bash
cd ~/seulfit/backend
python manage.py collectstatic --noinput
```

PythonAnywhere 공식 문서는 Static files mapping을 URL과 디렉터리의 대응으로 설정하고, Web app reload 후 적용한다고 설명합니다.

## 9. 배포 확인

```bash
cd ~/seulfit/backend
python manage.py check --deploy
```

Web 탭에서 Reload를 누른 뒤 확인:

```text
https://<yourusername>.pythonanywhere.com/
https://<yourusername>.pythonanywhere.com/api/v1/health/
https://<yourusername>.pythonanywhere.com/api/v1/config/
```

## 주의 사항

- 무료 PythonAnywhere 계정은 외부 인터넷 접근이 allowlist에 제한될 수 있습니다. Kakao, YouTube, GMS, Neo4j 외부 API 호출이 막히면 유료 플랜 또는 allowlist 확인이 필요합니다.
- `DJANGO_DEBUG=False`에서는 `/media/`를 Django가 직접 서빙하지 않으므로 PythonAnywhere Static files mapping에 `/media/`를 꼭 넣어야 카드 이미지가 보입니다.
- 프론트를 수정한 뒤에는 `npm run build`를 다시 실행하고 Web app Reload를 누르세요.
