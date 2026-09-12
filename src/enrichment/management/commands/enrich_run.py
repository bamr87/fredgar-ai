"""Iterate a dataset through the provider graph."""

import json

from django.conf import settings
from django.core.management.base import BaseCommand

from enrichment.core.runner import Budget, Context, Runner
from enrichment.pipeline import default_registry
from enrichment.services import refresh_providers

from ._base import add_dataset_argument, get_dataset


class Command(BaseCommand):
    help = (
        "Run enrichment providers over a dataset. Resumable: every (record, provider) "
        "attempt is checkpointed, so re-running only does what has not been done."
    )

    def add_arguments(self, parser):
        add_dataset_argument(parser)
        parser.add_argument("--limit", type=int, help="Only the first N records")
        parser.add_argument("--only", nargs="*", help="Run only these providers")
        parser.add_argument(
            "--refresh",
            nargs="*",
            help=(
                "Discard these providers' claims and checkpoints first, so they "
                "genuinely re-run. Every other provider's findings are untouched."
            ),
        )
        parser.add_argument("--workers", type=int, default=4)
        parser.add_argument("--max-fetch", type=int, default=5000, help="Page-fetch cap")
        parser.add_argument("--max-search", type=int, default=1000, help="Search-query cap")
        parser.add_argument("--max-api", type=int, default=50000, help="API-call cap")
        parser.add_argument("--search", action="store_true", help="Enable the web-search provider")
        parser.add_argument(
            "--no-web", action="store_true", help="Disable site fetching entirely (offline run)"
        )
        parser.add_argument("--searx", help="SearXNG base URL to use as the search backend")
        parser.add_argument(
            "--user-agent-email",
            default="",
            help="Contact email for SEC's required User-Agent (default: USER_AGENT_EMAIL)",
        )

    def handle(self, *args, **options):
        dataset = get_dataset(options["dataset"])

        if options.get("refresh"):
            dropped = refresh_providers(dataset, options["refresh"])
            self.stdout.write(
                self.style.WARNING(
                    f"Refreshed {', '.join(options['refresh'])}: dropped "
                    f"{dropped['claims']:,} claims and {dropped['runs']:,} checkpoints."
                )
            )

        registry = default_registry(
            enable_search=options["search"], enable_web=not options["no_web"]
        )

        ctx = Context(
            budget=Budget(
                max_fetch=options["max_fetch"],
                max_search=options["max_search"],
                max_api=options["max_api"],
            ),
            user_agent_email=options["user_agent_email"]
            or getattr(settings, "SEC_USER_AGENT_EMAIL", "")
            or None,
        )
        # Providers that index the whole list need to know which list.
        ctx.shared["dataset"] = dataset

        if not options["no_web"]:
            ctx.http = _http(ctx.user_agent_email)
        if options["search"] and options["searx"]:
            ctx.shared["search"] = _searx_backend(options["searx"])

        runner = Runner(registry, dataset, ctx, workers=options["workers"])
        if runner.workers != options["workers"]:
            self.stdout.write(
                self.style.WARNING(f"Using {runner.workers} worker(s): SQLite serialises writers.")
            )

        stats = runner.run(only=options["only"], limit=options["limit"])
        self.stdout.write(json.dumps(stats, indent=2, default=str))


def _http(user_agent_email: str | None):
    """Minimal HTTP client for site probing — stdlib, rate-limited, size-capped."""
    from enrichment.sources import Http

    contact = user_agent_email or "set USER_AGENT_EMAIL"
    return Http(per_second=3.0, ua=f"fredgar-enrichment/1.0 (contact: {contact})")


def _searx_backend(base: str):
    """Any SearXNG instance works as a search backend; swap for Brave or your own."""
    import json as _json
    import urllib.parse
    import urllib.request

    def search(q: str, n: int = 8):
        url = f"{base.rstrip('/')}/search?" + urllib.parse.urlencode({"q": q, "format": "json"})
        req = urllib.request.Request(url, headers={"User-Agent": "fredgar-enrichment/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - operator-supplied URL
            data = _json.loads(r.read())
        return [
            {"url": x.get("url"), "title": x.get("title"), "snippet": x.get("content")}
            for x in data.get("results", [])[:n]
        ]

    return search
