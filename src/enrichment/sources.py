"""HTTP for the open-web providers.

Deliberately not ``requests``: this client fetches arbitrary third-party domains
discovered from a list, so it caps the response size, refuses anything that is
not a document, and never follows a redirect off http(s). SEC and FRED traffic
does *not* go through here — those have their own clients in ``sec_edgar`` and
``public_data``, with the rate limits and User-Agent rules each publisher
requires.
"""

from __future__ import annotations

import gzip
import time
import urllib.error
import urllib.request

DEFAULT_UA = "fredgar-enrichment/1.0 (contact: set USER_AGENT_EMAIL)"

# A homepage that is larger than this is not a homepage. Without a cap, one
# misconfigured server streaming gigabytes stalls a whole run.
MAX_BYTES = 4 * 1024 * 1024


class Http:
    """Minimal polite client: fixed delay, retry with backoff, honest errors."""

    def __init__(
        self,
        per_second: float = 3.0,
        ua: str = DEFAULT_UA,
        *,
        timeout: float = 10.0,
        tries: int = 1,
    ):
        self.min_gap = 1.0 / per_second if per_second > 0 else 0.0
        self.ua = ua
        self.timeout = timeout
        self.tries = tries
        self._last = 0.0

    def get(self, url: str, accept: str = "application/json", tries: int | None = None) -> bytes:
        """Fetch one URL.

        Defaults to a single attempt with a short timeout, because the dominant
        use is probing *guessed* domains: most failures here are NXDOMAIN or a
        parked host, neither of which a retry can fix, and the framework's own
        budget is what protects the run — not per-request persistence. Raise
        `tries` for endpoints where a transient failure is worth waiting out.
        """
        tries = self.tries if tries is None else tries
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError(f"refusing non-http URL: {url[:80]}")

        for attempt in range(tries):
            gap = self.min_gap - (time.monotonic() - self._last)
            if gap > 0:
                time.sleep(gap)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.ua,
                    "Accept": accept,
                    "Accept-Encoding": "gzip, deflate",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 - scheme checked above
                    self._last = time.monotonic()
                    raw = r.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES:
                        raise ValueError(f"response exceeds {MAX_BYTES} bytes: {url[:80]}")
                    if r.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    return raw
            except Exception:
                self._last = time.monotonic()
                if attempt == tries - 1:
                    raise
                time.sleep(2**attempt)  # 1s, 2s
        raise RuntimeError("unreachable")  # pragma: no cover
