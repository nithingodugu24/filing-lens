import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evaluation"))
from framework import RetrievalEvaluator  # noqa: E402
from statistical_significance import paired_bootstrap  # noqa: E402


def test_rank_metrics_known_example():
    result = RetrievalEvaluator.score(["irrelevant", "a", "b"], {"a", "b"}, k=3)
    assert result["mrr"] == 0.5
    assert result["recall"] == 1
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["map"] == pytest.approx((0.5 + 2 / 3) / 2)
    assert 0 < result["ndcg"] < 1
    assert RetrievalEvaluator.score(["a"], set())["mrr"] is None


def test_bootstrap_identical_and_invalid_samples():
    result = paired_bootstrap([1, 0.5, 0], [1, 0.5, 0], iterations=100)
    assert result["confidence_interval_95"] == [0, 0]
    assert result["p_value_two_sided"] == 1
    with pytest.raises(ValueError):
        paired_bootstrap([1], [])
