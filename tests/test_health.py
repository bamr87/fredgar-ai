import json
from pathlib import Path
from unittest import mock

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.django_db
def test_api_v1_health():
    c = Client()
    r = c.get("/api/v1/health/")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_healthz_ok_without_touching_db():
    with mock.patch(
        "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
        side_effect=RuntimeError("db down"),
    ):
        r = Client().get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_readyz_ok():
    r = Client().get("/readyz")
    assert r.status_code == 200
    # Tests run Celery eagerly, so the broker check is skipped (no live Redis needed).
    assert r.json() == {"status": "ok", "checks": {"db": "ok", "cache": "ok", "broker": "skipped"}}
    assert r["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_readyz_degraded_when_db_unreachable():
    with mock.patch(
        "api.v1.views.connection.ensure_connection", side_effect=RuntimeError("db down")
    ):
        r = Client().get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["db"] == "error: RuntimeError"
    assert body["checks"]["cache"] == "ok"
    # The probe is public: the exception message must not leak.
    assert "db down" not in r.content.decode()


@pytest.mark.django_db
def test_readyz_degraded_when_open_connection_is_dead():
    # Persistent connections (conn_max_age) stay "open" after the server goes away;
    # readiness must make a round trip rather than trust ensure_connection().
    from django.db import OperationalError

    with mock.patch("api.v1.views.connection.cursor", side_effect=OperationalError("gone")):
        r = Client().get("/readyz")
    assert r.status_code == 503
    assert r.json()["checks"]["db"] == "error: OperationalError"


@pytest.mark.django_db
@override_settings(
    CELERY_TASK_ALWAYS_EAGER=False, CELERY_BROKER_URL="redis://broker.invalid:6379/0"
)
def test_readyz_degraded_when_broker_unreachable():
    with mock.patch("redis.Redis.ping", side_effect=ConnectionError("refused")):
        r = Client().get("/readyz")
    assert r.status_code == 503
    assert r.json()["checks"]["broker"] == "error: ConnectionError"


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=False, CELERY_BROKER_URL="redis://broker:6379/0")
def test_readyz_broker_ok():
    with mock.patch("redis.Redis.ping", return_value=True):
        r = Client().get("/readyz")
    assert r.status_code == 200
    assert r.json()["checks"]["broker"] == "ok"


@override_settings(CELERY_TASK_ALWAYS_EAGER=False, CELERY_BROKER_URL="memory://")
@pytest.mark.django_db
def test_readyz_broker_skipped_when_not_redis():
    assert Client().get("/readyz").json()["checks"]["broker"] == "skipped"


def test_version(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc1234")
    monkeypatch.setenv("BUILT_AT", "2026-11-11T00:00:00Z")
    r = Client().get("/version")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"name", "version", "commit", "built_at"}
    manifest = json.loads((REPO_ROOT / ".release-please-manifest.json").read_text())
    assert body == {
        "name": "fredgar-ai",
        "version": manifest["."],
        "commit": "abc1234",
        "built_at": "2026-11-11T00:00:00Z",
    }


def test_version_unknown_build_metadata(monkeypatch):
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILT_AT", raising=False)
    body = Client().get("/version").json()
    assert body["commit"] == "unknown"
    assert body["built_at"] == "unknown"


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/healthz", "/readyz", "/version", "/api/v1/health/ready/"])
def test_probes_anonymous_and_unthrottled(url):
    # Re-enable the production anon throttle at a tiny rate (DRF binds the defaults at
    # import, and settings_test clears them, so patch the class attributes directly):
    # an ordinary endpoint now 429s, the probes must not.
    with (
        mock.patch.object(APIView, "throttle_classes", [AnonRateThrottle]),
        mock.patch.object(AnonRateThrottle, "THROTTLE_RATES", {"anon": "2/min"}),
    ):
        cache.clear()
        c = Client()
        codes = [c.get(url).status_code for _ in range(5)]
        assert codes == [200] * 5
        # Sanity: the throttle really is active for a normal endpoint.
        cache.clear()
        other = [c.get(reverse("reference-sic-codes")).status_code for _ in range(5)]
        assert 429 in other
    cache.clear()
