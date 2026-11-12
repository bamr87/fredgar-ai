from __future__ import annotations

import pytest
from rest_framework import status


@pytest.mark.django_db
def test_health_ok(api_client) -> None:
    r = api_client.get("/api/v1/health/")
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["status"] == "ok"


@pytest.mark.django_db
def test_health_ready_database(api_client) -> None:
    r = api_client.get("/api/v1/health/ready/")
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert body["status"] == "ok"
    # UPS-BE-11 vocabulary: string checks keyed `db`/`cache`/`broker` (was `database: True`).
    assert body["checks"]["db"] == "ok"


@pytest.mark.django_db
def test_companies_list_json_shape(api_client) -> None:
    r = api_client.get("/api/v1/companies/")
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert "results" in data or isinstance(data, list)
