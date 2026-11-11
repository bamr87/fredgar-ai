from django.contrib import admin
from django.urls import include, path

from api.v1.views import HealthReadyView, HealthView, VersionView

urlpatterns = [
    # UPS-BE-10/11 probes at the root: anonymous, unthrottled, never cached.
    # /api/v1/health/ and /api/v1/health/ready/ stay as aliases of the same views.
    path("healthz", HealthView.as_view(), name="healthz"),
    path("readyz", HealthReadyView.as_view(), name="readyz"),
    path("version", VersionView.as_view(), name="version"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.v1.urls")),
    path("api/", include("api.urls")),
]
