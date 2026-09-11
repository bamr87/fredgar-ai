from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyMetadataViewSet,
    CompanyViewSet,
    DerivedMetricViewSet,
    EnrichmentDatasetViewSet,
    EnrichmentRecordViewSet,
    ExternalSeriesViewSet,
    FactViewSet,
    FilingViewSet,
    HealthReadyView,
    HealthView,
    PeerGroupViewSet,
    SectionViewSet,
    SeriesBundleViewSet,
    SeriesObservationViewSet,
    SicCodesReferenceView,
    TableViewSet,
    TaskStatusView,
)

router = DefaultRouter()
router.register(r"companies", CompanyViewSet)
router.register(r"company-metadata", CompanyMetadataViewSet, basename="company-metadata")
router.register(r"filings", FilingViewSet)
router.register(r"facts", FactViewSet)
router.register(r"sections", SectionViewSet)
router.register(r"tables", TableViewSet)
router.register(r"derived-metrics", DerivedMetricViewSet)
router.register(r"peer-groups", PeerGroupViewSet)
router.register(r"enrichment-datasets", EnrichmentDatasetViewSet)
router.register(r"enrichment-records", EnrichmentRecordViewSet)
router.register(r"public-series", ExternalSeriesViewSet)
router.register(r"public-observations", SeriesObservationViewSet)
router.register(r"series-bundles", SeriesBundleViewSet)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("health/ready/", HealthReadyView.as_view(), name="health-ready"),
    path("reference/sic-codes/", SicCodesReferenceView.as_view(), name="reference-sic-codes"),
    path("tasks/<str:task_id>/", TaskStatusView.as_view(), name="task-status"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("", include(router.urls)),
]
