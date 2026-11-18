from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass
class ObservationPoint:
    observation_date: date
    value: Decimal
    # The real-time period the provider reported for the value (FRED/ALFRED vintages).
    realtime_start: date | None = None
    realtime_end: date | None = None


class PublicDataProvider(Protocol):
    provider_slug: str

    def fetch_series_observations(
        self,
        external_id: str,
        observation_start: date | None = None,
        *,
        realtime_start: date | None = None,
        realtime_end: date | None = None,
    ) -> tuple[list[ObservationPoint], str]: ...
