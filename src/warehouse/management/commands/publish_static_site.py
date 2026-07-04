"""Sync a curated company set from SEC EDGAR and render the public static site.

This is the one command the GitHub Pages workflow runs; locally it does the same
end-to-end build (``--skip-sync`` renders from already-warehoused data only).
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from warehouse.services.static_site_publish import DEFAULT_TICKERS, publish_site


class Command(BaseCommand):
    help = (
        "Sync companies from SEC EDGAR (submissions, facts, metrics, leadership) and "
        "render the static public site — the GitHub Pages publish pipeline."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tickers",
            default=",".join(DEFAULT_TICKERS),
            help=f"Comma-separated tickers to publish (default: {','.join(DEFAULT_TICKERS)})",
        )
        parser.add_argument(
            "--output", default=None, help="Output directory (default: <repo>/site)"
        )
        parser.add_argument(
            "--skip-sync",
            action="store_true",
            help="Render from warehouse data only — no SEC network calls.",
        )
        parser.add_argument(
            "--sync-only",
            action="store_true",
            help="Sync the warehouse (SEC + FRED) without rendering — the "
            "dataset-refresh path; render later with --skip-sync.",
        )
        parser.add_argument(
            "--all-warehouse",
            action="store_true",
            help="Render every company already in the warehouse instead of a "
            "ticker list (implies --skip-sync; the dataset defines the site).",
        )
        parser.add_argument(
            "--delay", type=float, default=0.4, help="Seconds between companies during sync."
        )
        parser.add_argument(
            "--leadership-limit",
            type=int,
            default=10,
            help="Max ownership filings per company for leadership extraction (0 disables).",
        )
        parser.add_argument(
            "--force-refresh",
            action="store_true",
            help="Bypass the EdgarSecPayload cache and refetch from SEC.",
        )
        parser.add_argument(
            "--base-url",
            default=None,
            help="Canonical public URL (enables sitemap.xml/robots.txt); "
            "default: STATIC_SITE_BASE_URL.",
        )
        parser.add_argument(
            "--app-url",
            default=None,
            help="Interactive app URL to cross-link; default: STATIC_SITE_APP_URL.",
        )
        parser.add_argument(
            "--user-agent-email",
            default=None,
            help="SEC contact email override (default: USER_AGENT_EMAIL / settings).",
        )
        parser.add_argument(
            "--skip-macro",
            action="store_true",
            help="Skip the FRED bundle sync (macro pages still render if series "
            "data is already warehoused; without data the section is omitted).",
        )

    def handle(self, *args, **options):
        if options["skip_sync"] and options["sync_only"]:
            raise CommandError("--skip-sync and --sync-only are mutually exclusive.")
        if options["all_warehouse"] and options["sync_only"]:
            raise CommandError("--all-warehouse and --sync-only are mutually exclusive.")
        tickers: list[str] | None = [t for t in options["tickers"].split(",") if t.strip()]
        if options["all_warehouse"]:
            tickers = None
        elif not tickers:
            raise CommandError("Provide at least one ticker via --tickers.")
        output = options.get("output") or str(Path(settings.BASE_DIR).parent / "site")

        try:
            summary = publish_site(
                tickers,
                output,
                sync=not (options["skip_sync"] or options["all_warehouse"]),
                render=not options["sync_only"],
                delay=options["delay"],
                user_agent_email=options.get("user_agent_email"),
                leadership_limit=options["leadership_limit"],
                force_refresh=options["force_refresh"],
                macro=not options["skip_macro"],
                base_url=options.get("base_url"),
                app_url=options.get("app_url"),
            )
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        for ticker, msg in summary["errors"].items():
            self.stdout.write(self.style.WARNING(f"skipped {ticker}: {msg}"))
        if options["sync_only"]:
            macro_note = "with" if summary["macro_synced"] else "without"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Warehoused {summary['companies']} compan(y/ies) {macro_note} a FRED "
                    "macro sync (no rendering — publish later with --skip-sync)."
                )
            )
            return
        macro_note = (
            f", {summary['macro_series']} macro series in {summary['macro_bundles']} bundle(s)"
            if summary.get("macro_bundles")
            else ", no macro data (set FRED_API_KEY to publish FRED series)"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Published {summary['pages']} page(s) for {summary['companies']} "
                f"compan(y/ies){macro_note} -> {summary['output_dir']} "
                f"(as of {summary['generated_at']})"
            )
        )
