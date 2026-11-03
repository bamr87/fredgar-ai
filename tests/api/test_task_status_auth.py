"""GET /api/v1/tasks/{id}/ must not expose task results or errors to non-staff."""

from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

URL = "/api/v1/tasks/00000000-0000-4000-8000-000000000000/"


def _fake_result(ready=True, ok=False, result="boom: internal detail"):
    r = mock.Mock(status="FAILURE" if not ok else "SUCCESS", result=result)
    r.ready.return_value = ready
    r.successful.return_value = ok
    return r


@pytest.mark.django_db
def test_anonymous_is_rejected(api_client):
    with mock.patch("celery.result.AsyncResult", return_value=_fake_result()):
        resp = api_client.get(URL)
    assert resp.status_code in (401, 403)
    assert "boom" not in resp.content.decode()


@pytest.mark.django_db
def test_non_staff_is_rejected():
    user = get_user_model().objects.create_user(username="plain", password="x")
    client = APIClient()
    client.force_authenticate(user)
    with mock.patch("celery.result.AsyncResult", return_value=_fake_result()):
        resp = client.get(URL)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_staff_sees_result(admin_client):
    fake = _fake_result(ok=True, result={"filings_processed": 3})
    with mock.patch("celery.result.AsyncResult", return_value=fake):
        resp = admin_client.get(URL)
    assert resp.status_code == 200
    assert resp.json()["result"] == {"filings_processed": 3}
