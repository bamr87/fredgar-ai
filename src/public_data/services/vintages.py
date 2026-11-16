"""ALFRED vintages: a FRED series as it was known on a past date (FR-MAC-001), DB-first.

Behind ``ENABLE_FRED_VINTAGES``. A vintage is fetched from FRED once, with
``realtime_start = realtime_end =`` the vintage date, stored in
``warehouse.SeriesVintageObservation`` under that date, and read from the database after
that. ``manage.py sync_series_vintage`` and ``?vintage_date=`` on the observation
endpoints both come through here. Fetching calls FRED and writes rows, so it is a sync
action: the API lets only staff trigger it, and anyone reads what is stored.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from public_data.models import ExternalSeries
from public_data.providers.fred import FredProvider
from public_data.services.transforms import TransformError
from warehouse.models import SeriesVintageObservation

logger = logging.getLogger(__name__)


class VintageError(TransformError):
    """A vintage request that cannot be served: the feature is off, or the date is invalid."""


class VintageUnavailable(RuntimeError):
    """The vintage is not stored and FRED could not supply it. The message is safe to show."""


class VintageNotStored(VintageUnavailable):
    """The vintage is not stored, and this caller may not fetch it."""


def check_vintage_date(raw: str | date) -> date:
    """The vintage date of a request, validated; raises VintageError.

    Refused while ``ENABLE_FRED_VINTAGES`` is off, when malformed and when in the future
    (FRED has no vintage of a day that has not happened).
    """
    if not settings.ENABLE_FRED_VINTAGES:
        raise VintageError("vintages are disabled: set ENABLE_FRED_VINTAGES=true to use them")
    if isinstance(raw, date):
        as_of = raw
    else:
        try:
            as_of = date.fromisoformat(raw.strip())
        except ValueError:
            raise VintageError(f"vintage date '{raw}' is not a date (YYYY-MM-DD)") from None
    if as_of > timezone.localdate():
        raise VintageError(f"vintage date {as_of.isoformat()} is in the future")
    return as_of


def stored_vintage(series: ExternalSeries, as_of: date) -> list[tuple[date, Decimal]]:
    """The stored observations of ``series`` as of ``as_of``, oldest first (empty if not fetched)."""
    rows = SeriesVintageObservation.objects.filter(series=series, vintage_date=as_of)
    return list(rows.order_by("observation_date").values_list("observation_date", "value"))


@transaction.atomic
def sync_series_vintage(series: ExternalSeries, as_of: date) -> int:
    """Fetch ``series`` as FRED published it on ``as_of`` and store it; the observation count.

    Raises VintageUnavailable when the series is not a FRED series or FRED fails. The
    message never carries the request URL, which holds the API key.
    """
    if series.provider != "fred":
        raise VintageUnavailable(
            f"{series.provider}:{series.external_id} has no vintages; only FRED series do"
        )
    try:
        points, source_url = FredProvider().fetch_series_observations(
            series.external_id, realtime_start=as_of, realtime_end=as_of
        )
    except (requests.RequestException, RuntimeError) as exc:
        detail = _describe(exc)
        logger.warning("FRED vintage %s@%s failed: %s", series.external_id, as_of, detail)
        raise VintageUnavailable(
            f"{series.external_id} as of {as_of.isoformat()}: {detail}"
        ) from None
    for p in points:
        SeriesVintageObservation.objects.update_or_create(
            series=series,
            vintage_date=as_of,
            observation_date=p.observation_date,
            defaults={
                "value": p.value,
                "realtime_start": p.realtime_start or as_of,
                "realtime_end": p.realtime_end or as_of,
                "source_url": source_url[:1024],
            },
        )
    return len(points)


def vintage_points(
    series: ExternalSeries, as_of: date, *, fetch_missing: bool
) -> list[tuple[date, Decimal]]:
    """``series`` as known on ``as_of``: the stored vintage, else one FRED fetch (DB-first).

    Without ``fetch_missing`` a vintage that is not stored raises VintageNotStored.
    """
    stored = stored_vintage(series, as_of)
    if stored:
        return stored
    if not fetch_missing:
        raise VintageNotStored(
            f"{series.external_id} as of {as_of.isoformat()} is not stored yet; a staff "
            "user's request or manage.py sync_series_vintage fetches it from FRED"
        )
    sync_series_vintage(series, as_of)
    return stored_vintage(series, as_of)


def _describe(exc: BaseException) -> str:
    """What went wrong with a FRED call, without the URL (it carries the API key)."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            body = exc.response.json()
        except ValueError:
            body = None
        message = body.get("error_message") if isinstance(body, dict) else None
        status = exc.response.status_code
        return f"FRED answered {status}: {message}" if message else f"FRED answered {status}"
    if isinstance(exc, requests.RequestException):
        return "FRED could not be reached"
    return str(exc)
