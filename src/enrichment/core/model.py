"""The three objects the whole framework is built from.

Record  - one row of the input list, plus everything learned about it.
Claim   - one assertion by one provider, with the evidence that backs it.
Evidence- where a claim came from, concretely enough to re-check by hand.

The critical rule: providers NEVER write to a record's fields. They emit
claims. Resolution happens later, once, in one place. This is what keeps
"my list says X but the website says Y" a question you can answer instead of
a bug you discover in a board meeting.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json

# `field` is imported under an alias because Claim has an attribute called
# `field`, which shadows it inside the class body.
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from typing import Any


def NOW() -> str:
    """UTC timestamp, second resolution — every Evidence carries one."""
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Evidence:
    """Where a claim came from. A claim without this is a rumour."""

    url: str | None = None  # the page/endpoint that asserted it
    snippet: str | None = None  # the text that says so, verbatim, trimmed
    locator: str | None = None  # xpath / json path / xbrl tag / csv row
    retrieved_at: str = dataclass_field(default_factory=NOW)

    def digest(self) -> str:
        return hashlib.sha1(f"{self.url}|{self.locator}|{self.snippet}".encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Claim:
    """One provider's assertion about one field of one record."""

    field: str  # 'website' | 'legal_name' | 'employees' | ...
    value: Any
    confidence: float  # 0-1, the provider's own honest estimate
    provider: str
    evidence: Evidence = dataclass_field(default_factory=Evidence)
    # Set when a provider has actively checked the value rather than proposed it.
    # A guessed domain and a domain whose homepage names the company are both
    # 'website' claims; only one of them is verified.
    verified: bool = False

    def key(self) -> tuple:
        return (self.field, json.dumps(self.value, sort_keys=True, default=str))


@dataclass
class Record:
    """A row in flight. `fields` holds resolved values; `claims` holds the raw."""

    record_id: int
    source_key: str  # the original name/identifier from the list
    fields: dict[str, Any] = dataclass_field(default_factory=dict)
    claims: list[Claim] = dataclass_field(default_factory=list)
    ran: set[str] = dataclass_field(default_factory=set)  # provider names already executed

    # --- read side ------------------------------------------------------------
    def get(self, name: str, default=None):
        return self.fields.get(name, default)

    def has(self, *names: str) -> bool:
        return all(self.fields.get(n) not in (None, "", [], {}) for n in names)

    def available(self) -> frozenset[str]:
        return frozenset(k for k, v in self.fields.items() if v not in (None, "", [], {}))

    # --- write side -----------------------------------------------------------
    def add(self, claim: Claim) -> None:
        self.claims.append(claim)

    def claims_for(self, name: str) -> list[Claim]:
        return [c for c in self.claims if c.field == name]

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "source_key": self.source_key,
            "fields": dict(self.fields),
            "claims": [asdict(c) for c in self.claims],
        }
