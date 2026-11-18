"""ALFRED vintages: the FRED provider's real-time params and `sync_series_vintage` (FR-MAC-001)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
import responses
from django.core.management import call_command
from django.core.management.base import CommandError
from responses import matchers

from public_data.models import ExternalSeries
from public_data.providers.fred import FRED_OBSERVATIONS_URL, FRED_SERIES_INFO_URL, FredProvider
from warehouse.models import SeriesVintageObservation

AS_OF = {"realtime_start": "2020-01-01", "realtime_end": "2020-01-01"}
KEY = {"api_key": "test-fred-key", "file_type": "json"}


def observations(*rows):
    return {"observations": [{**AS_OF, "date": d, "value": v} for d, v in rows]}


@pytest.fixture
def vintages_on(settings):
    settings.ENABLE_FRED_VINTAGES = True


def test_provider_sends_the_real_time_period_and_reads_it_back(fred_api_key):
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rs:
        rs.add(
            responses.GET,
            FRED_OBSERVATIONS_URL,
            match=[matchers.query_param_matcher({"series_id": "GDPC1", **AS_OF, **KEY})],
            json=observations(("2019-07-01", "19141.744")),
        )
        points, source = FredProvider().fetch_series_observations(
            "GDPC1", realtime_start=date(2020, 1, 1), realtime_end=date(2020, 1, 1)
        )
    assert points[0].observation_date == date(2019, 7, 1)
    assert points[0].value == Decimal("19141.744")
    assert (points[0].realtime_start, points[0].realtime_end) == (date(2020, 1, 1), date(2020, 1, 1))
    assert "realtime_start=2020-01-01" in source
    assert "api_key" not in source


@pytest.mark.django_db
def test_command_refuses_while_vintages_are_off():
    with pytest.raises(CommandError, match="ENABLE_FRED_VINTAGES"):
        call_command("sync_series_vintage", series="GDPC1", as_of="2020-01-01")


@pytest.mark.django_db
def test_command_stores_a_vintage_once(fred_api_key, vintages_on):
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rs:
        rs.add(
            responses.GET,
            FRED_SERIES_INFO_URL,
            match=[matchers.query_param_matcher({"series_id": "GDPC1", **KEY})],
            json={"seriess": [{"id": "GDPC1", "title": "Real GDP", "frequency_short": "Q", "frequency": "Quarterly", "units": "Billions"}]},
        )
        rs.add(
            responses.GET,
            FRED_OBSERVATIONS_URL,
            match=[matchers.query_param_matcher({"series_id": "GDPC1", **AS_OF, **KEY})],
            json=observations(("2019-04-01", "19021.86"), ("2019-07-01", "19141.744")),
        )
        out = StringIO()
        call_command("sync_series_vintage", series="GDPC1", as_of="2020-01-01", stdout=out)
    assert "stored 2 observations" in out.getvalue()
    series = ExternalSeries.objects.get(provider="fred", external_id="GDPC1")
    rows = SeriesVintageObservation.objects.filter(series=series, vintage_date=date(2020, 1, 1))
    assert rows.count() == 2

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rs:  # DB-first: no call
        again = StringIO()
        call_command("sync_series_vintage", series="GDPC1", as_of="2020-01-01", stdout=again)
        assert len(rs.calls) == 0
    assert "already stored (2 observations)" in again.getvalue()


@pytest.mark.django_db
def test_command_reports_a_fred_failure_without_the_key(fred_api_key, vintages_on):
    ExternalSeries.objects.create(provider="fred", external_id="GDPC1", title="Real GDP")
    with responses.RequestsMock(assert_all_requests_are_fired=True) as rs:
        rs.add(
            responses.GET,
            FRED_OBSERVATIONS_URL,
            status=400,
            json={"error_code": 400, "error_message": "Bad Request. Variable realtime_start is not valid."},
        )
        with pytest.raises(CommandError) as excinfo:
            call_command("sync_series_vintage", series="GDPC1", as_of="2020-01-01")
    message = str(excinfo.value)
    assert message == "GDPC1 as of 2020-01-01: FRED answered 400: Bad Request. Variable realtime_start is not valid."
    assert "test-fred-key" not in message
    assert not SeriesVintageObservation.objects.exists()


@pytest.mark.django_db
def test_command_refuses_a_future_date(vintages_on):
    with pytest.raises(CommandError, match="in the future"):
        call_command("sync_series_vintage", series="GDPC1", as_of="2999-01-01")
