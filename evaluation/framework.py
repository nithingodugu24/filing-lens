"""Explicit relevance metrics. Quote overlap is not semantic faithfulness."""

import math
import statistics
from decimal import Decimal


class RetrievalEvaluator:
    @staticmethod
    def score(ranked, relevant, k=6):
        ranked = list(dict.fromkeys(ranked))[:k]
        relevant = set(relevant)
        if not relevant:
            return dict.fromkeys(["mrr", "ndcg", "recall", "precision", "map"], None)
        hits = [int(x in relevant) for x in ranked]
        dcg = sum(hit / math.log2(i + 2) for i, hit in enumerate(hits))
        ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(relevant))))
        return {
            "mrr": next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0),
            "ndcg": dcg / ideal,
            "recall": sum(hits) / len(relevant),
            "precision": sum(hits) / k,
            "map": sum(
                sum(hits[: i + 1]) / (i + 1) for i, hit in enumerate(hits) if hit
            )
            / len(relevant),
        }

    @staticmethod
    def latency(values):
        ordered = sorted(values)
        return (
            {
                f"p{q}": ordered[max(0, math.ceil(len(ordered) * q / 100) - 1)]
                for q in (50, 90, 99)
            }
            if ordered
            else {}
        )


class AnswerEvaluator:
    @staticmethod
    def score(result, question, bert=False):
        predicted = " ".join(c["text"] for c in result["claims"])
        expected = question["expected_answer"]
        scores = {"rouge1": None, "rouge2": None, "rougeL": None, "bertscore": None}
        try:
            from rouge_score.rouge_scorer import RougeScorer

            scores.update(
                {
                    key: value.fmeasure
                    for key, value in RougeScorer(
                        ["rouge1", "rouge2", "rougeL"], use_stemmer=True
                    )
                    .score(expected, predicted)
                    .items()
                }
            )
        except ImportError:
            pass
        if bert and predicted:
            from bert_score import score

            _, _, f1 = score(
                [predicted],
                [expected],
                model_type="distilbert-base-uncased",
                lang="en",
                verbose=False,
                device="cpu",
            )
            scores["bertscore"] = float(f1[0])
        evidence = {e["id"]: e for e in result["evidence"]}
        citations = [cid for c in result["claims"] for cid in c["citation_ids"]]
        gold = {tuple(x) for x in question["evidence"]}
        cited_pages = {
            (
                evidence[cid]["company"],
                evidence[cid]["period_end"],
                evidence[cid]["page_index"],
            )
            for cid in citations
            if cid in evidence
        }
        quote_support = [
            any(
                cid in evidence
                and " ".join(c["supporting_quote"].split())
                in " ".join(evidence[cid]["text"].split())
                for cid in c["citation_ids"]
            )
            for c in result["claims"]
        ]
        got = {c["company"]: Decimal(c["result"]) for c in result["calculations"]}
        scores.update(
            numerical_exact=all(
                name in got and got[name] == Decimal(str(value))
                for name, value in question["numbers"].items()
            )
            if "numbers" in question
            else None,
            abstention_correct=result["abstained"] == question["abstain"],
            citation_precision=len(cited_pages & gold) / len(cited_pages)
            if cited_pages
            else None,
            citation_recall=len(cited_pages & gold) / len(gold) if gold else None,
            quote_support=statistics.mean(quote_support) if quote_support else None,
            semantic_faithfulness=None,
        )
        return scores


class EmbeddingEvaluator:
    @staticmethod
    def aggregate(rows):
        keys = (
            "mrr",
            "ndcg",
            "recall",
            "precision",
            "map",
            "rouge1",
            "rouge2",
            "rougeL",
            "bertscore",
            "numerical_exact",
            "abstention_correct",
            "citation_precision",
            "citation_recall",
            "quote_support",
        )
        return {
            key: statistics.mean(values)
            if (values := [r[key] for r in rows if r.get(key) is not None])
            else None
            for key in keys
        }
