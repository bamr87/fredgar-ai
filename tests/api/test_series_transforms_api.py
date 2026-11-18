"""FRED transforms and vintages on the observation endpoints (FR-MAC-001)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import responses
from responses import matchers

from public_data.models import ExternalSeries, SeriesBundle, SeriesBundleItem, SeriesObservation
from public_data.providers.fred import FRED_OBSERVATIONS_URL
from warehouse.models import SeriesVintageObservation

BUNDLE_URL = "/api/v1/series-bundles/test-macro/observations/"
OBS_URL = "/api/v1/public-observations/"


@pytest.fixture
def bundle(db):
    monthly = ExternalSeries.objects.create(
        provider="fred", external_id="TESTM", title="Test monthly", frequency="Monthly",
        units="Index", metadata={"note": "a monthly series", "industries": ["Retail"]},
    )
    quarterly = ExternalSeries.objects.create(
        provider="fred", external_id="TESTQ", title="Test quarterly", frequency="Quarterly",
        units="Billions of Dollars",
    )
    for m in range(1, 13):
        SeriesObservation.objects.create(series=monthly, observation_date=date(2023, m, 1), value=Decimal(99 + m))
    for m in range(1, 4):
        SeriesObservation.objects.create(series=monthly, observation_date=date(2024, m, 1), value=Decimal(111 + m))
    for day, value in (
        (date(2022, 1, 1), 200), (date(2022, 4, 1), 202), (date(2022, 7, 1), 204),
        (date(2022, 10, 1), 206), (date(2023, 1, 1), 210), (date(2023, 4, 1), 212),
    ):
        SeriesObservation.objects.create(series=quarterly, observation_date=day, value=Decimal(value))
    b = SeriesBundle.objects.create(slug="test-macro", name="Test macro", description="Two series")
    SeriesBundleItem.objects.create(bundle=b, series=monthly, sort_order=0)
    SeriesBundleItem.objects.create(bundle=b, series=quarterly, sort_order=1)
    return {"monthly": monthly, "quarterly": quarterly}


def by_series(payload, external_id):
    return {o["date"]: o["value"] for o in payload["observations"] if o["series"] == external_id}


# --------------------------------------------------------------------------- defaults


def test_bundle_payload_without_params_is_unchanged(api_client, bundle):
    r = api_client.get(BUNDLE_URL)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"bundle", "name", "description", "count", "series", "observations"}
    assert body["count"] == 21
    assert body["series"][0] == {
        "external_id": "TESTM", "title": "Test monthly", "units": "Index", "frequency": "Monthly",
        "note": "a monthly series", "industries": ["Retail"],
    }
    # Newest first per series, the stored decimal strings, in bundle order.
    assert body["observations"][0] == {"series": "TESTM", "provider": "fred", "date": "2024-03-01", "value": "114.000000"}
    assert body["observations"][15] == {"series": "TESTQ", "provider": "fred", "date": "2023-04-01", "value": "212.000000"}


def test_observation_list_without_params_is_unchanged(api_client, bundle):
    r = api_client.get(OBS_URL, {"series": bundle["monthly"].pk})
    assert r.status_code == 200
    body = r.json()
    assert "transform" not in body
    assert body["count"] == 15
    assert set(body["results"][0]) == {"id", "series", "observation_date", "value", "source_url", "retrieved_at"}


# --------------------------------------------------------------------------- transforms


def test_bundle_pc1_quarterly_average(api_client, bundle):
    r = api_client.get(BUNDLE_URL, {"units": "pc1", "frequency": "q", "aggregation": "avg"})
    assert r.status_code == 200
    body = r.json()
    assert body["transform"] == {"units": "pc1", "frequency": "q", "aggregation": "avg", "vintage_date": None}
    assert [s["output_frequency"] for s in body["series"]] == ["q", "q"]
    # Monthly averaged to quarters, then FRED pc1: only 2024Q1 has a year-ago quarter.
    assert by_series(body, "TESTM") == {"2024-01-01": "11.881188"}  # (113/101 - 1) * 100
    assert by_series(body, "TESTQ") == {"2023-04-01": "4.950495", "2023-01-01": "5.000000"}
    assert body["count"] == 3


def test_bundle_series_keeps_its_own_frequency_when_the_request_is_higher(api_client, bundle):
    body = api_client.get(BUNDLE_URL, {"frequency": "m"}).json()
    assert body["transform"] == {"units": "lin", "frequency": "m", "aggregation": "avg", "vintage_date": None}
    assert [s["output_frequency"] for s in body["series"]] == ["m", "q"]
    assert by_series(body, "TESTQ")["2022-01-01"] == "200.000000"


def test_bundle_per_series_limit_applies_after_the_transform(api_client, bundle):
    body = api_client.get(BUNDLE_URL, {"units": "chg", "per_series": 2}).json()
    assert by_series(body, "TESTM") == {"2024-03-01": "1.000000", "2024-02-01": "1.000000"}


@pytest.mark.parametrize(
    ("params", "word"),
    [
        ({"units": "bogus"}, "units"),
        ({"frequency": "bw"}, "frequency"),
        ({"frequency": "q", "aggregation": "median"}, "aggregation"),
    ],
)
def test_unknown_values_are_a_400_with_detail(api_client, bundle, params, word):
    for url, extra in ((BUNDLE_URL, {}), (OBS_URL, {"series": bundle["monthly"].pk})):
        r = api_client.get(url, {**params, **extra})
        assert r.status_code == 400
        assert word in r.json()["detail"]


def test_observation_list_transforms_one_series(api_client, bundle):
    r = api_client.get(OBS_URL, {"series": bundle["monthly"].pk, "units": "chg"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 14  # the first month has no previous one
    assert body["results"][0] == {"series": bundle["monthly"].pk, "observation_date": "2024-03-01", "value": "1.000000"}
    assert body["transform"] == {"units": "chg", "frequency": None, "aggregation": None, "vintage_date": None}
    assert body["output_frequency"] == "m"


def test_observation_list_refuses_a_frequency_above_the_series_own(api_client, bundle):
    r = api_client.get(OBS_URL, {"series": bundle["quarterly"].pk, "frequency": "m"})
    assert r.status_code == 400
    assert "higher than the series' own frequency" in r.json()["detail"]


def test_observation_list_needs_one_known_series(api_client, bundle):
    assert api_client.get(OBS_URL, {"units": "pc1"}).status_code == 400
    assert api_client.get(OBS_URL, {"units": "pc1", "series": "abc"}).status_code == 400
    assert api_client.get(OBS_URL, {"units": "pc1", "series": 999999}).status_code == 404


# --------------------------------------------------------------------------- vintages


@pytest.fixture
def vintages_on(settings):
    settings.ENABLE_FRED_VINTAGES = True


def vintage_body(*rows):
    return {
        "realtime_start": "2020-01-01",
        "realtime_end": "2020-01-01",
        "observations": [
            {"realtime_start": "2020-01-01", "realtime_end": "2020-01-01", "date": d, "value": v}
            for d, v in rows
        ],
    }


def vintage_matcher(series_id):
    return matchers.query_param_matcher(
        {
            "series_id": series_id,
            "realtime_start": "2020-01-01",
            "realtime_end": "2020-01-01",
            "api_key": "test-fred-key",
            "file_type": "json",
        }
    )


def test_vintage_date_is_a_400_while_vintages_are_off(api_client, bundle):
    for url, extra in ((BUNDLE_URL, {}), (OBS_URL, {"series": bundle["monthly"].pk})):
        r = api_client.get(url, {"vintage_date": "2020-01-01", **extra})
        assert r.status_code == 400
        assert "ENABLE_FRED_VINTAGES" in r.json()["detail"]
    assert not SeriesVintageObservation.objects.exists()


def test_vintage_is_fetched_once_then_served_from_the_database(
    api_client, admin_client, bundle, fred_api_key, vintages_on
):
    params = {"series": bundle["monthly"].pk, "vintage_date": "2020-01-01"}
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rs:
        rs.add(
            responses.GET,
            FRED_OBSERVATIONS_URL,
            match=[vintage_matcher("TESTM")],
            json=vintage_body(("2019-10-01", "95.5"), ("2019-11-01", "96.0"), ("2019-12-01", ".")),
        )
        first = admin_client.get(OBS_URL, params)
    assert first.status_code == 200
    body = first.json()
    assert body["transform"]["vintage_date"] == "2020-01-01"
    assert [(row["observation_date"], row["value"]) for row in body["results"]] == [
        ("2019-11-01", "96.000000"),
        ("2019-10-01", "95.500000"),
    ]
    stored = SeriesVintageObservation.objects.filter(series=bundle["monthly"], vintage_date=date(2020, 1, 1))
    assert stored.count() == 2
    assert {(o.realtime_start, o.realtime_end) for o in stored} == {(date(2020, 1, 1), date(2020, 1, 1))}
    assert "api_key" not in stored.first().source_url

    # Stored now: anyone reads it, and FRED is not asked again.
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rs:  # nothing registered
        again = api_client.get(OBS_URL, {**params, "units": "chg"})
        assert len(rs.calls) == 0
    assert again.status_code == 200
    assert again.json()["results"] == [
        {"series": bundle["monthly"].pk, "observation_date": "2019-11-01", "value": "0.500000"}
    ]


def test_bundle_vintage_reports_a_series_fred_cannot_supply(admin_client, bundle, fred_api_key, vintages_on):
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rs:
        rs.add(
            responses.GET, FRED_OBSERVATIONS_URL, match=[vintage_matcher("TESTM")],
            json=vintage_body(("2019-12-01", "97.25")),
        )
        rs.add(
            responses.GET, FRED_OBSERVATIONS_URL, match=[vintage_matcher("TESTQ")], status=400,
            json={"error_code": 400, "error_message": "Bad Request. The series does not exist in ALFRED but may exist in FRED."},
        )
        r = admin_client.get(BUNDLE_URL, {"vintage_date": "2020-01-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["transform"]["vintage_date"] == "2020-01-01"
    assert by_series(body, "TESTM") == {"2019-12-01": "97.250000"}
    assert by_series(body, "TESTQ") == {}
    quarterly = body["series"][1]
    assert quarterly["output_frequency"] is None
    assert quarterly["error"].startswith("TESTQ as of 2020-01-01: FRED answered 400: Bad Request.")
    assert "test-fred-key" not in r.content.decode()


def test_vintage_errors_on_one_series_are_a_502_without_the_key(admin_client, bundle, fred_api_key, vintages_on):
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rs:
        rs.add(responses.GET, FRED_OBSERVATIONS_URL, match=[vintage_matcher("TESTM")], status=404, body="nope")
        r = admin_client.get(OBS_URL, {"series": bundle["monthly"].pk, "vintage_date": "2020-01-01"})
    assert r.status_code == 502
    assert r.json()["detail"] == "TESTM as of 2020-01-01: FRED answered 404"
    assert "test-fred-key" not in r.content.decode()


def test_only_staff_can_make_a_request_fetch_a_vintage(api_client, bundle, fred_api_key, vintages_on):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rs:  # nothing registered
        single = api_client.get(OBS_URL, {"series": bundle["monthly"].pk, "vintage_date": "2020-01-01"})
        many = api_client.get(BUNDLE_URL, {"vintage_date": "2020-01-01"})
        assert len(rs.calls) == 0
    assert single.status_code == 403
    assert "not stored yet" in single.json()["detail"]
    assert many.status_code == 200
    assert many.json()["count"] == 0
    assert all("not stored yet" in s["error"] for s in many.json()["series"])
    assert not SeriesVintageObservation.objects.exists()


@pytest.mark.parametrize("value", ["2020-13-01", "yesterday", "2999-01-01"])
def test_a_malformed_or_future_vintage_date_is_a_400(api_client, bundle, vintages_on, value):
    r = api_client.get(BUNDLE_URL, {"vintage_date": value})
    assert r.status_code == 400
    assert "vintage date" in r.json()["detail"]
