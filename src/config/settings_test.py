"""Django settings for pytest and CI (imported via DJANGO_SETTINGS_MODULE)."""

# Import production-like settings, then tighten for tests.
from .settings import *  # noqa: F403

DEBUG = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Run Celery tasks inline (no broker needed in tests).
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Tests must not call SEC/FRED unless explicitly mocked; keys may still be set in env.
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Neutralize throttling in tests so the global + per-action throttle classes never
# cause flaky 429s. Rates are set to None (unlimited) for every scope so even
# explicitly-attached action throttles (e.g. the 'sec' scope) become no-ops.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"anon": None, "user": None, "sec": None},
}

# AI analysis is on by default in production, but tests must never hit the live Anthropic
# API. Force it off and clear credentials here; tests that exercise the analyzer enable it
# explicitly via @override_settings and inject a fake client (or set a fake credential).
ENABLE_AI_ANALYSIS = False
AI_ANALYSIS_AUTH_TOKEN = ""
AI_ANALYSIS_API_KEY = ""

# FRED vintages fetch from FRED on demand; keep them off whatever src/.env says, and let
# the tests that exercise them switch them on with a mocked FRED.
ENABLE_FRED_VINTAGES = False
