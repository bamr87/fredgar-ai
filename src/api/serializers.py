from rest_framework import serializers

from public_data.models import ExternalSeries, SeriesBundle, SeriesObservation
from warehouse.models import (
    Company,
    DerivedMetric,
    EnrichmentClaim,
    EnrichmentDataset,
    EnrichmentGoldenField,
    EnrichmentRecord,
    Fact,
    Filing,
    PeerGroup,
    Section,
    Table,
)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"


class CompanyMetadataSerializer(serializers.ModelSerializer):
    """List view for metadata explorer (no large JSON blobs)."""

    class Meta:
        model = Company
        fields = [
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
        ]


class FilingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filing
        fields = "__all__"


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = "__all__"


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = "__all__"


class FactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fact
        fields = "__all__"


class DerivedMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DerivedMetric
        fields = "__all__"


class PeerGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeerGroup
        fields = "__all__"


class ExternalSeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalSeries
        fields = "__all__"


class SeriesObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeriesObservation
        fields = "__all__"


class SeriesBundleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeriesBundle
        fields = "__all__"


class EnrichmentDatasetSerializer(serializers.ModelSerializer):
    records = serializers.IntegerField(source="record_count", read_only=True)

    class Meta:
        model = EnrichmentDataset
        fields = ["id", "slug", "name", "description", "source_path", "records", "created_at"]


class EnrichmentGoldenFieldSerializer(serializers.ModelSerializer):
    """One resolved value, with the evidence and the dissent behind it."""

    class Meta:
        model = EnrichmentGoldenField
        fields = ["field", "value", "confidence", "provider", "ev_url", "rivals", "contested"]


class EnrichmentClaimSerializer(serializers.ModelSerializer):
    """One provider's assertion. ``verified`` separates a check from a proposal."""

    class Meta:
        model = EnrichmentClaim
        fields = [
            "field",
            "value",
            "confidence",
            "provider",
            "verified",
            "ev_url",
            "ev_snippet",
            "ev_locator",
            "retrieved_at",
        ]


class EnrichmentRecordSerializer(serializers.ModelSerializer):
    dataset = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    golden = EnrichmentGoldenFieldSerializer(source="golden_fields", many=True, read_only=True)

    class Meta:
        model = EnrichmentRecord
        fields = [
            "id",
            "dataset",
            "source_key",
            "seed",
            "company",
            "status",
            "golden",
            "updated_at",
        ]
