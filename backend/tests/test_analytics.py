from app.analytics import analytics


def test_checked_analytics_source_isolation(corpus):
    result = analytics(corpus, True)
    assert result["summary"] == {"document_count": 4, "company_count": 2, "fact_count": 8}
    assert [r["period_end"] for r in result["revenue_trends"]] == sorted(
        r["period_end"] for r in result["revenue_trends"]
    )
    assert {r["company"]: r["revenue_growth"] for r in result["company_profiles"]} == {
        "Infosys": "4.00",
        "TCS": "2.500",
    }
    assert analytics(corpus, False)["summary"]["fact_count"] == 0


def test_unchecked_fact_excluded(corpus):
    from sqlalchemy import select
    from app.models import Fact

    fact = corpus.scalar(select(Fact))
    fact.verified = False
    corpus.flush()
    assert analytics(corpus, True)["summary"]["fact_count"] == 7
