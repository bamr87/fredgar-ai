"""FRED API client (https://fred.stlouisfed.org/docs/api/fred/)."""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests

from public_data.providers.base import ObservationPoint

logger = logging.getLogger(__name__)

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES_INFO_URL = "https://api.stlouisfed.org/fred/series"

# FRED allows 120 requests/minute; back off politely on 429/5xx.
_MAX_RETRIES = 4
_BACKOFF_SECONDS = 8


class FredProvider:
    provider_slug = "fred"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("FRED_API_KEY") or ""

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY is not set")
        q = {**params, "api_key": self.api_key, "file_type": "json"}
        for attempt in range(_MAX_RETRIES):
            r = requests.get(url, params=q, timeout=60)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES - 1:
                wait = _BACKOFF_SECONDS * (attempt + 1)
                logger.warning("FRED %s on %s; backing off %ss", r.status_code, params.get("series_id"), wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError("FRED request failed after retries")  # pragma: no cover

    def series_info(self, series_id: str) -> dict[str, Any]:
        return self._get(
            FRED_SERIES_INFO_URL,
            {"series_id": series_id},
        )

    def fetch_series_observations(
        self,
        external_id: str,
        observation_start: date | None = None,
        *,
        realtime_start: date | None = None,
        realtime_end: date | None = None,
    ) -> tuple[list[ObservationPoint], str]:
        """Observations of a series; ``realtime_start``/``realtime_end`` ask ALFRED for a past vintage."""
        params: dict[str, Any] = {"series_id": external_id}
        if observation_start:
            params["observation_start"] = observation_start.isoformat()
        realtime: dict[str, str] = {}
        if realtime_start:
            realtime["realtime_start"] = realtime_start.isoformat()
        if realtime_end:
            realtime["realtime_end"] = realtime_end.isoformat()
        data = self._get(FRED_OBSERVATIONS_URL, {**params, **realtime})
        out: list[ObservationPoint] = []
        for row in data.get("observations") or []:
            if row.get("value") in (".", None, ""):
                continue
            try:
                d = datetime.strptime(row["date"], "%Y-%m-%d").date()
                out.append(
                    ObservationPoint(
                        d,
                        Decimal(str(row["value"])),
                        realtime_start=_iso_date(row.get("realtime_start")),
                        realtime_end=_iso_date(row.get("realtime_end")),
                    )
                )
            except (ValueError, KeyError, TypeError) as e:
                logger.debug("skip row %s: %s", row, e)
        source = f"{FRED_OBSERVATIONS_URL}?{urlencode({'series_id': external_id, **realtime})}"
        return out, source


def _iso_date(value: Any) -> date | None:
    """A FRED ``YYYY-MM-DD`` field as a date; None when absent or malformed."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
