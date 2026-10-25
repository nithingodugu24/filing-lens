from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from app.answers import validate_claims
from app.finance import calculate, period_label
from app.providers import ProviderError, embed, request_provider
from app.retrieval import retrieve
from app.schemas import Filters, SearchRequest


def fact(**changes):
    return SimpleNamespace(**({"verified": True, "metric": "revenue", "value": "100", "currency": "INR",
                               "units": "crore", "basis": "consolidated", "revision": "original",
                               "period_start": date(2025, 4, 1), "period_end": date(2025, 6, 30)} | changes))


@pytest.mark.parametrize("mode", ["keyword", "vector", "hybrid"])
def test_filters_before_retrieval(corpus, mode):
    request = SearchRequest(question="operating margin utilisation", mode=mode,
                            filters=Filters(companies=["TCS"], period_ends=["2025-09-30"]))
    evidence, _ = retrieve(corpus, request)
    assert evidence
    assert all(e["company"] == "TCS" and e["period_end"] == "2025-09-30" for e in evidence)
    assert len({(e["document_id"], e["page_index"]) for e in evidence}) == len(evidence)


def test_cutoff_excludes_future_and_unknown(corpus):
    request = SearchRequest(question="revenue", filters=Filters(publication_cutoff="2025-08-01"))
    evidence, _ = retrieve(corpus, request)
    assert evidence and all(e["period_end"] == "2025-06-30" for e in evidence)


def test_question_evidence_workflow(client, corpus):
    result = client.post("/api/questions", json={"question": "What explains operating margin?",
                                               "filters": {"companies": ["TCS"]}})
    assert result.status_code == 200, result.text
    payload = result.json()
    assert not payload["abstained"] and payload["claims"]
    validate_claims(payload["claims"], payload["evidence"])
    assert payload["cost_usd"] is None
    evidence = payload["evidence"][0]
    assert client.get(f"/api/documents/{evidence['document_id']}/pages/{evidence['page_index']}").status_code == 200


def test_unsupported_and_conflict(client, corpus):
    unknown = client.post("/api/questions", json={"question": "What is the share price?"}).json()
    assert unknown["abstained"] and "Insufficient" in unknown["limitation"]
    conflict = client.post("/api/questions", json={"question": "Did discretionary demand improve?",
                                                "filters": {"companies": ["Infosys"], "period_ends": ["2025-09-30"]}}).json()
    assert "Conflicting" in conflict["limitation"]


def test_numerical_question(client, corpus):
    response = client.post("/api/questions", json={"question": "Compare revenue growth",
                                                 "filters": {"companies": ["TCS", "Infosys"]}})
    assert response.status_code == 200, response.text
    calculations = response.json()["calculations"]
    assert {c["company"]: c["result"] for c in calculations} == {"TCS": "2.5000", "Infosys": "4.0000"}


def test_citation_ids_and_quotes_rejected():
    with pytest.raises(ProviderError, match="invalid citation"):
        validate_claims([{"citation_ids": ["fake"], "supporting_quote": "hello"}], [{"id": "real", "text": "hello"}])
    with pytest.raises(ProviderError, match="quotation"):
        validate_claims([{"citation_ids": ["real"], "supporting_quote": "invented"}], [{"id": "real", "text": "hello"}])


def test_units_margin_and_growth():
    assert calculate(fact(), fact(value="1100", units="million"), "percentage_change")["result"] == "10.0000"
    assert calculate(fact(units="lakh"), fact(value="110", units="lakh"), "difference")["result"] == "1000000.0000"
    a = fact(metric="operating_margin", value="24", units="percent", currency="PCT")
    b = fact(metric="operating_margin", value="25", units="percent", currency="PCT")
    assert calculate(a, b, "percentage_points")["result"] == "1.0000"
    assert calculate(a, b, "basis_points")["result"] == "100.0000"
    assert period_label(date(2025, 4, 1), date(2025, 6, 30))["fiscal"] == "Q1 FY26"


@pytest.mark.parametrize("changes,operation,message", [
    ({"basis": "standalone"}, "difference", "basis"),
    ({"currency": "USD"}, "difference", "Currency"),
    ({"revision": "restated"}, "difference", "restated"),
    ({"verified": False}, "difference", "reviewed"),
    ({"units": "unknown"}, "difference", "Unknown"),
    ({"value": "NaN"}, "difference", "Missing"),
    ({"period_start": date(2025, 1, 1)}, "difference", "durations"),
])
def test_incompatible_facts(changes, operation, message):
    with pytest.raises(ValueError, match=message):
        calculate(fact(), fact(**changes), operation)


def test_zero_and_missing_values():
    with pytest.raises(ValueError, match="zero"):
        calculate(fact(value="0"), fact(), "percentage_change")
    with pytest.raises(ValueError, match="Missing"):
        calculate(fact(value=None), fact(), "difference")


def test_embedding_mismatch(corpus, monkeypatch):
    from app.config import get_settings
    get_settings().embedding_model = "changed-model"
    with pytest.raises(ProviderError, match="Reindex"):
        retrieve(corpus, SearchRequest(question="margin", mode="vector"))


def test_provider_timeout_and_rate_limit(monkeypatch):
    from app.config import get_settings
    get_settings().provider_api_key = "test-only"
    calls = []
    def timeout(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("no response")
    monkeypatch.setattr(httpx, "post", timeout)
    monkeypatch.setattr("app.providers.time.sleep", lambda _: None)
    with pytest.raises(ProviderError, match="timed out"):
        request_provider("embeddings", {})
    assert len(calls) == 3
    calls.clear()
    def limited(*args, **kwargs):
        calls.append(1)
        return httpx.Response(429, request=httpx.Request("POST", "https://example.test"))
    monkeypatch.setattr(httpx, "post", limited)
    with pytest.raises(ProviderError, match="failed"):
        request_provider("embeddings", {})
    assert len(calls) == 3


def test_embedding_dimensions_checked(monkeypatch):
    from app.config import get_settings
    get_settings().embedding_provider = "openai"
    monkeypatch.setattr("app.providers.request_provider", lambda *args: {"data": [{"index": 0, "embedding": [0.1]}]})
    with pytest.raises(ProviderError, match="incompatible"):
        embed(["test"])
