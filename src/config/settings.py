import os
from pathlib import Path

import dj_database_url
from corsheaders.defaults import default_headers as _cors_default_headers
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load src/.env (if present) before any os.getenv() below. Real environment
# variables already set take precedence (override=False).
load_dotenv(BASE_DIR / ".env", override=False)


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

# Fail fast in production rather than booting with insecure defaults.
if not DEBUG:
    if SECRET_KEY == "dev-secret-key":
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a strong value when DJANGO_DEBUG=false"
        )
    if ALLOWED_HOSTS == ["*"]:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must be set (not '*') when DJANGO_DEBUG=false"
        )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Registers the Postgres full-text `__search` lookup used by /filings/search/
    # (no models, so it adds no migrations; the icontains fallback covers SQLite).
    'django.contrib.postgres',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'django_filters',
    'warehouse',
    'sec_edgar',
    'public_data',
    'enrichment',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(BASE_DIR / 'db.sqlite3'),
        }
    }

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'fredgar-ai',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# JSON-only in production; the browsable API is a dev convenience (and a prod info leak).
_RENDERER_CLASSES = ['rest_framework.renderers.JSONRenderer']
if DEBUG:
    _RENDERER_CLASSES.append('rest_framework.renderers.BrowsableAPIRenderer')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # Token auth lets the cross-origin SPA authenticate via the Authorization
        # header (no CSRF); session auth is for the Django admin / browsable API.
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        # Reads are public; writes and SEC-hitting actions require a staff user.
        'api.permissions.IsAdminOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': int(os.getenv('API_PAGE_SIZE', '50')),
    'DEFAULT_RENDERER_CLASSES': _RENDERER_CLASSES,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('THROTTLE_ANON', '60/min'),
        'user': os.getenv('THROTTLE_USER', '600/min'),
        # Scoped throttle applied to SEC-hitting actions (sync/ingest/bulk/resolve).
        'sec': os.getenv('THROTTLE_SEC', '20/min'),
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Fredgar AI API',
    'DESCRIPTION': 'SEC EDGAR company data, filings, XBRL facts, derived metrics, '
    'financial statements, and macro series.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# drf-spectacular can't infer serializers for the plain health/task APIViews; that
# schema-completeness warning is cosmetic and must not fail `check --deploy`.
SILENCED_SYSTEM_CHECKS = ['drf_spectacular.W002']

# Local dev: allow Vite frontend (include alternate ports if Vite bumps e.g. 5173→5174). Tighten in production via env.
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,http://localhost:8080,http://127.0.0.1:8080',
    ).split(',')
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(_cors_default_headers) + [
    "x-sec-user-agent-email",
    "authorization",
]

# Security headers — relaxed in DEBUG, hardened otherwise. TLS terminates at the
# proxy/nginx; SECURE_PROXY_SSL_HEADER tells Django the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 0 if DEBUG else int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# HTM downloads and parsed artifacts (default: repo /data)
EDGAR_DATA_DIR = os.getenv('EDGAR_DATA_DIR', str((BASE_DIR.parent / 'data').resolve()))

SEC_USER_AGENT_EMAIL = os.getenv('USER_AGENT_EMAIL', '')

# Static site mirror (GitHub Pages). STATIC_SITE_BASE_URL is the canonical public URL
# of the published mirror (drives sitemap/robots + the frontend cross-link);
# STATIC_SITE_APP_URL is the interactive app the mirror links back to. Both optional.
STATIC_SITE_BASE_URL = os.getenv('STATIC_SITE_BASE_URL', '').rstrip('/')
STATIC_SITE_APP_URL = os.getenv('STATIC_SITE_APP_URL', '').rstrip('/')
STATIC_SITE_SOURCE_URL = os.getenv(
    'STATIC_SITE_SOURCE_URL', 'https://github.com/bamr87/fredgar-ai'
).rstrip('/')

# Content-addressed storage for filing artifacts (raw + extracted text).
STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'local')  # 'local' | 's3'
STORAGE_ROOT = os.getenv('STORAGE_ROOT', os.path.join(EDGAR_DATA_DIR, 'storage'))
S3_BUCKET = os.getenv('S3_BUCKET', '')
S3_PREFIX = os.getenv('S3_PREFIX', '')

# Apache Tika content extraction (PDF/other); requires a Tika server sidecar.
ENABLE_TIKA = _env_bool('ENABLE_TIKA', False)
TIKA_SERVER_ENDPOINT = os.getenv('TIKA_SERVER_ENDPOINT', 'http://localhost:9998')

# Embeddings (Company-360 AI foundation). Off by default — the ContentChunk schema
# and retrieval exist regardless; embeddings populate only when a backend is enabled.
ENABLE_EMBEDDINGS = _env_bool('ENABLE_EMBEDDINGS', False)
EMBEDDINGS_BACKEND = os.getenv('EMBEDDINGS_BACKEND', 'none')  # none | local | api

# AI narrative analysis (leadership initiatives/quotes from filing text). Enabled by
# default with Claude as the provider; it degrades to a no-op unless the optional
# `anthropic` SDK (requirements-ai.txt) AND a credential are present, so it is never
# required for the core runtime. Output is grounded in SEC filing excerpts only.
ENABLE_AI_ANALYSIS = _env_bool('ENABLE_AI_ANALYSIS', True)
AI_ANALYSIS_BACKEND = os.getenv('AI_ANALYSIS_BACKEND', 'anthropic')  # anthropic | none
AI_ANALYSIS_MODEL = os.getenv('AI_ANALYSIS_MODEL', 'claude-opus-4-8')
# Credential, token-first: a Claude Code OAuth token (`claude setup-token`) is preferred and
# sent as a Bearer auth token with the oauth beta header; ANTHROPIC_API_KEY is the fallback.
# Set only ONE — if both a token and an API key are present the Anthropic API returns 401.
AI_ANALYSIS_AUTH_TOKEN = (
    os.getenv('CLAUDE_CODE_OAUTH_TOKEN') or os.getenv('ANTHROPIC_AUTH_TOKEN') or ''
).strip()
AI_ANALYSIS_API_KEY = os.getenv('ANTHROPIC_API_KEY', '').strip()

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'sec_edgar': {'level': 'INFO', 'propagate': True},
        'public_data': {'level': 'INFO', 'propagate': True},
    },
}

# Celery (background jobs) — Redis broker/result backend by default.
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = _env_bool('CELERY_TASK_ALWAYS_EAGER', False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.getenv('CELERY_TASK_TIME_LIMIT', '1800'))
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

SENTRY_DSN = os.getenv('SENTRY_DSN', '').strip()
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0')),
        send_default_pii=False,
    )
