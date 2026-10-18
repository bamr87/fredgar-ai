"""LLM leadership narrative analyzer — gating, grounding, persistence, and API.

No live API calls: the Anthropic client is faked/injected throughout.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.test import override_settings
from rest_framework import status

from warehouse.models import (
    Company,
    ContentChunk,
    Filing,
    FilingDocument,
    LeadershipAnalysis,
)
from warehouse.services.leadership_ai import (
    AnthropicAnalyzer,
    NoopAnalyzer,
    _gather_passages,
    analyze_company_leadership,
    get_leadership_analyzer,
)

PAYLOAD = {
    "summary": "Leadership emphasized local manufacturing and R&D.",
    "initiatives": [
        {"title": "Gigafactory expansion", "description": "New domestic plant.", "source": "S1"}
    ],
    "quotes": [{"text": "We are investing in American jobs.", "speaker": "CEO", "source": "S1"}],
    "direction": "Continued reinvestment in capacity.",
}


class _FakeMessages:
    def __init__(self, payload, recorder):
        self._payload = payload
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.update(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking="(reasoning omitted)"),
                SimpleNamespace(type="text", text=json.dumps(self._payload)),
            ]
        )


class FakeAnthropic:
    """Stand-in for ``anthropic.Anthropic`` that records the request."""

    def __init__(self, payload=PAYLOAD):
        self.calls: dict = {}
        self.messages = _FakeMessages(payload, self.calls)


def _company_with_text() -> Company:
    co = Company.objects.create(cik="0001318605", ticker="TSLA", name="Tesla")
    f = Filing.objects.create(company=co, accession_number="0001-23", form_type="10-K")
    FilingDocument.objects.create(
        filing=f, sequence=1, sha1="abc", type="10-K",
        text="Our CEO said we are investing in American jobs and new factories.",
    )
    return co


# --- gating ---


@override_settings(ENABLE_AI_ANALYSIS=False)
@pytest.mark.django_db
def test_disabled_returns_noop():
    assert isinstance(get_leadership_analyzer(), NoopAnalyzer)
    co = _company_with_text()
    result = analyze_company_leadership(co)
    assert result["enabled"] is False
    assert result["backend"] == "none"
    # A disabled run is still recorded (transparency), with no content.
    row = LeadershipAnalysis.objects.get(company=co)
    assert row.enabled is False
    assert row.initiatives == []


@override_settings(ENABLE_AI_ANALYSIS=True, AI_ANALYSIS_AUTH_TOKEN="", AI_ANALYSIS_API_KEY="")
@pytest.mark.django_db
def test_enabled_without_credentials_degrades_to_noop():
    # On by default but no token/key configured and no client injected -> safe no-op,
    # never a surprise API call or an auth error.
    assert isinstance(get_leadership_analyzer(), NoopAnalyzer)


@override_settings(ENABLE_AI_ANALYSIS=True, AI_ANALYSIS_BACKEND="none")
@pytest.mark.django_db
def test_backend_none_is_noop_even_when_enabled():
    assert isinstance(get_leadership_analyzer(), NoopAnalyzer)


@override_settings(ENABLE_AI_ANALYSIS=True, AI_ANALYSIS_BACKEND="anthropic")
@pytest.mark.django_db
def test_enabled_returns_anthropic_analyzer():
    analyzer = get_leadership_analyzer(client=FakeAnthropic())
    assert isinstance(analyzer, AnthropicAnalyzer)
    assert analyzer.enabled is True


# --- passages / grounding ---


@pytest.mark.django_db
def test_gather_passages_prefers_content_chunks():
    co = _company_with_text()
    fd = FilingDocument.objects.filter(filing__company=co).first()
    ContentChunk.objects.create(
        company=co, filing_document=fd, source="filing_document",
        char_start=0, char_end=20, text="Chunked leadership passage about hiring locally.",
    )
    passages = _gather_passages(co)
    assert passages, "expected at least one passage"
    assert passages[0]["tag"] == "S1"
    assert "Chunked leadership passage" in passages[0]["text"]
    assert passages[0]["accession"] == "0001-23"


@pytest.mark.django_db
def test_gather_passages_falls_back_to_filing_documents():
    co = _company_with_text()  # no ContentChunk rows
    passages = _gather_passages(co)
    assert len(passages) == 1
    assert passages[0]["tag"] == "S1"
    assert "American jobs" in passages[0]["text"]


# --- enabled analysis with an injected client ---


@override_settings(ENABLE_AI_ANALYSIS=True, AI_ANALYSIS_MODEL="claude-opus-5-5")
@pytest.mark.django_db
def test_analyze_with_injected_client_persists_and_grounds():
    co = _company_with_text()
    fake = FakeAnthropic()
    result = analyze_company_leadership(co, client=fake)

    assert result["enabled"] is True
    assert result["backend"] == "anthropic"
    assert result["initiatives"][0]["title"] == "Gigafactory expansion"
    assert result["quotes"][0]["source"] == "S1"
    assert result["used_sources"][0]["tag"] == "S1"
    assert result["error"] == ""

    # The request was grounded: system prompt + the filing excerpt were sent, with
    # structured-output + adaptive thinking configured.
    call = fake.calls
    assert call["model"] == "claude-opus-5-5"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "verbatim" in call["system"].lower()
    assert "American jobs" in call["messages"][0]["content"]
    assert "[S1]" in call["messages"][0]["content"]

    row = LeadershipAnalysis.objects.get(company=co)
    assert row.enabled is True
    assert row.summary == PAYLOAD["summary"]
    assert row.model_name == "claude-opus-5-5"


@override_settings(ENABLE_AI_ANALYSIS=True, AI_ANALYSIS_API_KEY="test-key")
@pytest.mark.django_db
def test_enabled_but_no_text_records_error_without_calling_model():
    co = Company.objects.create(cik="0000000009", name="NoText")
    # A credential is configured so the real analyzer is selected, but with no filing text
    # the model is never called (analyze() — and the SDK import — are short-circuited).
    result = analyze_company_leadership(co)
    assert result["enabled"] is True
    assert "No filing text" in result["error"]
    assert result["initiatives"] == []
    assert LeadershipAnalysis.objects.filter(company=co, enabled=True).exists()


@override_settings(ENABLE_AI_ANALYSIS=True)
@pytest.mark.django_db
def test_model_failure_is_recorded_not_raised():
    co = _company_with_text()

    class _BoomClient:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("upstream 529")

    result = analyze_company_leadership(co, client=_BoomClient())
    assert result["enabled"] is True
    assert "529" in result["error"]


# --- credential / token auth ---


def _install_fake_anthropic_sdk(monkeypatch):
    """Insert a fake top-level ``anthropic`` module so ``_get_client()`` can build a client
    without the real SDK; returns a dict capturing the constructor kwargs."""
    import sys
    import types

    captured: dict = {}

    class _Client:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.api_key = kwargs.get("api_key")
            self.auth_token = kwargs.get("auth_token")
            self.default_headers = kwargs.get("default_headers")

    mod = types.ModuleType("anthropic")
    mod.Anthropic = _Client
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    return captured


@override_settings(
    ENABLE_AI_ANALYSIS=True, AI_ANALYSIS_AUTH_TOKEN="oauth-tok", AI_ANALYSIS_API_KEY=""
)
@pytest.mark.django_db
def test_get_client_prefers_oauth_token(monkeypatch):
    captured = _install_fake_anthropic_sdk(monkeypatch)
    analyzer = get_leadership_analyzer()
    assert isinstance(analyzer, AnthropicAnalyzer)
    client = analyzer._get_client()
    # Bearer token + oauth beta header; api_key never passed and explicitly neutralized so
    # x-api-key is not sent alongside the Authorization header (which would 401).
    assert captured["init"]["auth_token"] == "oauth-tok"
    assert captured["init"]["default_headers"] == {"anthropic-beta": "oauth-2025-04-20"}
    assert "api_key" not in captured["init"]
    assert client.api_key is None


@override_settings(
    ENABLE_AI_ANALYSIS=True, AI_ANALYSIS_AUTH_TOKEN="", AI_ANALYSIS_API_KEY="key-123"
)
@pytest.mark.django_db
def test_get_client_falls_back_to_api_key(monkeypatch):
    captured = _install_fake_anthropic_sdk(monkeypatch)
    analyzer = get_leadership_analyzer()
    assert isinstance(analyzer, AnthropicAnalyzer)
    analyzer._get_client()
    assert captured["init"]["api_key"] == "key-123"
    assert "auth_token" not in captured["init"]


@override_settings(
    ENABLE_AI_ANALYSIS=True, AI_ANALYSIS_AUTH_TOKEN="oauth-tok", AI_ANALYSIS_API_KEY="key-123"
)
@pytest.mark.django_db
def test_get_client_warns_and_uses_token_when_both_set(monkeypatch, caplog):
    captured = _install_fake_anthropic_sdk(monkeypatch)
    analyzer = AnthropicAnalyzer()
    with caplog.at_level("WARNING"):
        analyzer._get_client()
    assert captured["init"]["auth_token"] == "oauth-tok"
    assert "api_key" not in captured["init"]  # never send both
    assert any("ignoring the API key" in r.getMessage() for r in caplog.records)


# --- API ---


@pytest.mark.django_db
def test_analyze_leadership_api_requires_admin(api_client):
    co = _company_with_text()
    r = api_client.post(f"/api/v1/companies/{co.id}/analyze-leadership/")
    assert r.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
def test_analyze_leadership_api_disabled_returns_caveat(admin_client):
    co = _company_with_text()
    r = admin_client.post(f"/api/v1/companies/{co.id}/analyze-leadership/")
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert body["enabled"] is False
    assert "approval rating" in body["caveats"].lower()


@override_settings(ENABLE_AI_ANALYSIS=True)
@pytest.mark.django_db
def test_analyze_and_fetch_via_api(admin_client, monkeypatch):
    co = _company_with_text()

    class _Stub:
        enabled = True
        backend = "anthropic"
        model_name = "claude-opus-5-5"

        def analyze(self, name, passages):
            return PAYLOAD

    monkeypatch.setattr(
        "warehouse.services.leadership_ai.get_leadership_analyzer",
        lambda **kw: _Stub(),
    )
    r = admin_client.post(f"/api/v1/companies/{co.id}/analyze-leadership/")
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["initiatives"][0]["title"] == "Gigafactory expansion"

    # GET returns the stored analysis (reads are public).
    g = admin_client.get(f"/api/v1/companies/{co.id}/leadership-analysis/")
    assert g.status_code == status.HTTP_200_OK
    gbody = g.json()
    assert gbody["available"] is True
    assert gbody["quotes"][0]["text"] == PAYLOAD["quotes"][0]["text"]
    assert "caveats" in gbody


@pytest.mark.django_db
def test_leadership_analysis_api_empty(api_client):
    co = _company_with_text()
    r = api_client.get(f"/api/v1/companies/{co.id}/leadership-analysis/")
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["available"] is False
