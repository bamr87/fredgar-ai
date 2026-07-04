"""Publish pipeline for the public static mirror.

One entry point (used by ``manage.py publish_static_site`` and the GitHub Pages
workflow) that syncs a curated set of companies from SEC EDGAR — submissions,
XBRL facts, derived metrics, and (optionally) leadership — then renders the
static site with :func:`warehouse.services.static_site.generate_site`.

SEC fair-access: requests are paced with a configurable delay and every fetch
goes through the DB-first payload cache, so re-runs are cheap. One company
failing never aborts the whole publish — it is reported in the summary instead.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Iterable

from warehouse.models import Company
from warehouse.services.static_site import generate_site

logger = logging.getLogger(__name__)

# Default publish set: a small, liquid, cross-sector cohort that keeps the build
# well under SEC rate limits. Override with --tickers / the workflow input.
DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "JPM",
    "V",
    "JNJ",
    "UNH",
    "XOM",
    "PG",
    "WMT",
    "COST",
    "KO",
]


def sync_company_for_site(
    ticker: str,
    *,
    user_agent_email: str | None = None,
    leadership_limit: int = 10,
    force_refresh: bool = False,
) -> Company:
    """Sync everything one company's static page needs (filings, facts, metrics,
    leadership). Leadership is best-effort — the page renders without it."""
    from warehouse.services.edgar.metrics import compute_derived_metrics
    from warehouse.services.edgar.sync import EdgarSyncService

    company, _ = EdgarSyncService.get_or_create_company_from_edgar(
        ticker=ticker,
        cik_raw=None,
        name_override=None,
        user_agent_email=user_agent_email,
    )
    EdgarSyncService.sync_submissions(
        company, user_agent_email=user_agent_email, force_refresh=force_refresh
    )
    EdgarSyncService.sync_facts(
        company, user_agent_email=user_agent_email, force_refresh=force_refresh
    )
    compute_derived_metrics(company)
    if leadership_limit > 0:
        from warehouse.services.leadership import sync_leadership

        try:
            sync_leadership(company, user_agent_email=user_agent_email, limit=leadership_limit)
        except Exception as exc:  # noqa: BLE001 - leadership must not block the publish
            logger.warning("leadership sync failed for %s: %s", ticker, exc)
    return company


def sync_macro_for_site(*, delay: float = 0.5, days_back: int = 365 * 20) -> bool:
    """Best-effort FRED bundle sync so the static site can publish macro pages.

    Requires ``FRED_API_KEY``; silently skipped without it (the site renders
    whatever series data is already warehoused, or omits the macro section
    entirely). A failing sync never blocks the company publish.
    """
    if not os.getenv("FRED_API_KEY"):
        logger.info(
            "FRED_API_KEY not set — skipping macro sync (macro pages render only if data exists)"
        )
        return False
    from django.core.management import call_command

    try:
        call_command("refresh_series_bundles", delay=delay, days_back=days_back)
    except Exception as exc:  # noqa: BLE001 - macro must not block the publish
        logger.warning("macro (FRED) sync failed: %s", exc)
        return False
    return True


def publish_site(
    tickers: Iterable[str],
    output_dir: str | Path,
    *,
    sync: bool = True,
    delay: float = 0.4,
    user_agent_email: str | None = None,
    leadership_limit: int = 10,
    force_refresh: bool = False,
    macro: bool = True,
    base_url: str | None = None,
    app_url: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Sync ``tickers`` (unless ``sync=False``) and render the static site.

    ``macro=True`` additionally syncs the FRED series bundles when a
    ``FRED_API_KEY`` is available (skipped otherwise); the macro section renders
    from whatever series data ends up warehoused. Returns the ``generate_site``
    summary plus ``companies`` (published count) and ``errors`` (ticker ->
    message for companies that were skipped).
    """
    companies: list[Company] = []
    seen_pks: set[int] = set()
    errors: dict[str, str] = {}

    for raw in tickers:
        ticker = raw.strip().upper()
        if not ticker:
            continue
        if sync:
            try:
                company = sync_company_for_site(
                    ticker,
                    user_agent_email=user_agent_email,
                    leadership_limit=leadership_limit,
                    force_refresh=force_refresh,
                )
            except Exception as exc:  # noqa: BLE001 - keep publishing the rest
                errors[ticker] = str(exc)[:500]
                logger.warning("skipping %s: %s", ticker, exc)
                continue
            time.sleep(max(0.0, delay))
        else:
            found = Company.objects.filter(ticker=ticker).first()
            if found is None:
                errors[ticker] = "not in warehouse (rerun without skipping sync)"
                continue
            company = found
        if company.pk not in seen_pks:
            seen_pks.add(company.pk)
            companies.append(company)

    if not companies:
        raise RuntimeError(f"No companies to publish (errors: {errors or 'none'})")

    macro_synced = sync_macro_for_site(delay=delay) if (macro and sync) else False

    summary = generate_site(
        companies, output_dir, base_url=base_url, app_url=app_url, source_url=source_url
    )
    summary["companies"] = len(companies)
    summary["errors"] = errors
    summary["macro_synced"] = macro_synced
    return summary
