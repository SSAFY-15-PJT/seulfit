import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env", override=True)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    value = os.getenv(name, "")
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-seulpick-secret-key")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["*"] if DEBUG else [])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "hyperlocal",
    "finance",
    "community",
    "users",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "seulpick_api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "seulpick_api.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    PROJECT_ROOT / "frontend" / "dist" / "assets",
] if (PROJECT_ROOT / "frontend" / "dist" / "assets").exists() else []
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY") or os.getenv("KAKAO_API_KEY", "")
KAKAO_JAVASCRIPT_KEY = (
    os.getenv("KAKAO_JAVASCRIPT_KEY")
    or os.getenv("KAKAOMAP_API_KEY")
    or os.getenv("KAKAO_MAP_API_KEY", "")
)
KAKAOMAP_API_KEY = KAKAO_JAVASCRIPT_KEY
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
GMS_KEY = os.getenv("GMS_KEY", "")
VLM_API_URL = os.getenv("VLM_API_URL", "")
VLM_API_KEY = os.getenv("VLM_API_KEY") or os.getenv("GMS_KEY", "")
VLM_MODEL = os.getenv("VLM_MODEL", "")
VLM_API_TYPE = os.getenv("VLM_API_TYPE", "chat_completions")
VLM_GMS_COMPAT = os.getenv("VLM_GMS_COMPAT", "").lower() in {"1", "true", "yes", "on"}
VLM_GMS_STRICT = os.getenv("VLM_GMS_STRICT", "").lower() in {"1", "true", "yes", "on"}
NEO4J_HTTP_URI = os.getenv("NEO4J_HTTP_URI", "http://localhost:7474")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", CORS_ALLOWED_ORIGINS)

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
}
