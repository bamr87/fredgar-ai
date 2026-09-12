import logging

from django.db import connection
from django.db.models import Count
from django.db.models.functions import TruncYear
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from enrichment.services import dataset_report
from public_data.models import ExternalSeries, SeriesBundle, SeriesObservation
from sec_edgar.exceptions import EdgarRateLimitError, EdgarResolutionError
from sec_edgar.services.sic_reference import (
    search_sic_codes,  # reference-data tier (not EDGAR sync)
)
from warehouse.models import (
    Company,
    DerivedMetric,
    EdgarEntitySyncState,
    EnrichmentDataset,
    EnrichmentRecord,
    Fact,
    Filing,
    FilingDocument,
    LeadershipPosition,
    PeerGroup,
    Section,
    Table,
)
from warehouse.services.edgar.analytics import EdgarAnalyticsService
from warehouse.services.edgar.sync import EdgarSyncService

from ..filters import CompanyMetadataFilter, FactFilterSet
from ..sec_user_agent import sec_user_agent_email_from_request
from ..serializers import (
    CompanyMetadataSerializer,
    CompanySerializer,
    DerivedMetricSerializer,
    EnrichmentClaimSerializer,
    EnrichmentDatasetSerializer,
    EnrichmentGoldenFieldSerializer,
    EnrichmentRecordSerializer,
    ExternalSeriesSerializer,
    FactSerializer,
    FilingSerializer,
    PeerGroupSerializer,
    SectionSerializer,
    SeriesBundleSerializer,
    SeriesObservationSerializer,
    TableSerializer,
)
from ..throttles import SecActionThrottle

logger = logging.getLogger(__name__)

# Responsible-use note attached to every LLM leadership-analysis response.
LEADERSHIP_AI_CAVEAT = (
    "LLM-extracted narrative, grounded only in the company's SEC filing excerpts. "
    "Quotes are verbatim from those filings; initiatives cite their source passage. "
    "This is NOT an approval rating or a character/competence judgment of any "
    "individual. Verify against the cited filings. See docs/leadership-methodology.md."
)


def _wants_async(request) -> bool:
    """True if the caller requested background processing (``?async=true``)."""
    raw = request.query_params.get("async") or request.data.get("async") or ""
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


class HealthView(APIView):
    """Liveness probe; does not check the database."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes: list = []  # liveness must never be throttled

    def get(self, request):
        return Response({"status": "ok"})


class HealthReadyView(APIView):
    """Readiness: verifies app can reach the default database."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes: list = []  # readiness must never be throttled

    def get(self, request):
        try:
            connection.ensure_connection()
        except Exception:
            return Response(
                {"status": "unready", "checks": {"database": False}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok", "checks": {"database": True}})


class TaskStatusView(APIView):
    """Celery task state for an async job dispatched by a sync action."""

    def get(self, request, task_id):
        from celery.result import AsyncResult

        res = AsyncResult(task_id)
        ready = res.ready()
        payload: dict = {"task_id": task_id, "status": res.status, "ready": ready}
        if ready and res.successful():
            result = res.result
            payload["result"] = (
                result if isinstance(result, (int, float, str, dict, list)) else str(result)
            )
        elif ready:
            payload["error"] = str(res.result)
        return Response(payload)


class SicCodesReferenceView(APIView):
    """SEC SIC master list (from ``data/reference/sic_codes.json``) for lookup and autocomplete."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        qp = request.query_params
        try:
            lim = int(qp.get("limit", 50))
        except ValueError:
            lim = 50
        lim = max(1, min(lim, 200))
        code = (qp.get("code") or "").strip() or None
        q = (qp.get("q") or "").strip() or None
        rows = search_sic_codes(q=q, code=code, limit=lim)
        return Response({"count": len(rows), "results": rows})


class CompanyViewSet(viewsets.ModelViewSet):
    """CRUD for ``Company`` plus EDGAR resolution, sync, and read-only analytics helpers."""

    queryset = Company.objects.all().order_by("name")
    serializer_class = CompanySerializer
    filterset_fields = ["ticker", "cik", "industry", "sic_code", "hq_state"]
    search_fields = ["name", "ticker", "cik"]

    @action(detail=False, methods=["get"], url_path="edgar-search")
    def edgar_search(self, request):
        """Search listed issuers (DB-backed ``ListedIssuer``; optional ``force_refresh`` refetches SEC file)."""
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response(
                {"detail": "Query must be at least 2 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            lim = int(request.query_params.get("limit", 50))
        except ValueError:
            lim = 50
        lim = max(1, min(lim, 100))
        force_refresh = request.query_params.get("force_refresh", "").lower() in (
            "1",
            "true",
            "yes",
        )
        ua = sec_user_agent_email_from_request(request)
        try:
            matches = EdgarSyncService.search_edgar_directory(
                q,
                user_agent_email=ua,
                limit=lim,
                force_refresh=force_refresh,
            )
        except EdgarRateLimitError:
            return Response(
                {"detail": "SEC rate limit reached; try again shortly."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except Exception:
            logger.exception("edgar_search failed")
            return Response(
                {"detail": "Could not load SEC company directory."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        ciks = [m["cik"] for m in matches]
        existing = set(Company.objects.filter(cik__in=ciks).values_list("cik", flat=True))
        results = [{**m, "in_warehouse": m["cik"] in existing} for m in matches]
        return Response({"count": len(results), "results": results})

    @action(
        detail=False,
        methods=["post"],
        url_path="from-edgar",
        throttle_classes=[SecActionThrottle],
    )
    def from_edgar(self, request):
        """Create or return a warehouse Company from EDGAR directory (DB first, then SEC)."""
        ticker = (request.data.get("ticker") or "").strip().upper() or None
        cik_raw = request.data.get("cik")
        name_override = (request.data.get("name") or "").strip() or None
        if not ticker and not cik_raw:
            return Response(
                {"detail": "Provide cik and/or ticker."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ua = sec_user_agent_email_from_request(request)
        try:
            company, created = EdgarSyncService.get_or_create_company_from_edgar(
                ticker=ticker,
                cik_raw=cik_raw,
                name_override=name_override,
                user_agent_email=ua,
            )
        except EdgarResolutionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except EdgarRateLimitError:
            return Response(
                {"detail": "SEC rate limit reached; try again shortly."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("from_edgar failed")
            return Response(
                {"detail": "Could not resolve company from SEC."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            CompanySerializer(company).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="bulk-from-edgar-tickers",
        throttle_classes=[SecActionThrottle],
    )
    def bulk_from_edgar_tickers(self, request):
        """Insert missing ``Company`` rows from SEC company_tickers.json (bulk, no per-CIK API)."""
        update_existing = bool(request.data.get("update_existing"))
        refresh_sec_json = bool(request.data.get("refresh_sec_json"))
        ua = sec_user_agent_email_from_request(request)
        try:
            stats = EdgarSyncService.bulk_sync_companies_from_sec_tickers(
                user_agent_email=ua,
                update_existing=update_existing,
                refresh_sec_json=refresh_sec_json,
            )
        except EdgarRateLimitError:
            return Response(
                {"detail": "SEC rate limit reached; try again shortly."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except Exception:
            logger.exception("bulk_from_edgar_tickers failed")
            return Response(
                {"detail": "Bulk load failed."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(stats)

    @action(detail=True, methods=["post"], url_path="suggest-schema")
    def suggest_schema(self, request, pk=None):
        """Return static CRM-style field hints until filing-driven schema inference exists."""
        company = self.get_object()
        base_fields = [
            "industry",
            "management",
            "headquarters",
            "locations",
            "business_units",
            "product_types",
            "size",
        ]
        suggested = {
            "required": ["industry", "headquarters"],
            "recommended": base_fields,
            "custom_candidates": [
                "esg_policies",
                "risk_factors",
                "major_customers",
                "competitors",
                "supply_chain_regions",
                "revenue_streams",
            ],
            "notes": "Heuristic schema hints; refine with filings + AI later.",
        }
        return Response({"company": company.id, "suggested_schema": suggested})

    @action(
        detail=True,
        methods=["post"],
        url_path="sync-submissions",
        throttle_classes=[SecActionThrottle],
    )
    def sync_submissions(self, request, pk=None):
        company = self.get_object()
        ua = sec_user_agent_email_from_request(request)
        if _wants_async(request):
            from warehouse.tasks import sync_submissions_task

            res = sync_submissions_task.delay(company.id, ua)
            return Response(
                {"company": company.id, "task_id": res.id, "status": "queued"},
                status=status.HTTP_202_ACCEPTED,
            )
        n = EdgarSyncService.sync_submissions(company, user_agent_email=ua)
        return Response({"company": company.id, "filings_processed": n})

    @action(
        detail=True,
        methods=["post"],
        url_path="sync-facts",
        throttle_classes=[SecActionThrottle],
    )
    def sync_facts(self, request, pk=None):
        company = self.get_object()
        ua = sec_user_agent_email_from_request(request)
        if _wants_async(request):
            from warehouse.tasks import sync_facts_task

            res = sync_facts_task.delay(company.id, ua)
            return Response(
                {"company": company.id, "task_id": res.id, "status": "queued"},
                status=status.HTTP_202_ACCEPTED,
            )
        count = EdgarSyncService.sync_facts(company, user_agent_email=ua)
        return Response({"company": company.id, "facts_loaded": count})

    @action(detail=True, methods=["get"], url_path="edgar-sync-status")
    def edgar_sync_status(self, request, pk=None):
        company = self.get_object()
        state = EdgarEntitySyncState.objects.filter(company_id=company.id).first()
        return Response(
            {
                "company": company.id,
                "submissions_synced_at": state.submissions_synced_at if state else None,
                "facts_synced_at": state.facts_synced_at if state else None,
                "last_error": (state.last_error[:500] if state and state.last_error else ""),
            }
        )

    @action(detail=True, methods=["get"], url_path="analytics/latest-by-concepts")
    def analytics_latest_by_concepts(self, request, pk=None):
        company = self.get_object()
        raw = (request.query_params.get("concepts") or "").strip()
        concepts = [c.strip() for c in raw.split(",") if c.strip()]
        if not concepts:
            return Response(
                {"detail": "Provide concepts as comma-separated XBRL tags."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        taxonomy = (request.query_params.get("taxonomy") or "us-gaap").strip() or "us-gaap"
        data = EdgarAnalyticsService.latest_by_concepts(company, concepts, taxonomy=taxonomy)
        return Response({"company": company.id, "taxonomy": taxonomy, "values": data})

    @action(detail=True, methods=["get"], url_path="analytics/timeseries")
    def analytics_timeseries(self, request, pk=None):
        company = self.get_object()
        # `concepts` (comma-separated priority chain) resolves a continuous series
        # across XBRL tag migrations; `concept` is the single-tag legacy form.
        raw_concepts = (request.query_params.get("concepts") or "").strip()
        concepts = [c.strip() for c in raw_concepts.split(",") if c.strip()]
        concept = (request.query_params.get("concept") or "").strip()
        if not concepts and concept:
            concepts = [concept]
        if not concepts:
            return Response(
                {"detail": "concept or concepts query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        taxonomy = (request.query_params.get("taxonomy") or "us-gaap").strip() or "us-gaap"
        annual = (request.query_params.get("annual") or "").strip().lower() in ("1", "true", "yes", "on")
        try:
            lim = int(request.query_params.get("limit", 80))
        except ValueError:
            lim = 80
        lim = max(1, min(lim, 500))
        series = EdgarAnalyticsService.timeseries_for_concepts(
            company, concepts, taxonomy=taxonomy, limit=lim, annual_only=annual
        )
        return Response(
            {"company": company.id, "concept": concepts[0], "concepts": concepts, "taxonomy": taxonomy, "series": series}
        )

    @action(detail=True, methods=["get"], url_path="statements")
    def statements(self, request, pk=None):
        """Curated financial-statement view (balance/income/cash-flow) from Facts."""
        from warehouse.services.edgar.statements import (
            available_statement_types,
            build_financial_statement,
        )

        company = self.get_object()
        st = (request.query_params.get("statement_type") or "").strip()
        taxonomy = (request.query_params.get("taxonomy") or "us-gaap").strip() or "us-gaap"
        if not st:
            return Response(
                {
                    "detail": "statement_type query parameter is required.",
                    "available": available_statement_types(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            data = build_financial_statement(company, st, taxonomy=taxonomy)
        except KeyError:
            return Response(
                {
                    "detail": f"Unknown statement_type '{st}'.",
                    "available": available_statement_types(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(data)

    @action(detail=True, methods=["post"], url_path="compute-metrics")
    def compute_metrics(self, request, pk=None):
        """Compute/refresh DerivedMetric rows from this company's Facts (admin only)."""
        from warehouse.services.edgar.metrics import compute_derived_metrics

        company = self.get_object()
        written = compute_derived_metrics(company)
        return Response({"company": company.id, "metrics_written": written})

    @action(detail=True, methods=["get"], url_path="profile")
    def profile(self, request, pk=None):
        """Consolidated Company-360 view: identity, financials, filings, documents, CRM."""
        from warehouse.services.edgar.profile import build_company_profile

        company = self.get_object()
        return Response(build_company_profile(company))

    @action(detail=False, methods=["get"], url_path="compare")
    def compare(self, request):
        """Compare a concept across a cohort grouped by industry/region/size."""
        from warehouse.services.edgar.profile import (
            COHORT_GROUP_FIELDS,
            cohort_compare,
        )

        group_by = (request.query_params.get("group_by") or "sic_code").strip()
        concept = (request.query_params.get("concept") or "").strip()
        if not concept:
            return Response(
                {"detail": "concept query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        taxonomy = (request.query_params.get("taxonomy") or "us-gaap").strip() or "us-gaap"
        try:
            data = cohort_compare(group_by=group_by, concept=concept, taxonomy=taxonomy)
        except ValueError as e:
            return Response(
                {"detail": str(e), "allowed_group_by": sorted(COHORT_GROUP_FIELDS)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(data)

    @action(detail=True, methods=["get"], url_path="leadership")
    def leadership(self, request, pk=None):
        """Officers/directors extracted from this company's SEC ownership filings."""
        company = self.get_object()
        positions = (
            LeadershipPosition.objects.filter(company=company)
            .select_related("person")
            .order_by("-last_seen")
        )
        people = [
            {
                "name": p.person.full_name,
                "person_cik": p.person.cik,
                "title": p.title,
                "is_director": p.is_director,
                "is_officer": p.is_officer,
                "is_ten_percent_owner": p.is_ten_percent_owner,
                "first_seen": p.first_seen.isoformat() if p.first_seen else None,
                "last_seen": p.last_seen.isoformat() if p.last_seen else None,
                "filings_count": p.filings_count,
                "net_insider_shares": float(p.net_insider_shares),
                "source": p.source,
            }
            for p in positions
        ]
        return Response({"company": company.id, "count": len(people), "leadership": people})

    @action(detail=True, methods=["get"], url_path="stakeholder-assessment")
    def stakeholder_assessment(self, request, pk=None):
        """Transparent people-vs-profits orientation index (heuristic; see caveats)."""
        from warehouse.services.stakeholder import compute_stakeholder_assessment

        company = self.get_object()
        return Response(compute_stakeholder_assessment(company, persist=False))

    @action(detail=False, methods=["get"], url_path="leadership-compare")
    def leadership_compare(self, request):
        """Compare leadership footprint + stakeholder orientation across companies (by CIK)."""
        from sec_edgar.cik import normalize_cik
        from warehouse.services.stakeholder import CAVEATS, compute_stakeholder_assessment

        raw = request.query_params.getlist("cik") or [
            c for c in (request.query_params.get("ciks") or "").split(",") if c.strip()
        ]
        ciks = []
        for c in raw:
            try:
                ciks.append(normalize_cik(c))
            except ValueError:
                continue
        if not ciks:
            return Response(
                {"detail": "Provide cik query params (e.g. ?cik=...&cik=...)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = []
        for company in Company.objects.filter(cik__in=ciks):
            assessment = compute_stakeholder_assessment(company, persist=False)
            top = (
                LeadershipPosition.objects.filter(company=company)
                .select_related("person")
                .order_by("-filings_count")[:5]
            )
            rows.append(
                {
                    "cik": company.cik,
                    "name": company.name,
                    "ticker": company.ticker,
                    "leadership_count": LeadershipPosition.objects.filter(company=company).count(),
                    "key_people": [
                        {"name": p.person.full_name, "title": p.title} for p in top
                    ],
                    "orientation_index": assessment["orientation_index"],
                    "orientation_label": assessment["label"],
                }
            )
        return Response({"count": len(rows), "results": rows, "caveats": CAVEATS})

    @action(detail=True, methods=["post"], url_path="analyze-leadership")
    def analyze_leadership(self, request, pk=None):
        """Run the optional LLM narrative analysis of leadership (admin only).

        Strictly grounded in this company's ingested SEC filing text; gated behind
        ``ENABLE_AI_ANALYSIS``. Returns a disabled-shaped payload when off. See
        ``docs/leadership-methodology.md`` for the responsible-use boundary.
        """
        from warehouse.services.leadership_ai import analyze_company_leadership

        company = self.get_object()
        result = analyze_company_leadership(company, persist=True)
        result["caveats"] = LEADERSHIP_AI_CAVEAT
        return Response(result)

    @action(detail=True, methods=["get"], url_path="leadership-analysis")
    def leadership_analysis(self, request, pk=None):
        """Most recent stored LLM leadership analysis for this company (if any)."""
        from warehouse.models import LeadershipAnalysis

        company = self.get_object()
        latest = (
            LeadershipAnalysis.objects.filter(company=company).order_by("-created_at").first()
        )
        if latest is None:
            return Response(
                {
                    "company": company.id,
                    "available": False,
                    "detail": "No analysis yet. POST to analyze-leadership/ to generate one.",
                    "caveats": LEADERSHIP_AI_CAVEAT,
                }
            )
        return Response(
            {
                "company": company.id,
                "available": True,
                "enabled": latest.enabled,
                "backend": latest.backend,
                "model_name": latest.model_name,
                "summary": latest.summary,
                "initiatives": latest.initiatives,
                "quotes": latest.quotes,
                "direction": latest.direction,
                "used_sources": latest.used_sources,
                "error": latest.error,
                "created_at": latest.created_at.isoformat(),
                "caveats": LEADERSHIP_AI_CAVEAT,
            }
        )


class CompanyMetadataPagination(PageNumberPagination):
    page_size = 40
    page_size_query_param = "page_size"
    max_page_size = 200


class FilingPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class CompanyMetadataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Paginated company metadata for filtering, sorting, and dashboard-style facets.
    """

    queryset = Company.objects.all()
    serializer_class = CompanyMetadataSerializer
    pagination_class = CompanyMetadataPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = CompanyMetadataFilter
    search_fields = [
        "name",
        "ticker",
        "cik",
        "industry",
        "sic_description",
        "headquarters",
        "sic_code",
        "naics_code",
        "crm_external_key",
        "customer_vertical",
        "customer_class",
        "contract_status",
        "hq_city",
    ]
    ordering_fields = [
        "name",
        "ticker",
        "cik",
        "industry",
        "sic_code",
        "sic_description",
        "hq_state",
        "hq_country",
        "hq_city",
        "customer_vertical",
        "contract_status",
        "created_at",
        "updated_at",
    ]
    ordering = ["name"]

    def get_queryset(self):
        return Company.objects.all().only(
            "id",
            "cik",
            "ticker",
            "name",
            "industry",
            "sic_code",
            "sic_description",
            "naics_code",
            "hq_state",
            "hq_country",
            "hq_city",
            "headquarters",
            "size",
            "crm_external_key",
            "customer_class",
            "customer_type",
            "customer_vertical",
            "contract_status",
            "created_at",
            "updated_at",
        )

    @action(detail=False, methods=["get"], url_path="facets")
    def facets(self, request):
        """Aggregate counts for SIC, state, industry, and coverage stats."""
        qs = Company.objects.all()
        total = qs.count()
        with_sic = (
            qs.exclude(sic_code__isnull=True).exclude(sic_code="").count()
        )
        with_naics = (
            qs.exclude(naics_code__isnull=True).exclude(naics_code="").count()
        )
        with_industry = (
            qs.exclude(industry__isnull=True).exclude(industry="").count()
        )
        top_sic = list(
            qs.exclude(sic_description__isnull=True)
            .exclude(sic_description="")
            .values("sic_code", "sic_description")
            .annotate(count=Count("id"))
            .order_by("-count")[:30]
        )
        hq_state = list(
            qs.exclude(hq_state__isnull=True)
            .exclude(hq_state="")
            .values("hq_state")
            .annotate(count=Count("id"))
            .order_by("-count")[:30]
        )
        industry = list(
            qs.exclude(industry__isnull=True)
            .exclude(industry="")
            .values("industry")
            .annotate(count=Count("id"))
            .order_by("-count")[:25]
        )
        hq_country = list(
            qs.values("hq_country")
            .annotate(count=Count("id"))
            .order_by("-count")[:15]
        )
        return Response(
            {
                "totals": {
                    "companies": total,
                    "with_sic_code": with_sic,
                    "with_naics_code": with_naics,
                    "with_industry_text": with_industry,
                },
                "top_sic": top_sic,
                "hq_state": hq_state,
                "industry": industry,
                "hq_country": hq_country,
            }
        )


class FilingViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only filing data; writes happen via sync/ingest (admin-gated actions)."""

    queryset = Filing.objects.all().order_by("-filing_date")
    serializer_class = FilingSerializer
    pagination_class = FilingPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["form_type", "company"]
    search_fields = ["form_type", "accession_number"]
    ordering_fields = [
        "filing_date",
        "form_type",
        "accession_number",
        "period_of_report",
        "id",
    ]
    ordering = ["-filing_date"]

    @action(
        detail=False,
        methods=["post"],
        url_path="ingest-htm",
        throttle_classes=[SecActionThrottle],
    )
    def ingest_htm(self, request):
        """Parse one HTM filing URL into ``Filing`` / related rows (same service as ``ingest_htm`` command)."""
        url = request.data.get("url")
        ticker = request.data.get("ticker")
        cik = request.data.get("cik")
        if not url or (not ticker and not cik):
            return Response(
                {"detail": "url and ticker or cik are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ua = sec_user_agent_email_from_request(request)
            filing = EdgarSyncService.ingest_htm(url=url, ticker=ticker, cik=cik, user_agent_email=ua)
        except EdgarRateLimitError:
            return Response(
                {"detail": "SEC rate limit reached; try again shortly."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("ingest_htm failed")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(FilingSerializer(filing).data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["post"],
        url_path="ingest-submission",
        throttle_classes=[SecActionThrottle],
    )
    def ingest_submission(self, request):
        """Ingest a full SEC submission (.txt) into Filing + FilingDocument rows."""
        from sec_edgar.services.ingest_submission import (
            ingest_submission as ingest_submission_service,
        )

        url = request.data.get("url")
        ticker = request.data.get("ticker")
        cik = request.data.get("cik")
        if not url or (not ticker and not cik):
            return Response(
                {"detail": "url and ticker or cik are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ua = sec_user_agent_email_from_request(request)
            filing, n = ingest_submission_service(
                url=url, ticker=ticker, cik=cik, user_agent_email=ua
            )
        except EdgarRateLimitError:
            return Response(
                {"detail": "SEC rate limit reached; try again shortly."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("ingest_submission failed")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(
            {"filing": filing.id, "documents_ingested": n},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="search")
    def search_documents(self, request):
        """Full-text search across ingested FilingDocument text.

        Postgres uses ``SearchVector``/``SearchRank``; other backends fall back to
        a case-insensitive substring match.
        """
        from django.db import connection

        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response(
                {"detail": "q must be at least 2 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = FilingDocument.objects.select_related("filing", "filing__company")
        form_type = (request.query_params.get("form_type") or "").strip()
        if form_type:
            qs = qs.filter(filing__form_type=form_type)
        cik = (request.query_params.get("cik") or "").strip()
        if cik:
            from sec_edgar.cik import normalize_cik

            try:
                qs = qs.filter(filing__company__cik=normalize_cik(cik))
            except ValueError:
                pass

        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import (
                SearchQuery,
                SearchRank,
                SearchVector,
            )

            search_query = SearchQuery(q, config="english")
            qs = (
                qs.annotate(rank=SearchRank(SearchVector("text", config="english"), search_query))
                .filter(text__search=search_query)
                .order_by("-rank")
            )
        else:
            qs = qs.filter(text__icontains=q).order_by("-filing__filing_date")

        rows = list(qs[:50])
        results = [
            {
                "id": d.id,
                "filing": d.filing_id,
                "company": d.filing.company_id,
                "cik": d.filing.company.cik,
                "form_type": d.filing.form_type,
                "type": d.type,
                "sequence": d.sequence,
                "file_name": d.file_name,
                "snippet": (d.text or "")[:280],
            }
            for d in rows
        ]
        return Response({"count": len(results), "query": q, "results": results})


class SectionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    filterset_fields = ["filing", "name"]


class TableViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    filterset_fields = ["filing"]


class FactViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Fact.objects.all().order_by("-period_end", "concept")
    serializer_class = FactSerializer
    filterset_class = FactFilterSet
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["concept"]
    ordering_fields = [
        "id",
        "period_end",
        "period_start",
        "concept",
        "taxonomy",
        "value",
        "company",
    ]
    ordering = ["-period_end", "concept"]

    @action(detail=False, methods=["get"], url_path="facets")
    def facets(self, request):
        company_id = request.query_params.get("company")
        if not company_id:
            return Response(
                {"detail": "company query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Fact.objects.filter(company_id=company_id)
        by_tax = list(qs.values("taxonomy").annotate(c=Count("id")).order_by("-c"))
        top_concepts = list(qs.values("concept").annotate(c=Count("id")).order_by("-c")[:50])
        by_year = list(
            qs.exclude(period_end__isnull=True)
            .annotate(y=TruncYear("period_end"))
            .values("y")
            .annotate(c=Count("id"))
            .order_by("-y")[:25]
        )
        year_rows = []
        for x in by_year:
            y = x["y"]
            year_rows.append(
                {"year": y.year if y is not None else None, "count": x["c"]}
            )
        return Response(
            {
                "company": int(company_id),
                "taxonomy_counts": by_tax,
                "top_concepts": top_concepts,
                "facts_by_period_year": year_rows,
            }
        )


class DerivedMetricViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DerivedMetric.objects.all().order_by("-period_end", "key")
    serializer_class = DerivedMetricSerializer
    filterset_fields = ["company", "key"]


class PeerGroupViewSet(viewsets.ModelViewSet):
    queryset = PeerGroup.objects.all().order_by("name")
    serializer_class = PeerGroupSerializer
    search_fields = ["name"]

    @action(detail=True, methods=["get"], url_path="analytics/peer-fact-compare")
    def analytics_peer_fact_compare(self, request, pk=None):
        """Latest fact for ``concept`` across members of this peer group."""
        pg = self.get_object()
        concept = (request.query_params.get("concept") or "").strip()
        if not concept:
            return Response(
                {"detail": "concept query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        taxonomy = (request.query_params.get("taxonomy") or "us-gaap").strip() or "us-gaap"
        rows = EdgarAnalyticsService.peer_group_latest_for_concept(
            pg, concept, taxonomy=taxonomy
        )
        return Response(
            {
                "peer_group": pg.id,
                "concept": concept,
                "taxonomy": taxonomy,
                "rows": rows,
            }
        )


class ExternalSeriesViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExternalSeries.objects.all().order_by("provider", "external_id")
    serializer_class = ExternalSeriesSerializer
    filterset_fields = ["provider", "external_id"]


class SeriesObservationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SeriesObservation.objects.all().order_by("-observation_date")
    serializer_class = SeriesObservationSerializer
    filterset_fields = ["series"]


class SeriesBundleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SeriesBundle.objects.all().order_by("slug")
    serializer_class = SeriesBundleSerializer
    lookup_field = "slug"

    @action(detail=True, methods=["get"], url_path="observations")
    def observations(self, request, slug=None):
        """Recent observations + series metadata for every series in this bundle.

        Limit is applied *per series* (``per_series``) so high-frequency (daily)
        series aren't truncated by lower-frequency ones sharing the bundle.
        """
        bundle = self.get_object()
        try:
            per = int(request.query_params.get("per_series") or request.query_params.get("limit") or 1500)
        except ValueError:
            per = 1500
        per = max(1, min(per, 8000))

        items = list(bundle.items.select_related("series").order_by("sort_order"))
        series_meta: list[dict] = []
        data: list[dict] = []
        for item in items:
            s = item.series
            meta = s.metadata or {}
            series_meta.append(
                {
                    "external_id": s.external_id,
                    "title": s.title,
                    "units": s.units,
                    "frequency": s.frequency,
                    "note": meta.get("note", ""),
                    "industries": meta.get("industries", []),
                }
            )
            for o in (
                SeriesObservation.objects.filter(series=s).order_by("-observation_date")[:per]
            ):
                data.append(
                    {
                        "series": s.external_id,
                        "provider": s.provider,
                        "date": o.observation_date.isoformat(),
                        "value": str(o.value),
                    }
                )
        return Response(
            {
                "bundle": bundle.slug,
                "name": bundle.name,
                "description": bundle.description,
                "count": len(data),
                "series": series_meta,
                "observations": data,
            }
        )


class EnrichmentDatasetViewSet(viewsets.ReadOnlyModelViewSet):
    """Enrichment datasets, with a coverage/trust report per dataset.

    Read-only over HTTP on purpose: running providers spends SEC and search
    budget and takes minutes, so it belongs to ``manage.py enrich_run`` (and
    Celery), not to a request that a browser can retry.
    """

    queryset = EnrichmentDataset.objects.annotate(record_count=Count("records")).order_by("slug")
    serializer_class = EnrichmentDatasetSerializer
    lookup_field = "slug"

    @action(detail=True, methods=["get"])
    def report(self, request, slug=None):
        """Coverage, validation tiers and per-provider outcomes for this dataset."""
        return Response(dataset_report(self.get_object()))


class EnrichmentRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """Enriched party records: the resolved golden values, and the claims behind them.

    ``/evidence/`` is the endpoint that makes this data usable — "why does it say
    that?" is answerable for every field, which is the entire reason providers
    emit claims instead of writing values.
    """

    queryset = (
        EnrichmentRecord.objects.select_related("dataset", "company")
        .prefetch_related("golden_fields")
        .order_by("pk")
    )
    serializer_class = EnrichmentRecordSerializer
    filterset_fields = ["dataset__slug", "status", "company"]
    search_fields = ["source_key"]

    @action(detail=True, methods=["get"])
    def evidence(self, request, pk=None):
        """Every claim for this record, with its provider, confidence and source."""
        record = self.get_object()
        return Response(
            {
                "record_id": record.pk,
                "source_key": record.source_key,
                "company": record.company_id,
                "claims": EnrichmentClaimSerializer(
                    record.claims.all().order_by("field", "-verified", "-confidence"), many=True
                ).data,
                "golden": EnrichmentGoldenFieldSerializer(
                    record.golden_fields.all().order_by("field"), many=True
                ).data,
                "provider_runs": list(
                    record.provider_runs.values("provider", "status", "detail", "ran_at")
                ),
            }
        )

    @action(detail=False, methods=["get"])
    def contested(self, request):
        """The review queue: records where comparable sources disagreed closely."""
        qs = self.filter_queryset(self.get_queryset()).filter(golden_fields__contested=True)
        page = self.paginate_queryset(qs.distinct())
        serializer = self.get_serializer(page if page is not None else qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
