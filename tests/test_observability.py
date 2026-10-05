import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from eval import failure_loop
from rag import observability
from rag.llm import BaseLLM
from rag.pipeline import SimpleRAGPipeline
from rag.rerank import BaseRerank
from rag.retrieval import BaseRetrieval
from rag.semantic_cache import SemanticCache, normalize


def fake_embed(text: str) -> np.ndarray:
    """Deterministic bag-of-letters embedding: paraphrases that share most
    words land close together, unrelated text doesn't. No model download.
    """
    vec = np.zeros(26, dtype=np.float32)
    for word in normalize(text).split():
        for ch in word:
            if ch.isalpha() and ch.isascii():
                vec[ord(ch) - 97] += 1
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)


class SemanticCacheTests(TempDirCase):
    def make(self, **kw):
        return SemanticCache(path=self.dir / "c.jsonl", embed_fn=fake_embed, **kw)

    def test_exact_and_paraphrase_hit_unrelated_miss(self):
        cache = self.make(threshold=0.95)
        cache.store("doc1", "What projects did he work on?", {"answer": "Swapsi"})
        hit = cache.lookup("doc1", "what projects did he work on")
        self.assertTrue(hit["hit"])
        self.assertEqual(hit["similarity"], 1.0)
        self.assertFalse(cache.lookup("doc1", "zzz qqq xxx")["hit"])

    def test_paraphrase_hits_by_similarity(self):
        cache = self.make(threshold=0.9)
        cache.store("doc1", "what projects did he work on", {"answer": "Swapsi"})
        result = cache.lookup("doc1", "what projects has he worked on")
        self.assertTrue(result["hit"])
        self.assertLess(result["similarity"], 1.0)

    def test_namespaces_are_isolated(self):
        cache = self.make()
        cache.store("doc1", "who is the candidate", {"answer": "A"})
        self.assertFalse(cache.lookup("doc2", "who is the candidate")["hit"])

    def test_persists_across_restart_and_respects_ttl(self):
        self.make().store("doc1", "who is the candidate", {"answer": "A"})
        self.assertTrue(self.make().lookup("doc1", "who is the candidate")["hit"])
        self.assertFalse(self.make(ttl_s=-1).lookup("doc1", "who is the candidate")["hit"])

    def test_eviction_and_invalidate(self):
        cache = self.make(max_entries=2)
        for q in ("alpha question", "beta question", "gamma question"):
            cache.store("doc1", q, {"answer": q})
        self.assertEqual(cache.stats()["entries"], 2)
        self.assertEqual(cache.invalidate("doc1"), 2)
        self.assertEqual(cache.stats()["entries"], 0)


class LogDirCase(TempDirCase):
    def setUp(self):
        super().setUp()
        # RAG_TRACE_FILE="" disables eval/trace_report.json so tests never
        # append fake queries to the real trace.
        for name, value in (("RAG_LOG_DIR", str(self.dir)), ("RAG_TRACE_FILE", "")):
            old = os.environ.get(name)
            os.environ[name] = value
            self.addCleanup(
                lambda n=name, o=old: os.environ.pop(n, None) if o is None else os.environ.__setitem__(n, o)
            )
        old_cases = failure_loop.CASES_FILE
        failure_loop.CASES_FILE = self.dir / "cases.jsonl"
        self.addCleanup(lambda: setattr(failure_loop, "CASES_FILE", old_cases))


class ObservabilityTests(LogDirCase):
    def _record(self, query_id, cache_hit=False, cost=0.001, ms=1000.0):
        return observability.record_query_metrics(
            {
                "query_id": query_id,
                "query": "q",
                "total_duration_ms": ms,
                "steps": {"generate": {"duration_ms": ms}},
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "estimated_cost_usd": cost},
                "issues": [],
            },
            pdf_hash="h",
            cache={"hit": cache_hit, "saved_cost_usd": 0.001 if cache_hit else 0.0},
        )

    def test_summary_counts_hits_cost_and_savings(self):
        self._record("a", cost=0.002, ms=2000)
        self._record("b", cache_hit=True, cost=0.0, ms=5)
        s = observability.summarize()
        self.assertEqual(s["queries"], 2)
        self.assertEqual(s["cache_hit_rate"], 0.5)
        self.assertAlmostEqual(s["total_cost_usd"], 0.002)
        self.assertAlmostEqual(s["saved_cost_usd"], 0.001)

    def test_slow_query_alert(self):
        self.assertIn("slow_query", self._record("slow", ms=60000)["alerts"])

    def test_failure_dedupes_and_promotes_idempotently(self):
        observability.record_failure("q1", "issue:low_relevance", query="who?", pdf_hash="h", answer="idk")
        observability.record_failure("q1", "low_rating", detail="rated 1")
        failures = observability.list_failures()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["kinds"], ["issue:low_relevance", "low_rating"])

        case = failure_loop.promote("q1", expected_keyword="Midhun")
        again = failure_loop.promote("q1", expected_keyword="Midhun")
        self.assertEqual(case["case_id"], again["case_id"])
        self.assertEqual(len(failure_loop.load_cases()), 1)
        self.assertEqual(observability.get_failure("q1")["status"], "promoted")

    def test_promote_rejects_unreplayable_failure(self):
        observability.record_failure("q2", "exception", detail="boom")
        with self.assertRaises(ValueError):
            failure_loop.promote("q2")
        with self.assertRaises(KeyError):
            failure_loop.promote("nope")

    def test_evaluate_case_rules(self):
        case = {"should_answer": True, "expected_keyword": "Midhun"}
        ctx = ["Midhun T Mobile Developer"]
        self.assertTrue(failure_loop.evaluate_case(case, "The candidate is Midhun T.", ctx, [])["passed"])
        self.assertFalse(failure_loop.evaluate_case(case, "The candidate is Bob.", ctx, [])["passed"])
        self.assertFalse(
            failure_loop.evaluate_case(case, "It is Midhun.", ctx, [{"type": "low_relevance"}])["passed"]
        )


class _Retrieval(BaseRetrieval):
    def retrieve(self, query, top_k=10):
        return ["Midhun T is a mobile developer."], None


class _Rerank(BaseRerank):
    def __init__(self, score):
        self.score = score

    def rerank(self, query, documents, top_k=3):
        return documents, [self.score]


class _LLM(BaseLLM):
    model_name = "stub"

    def __init__(self):
        self.calls = 0

    def generate_with_reasoning(self, prompt, **kwargs):
        self.calls += 1
        return {
            "content": "Midhun T",
            "reasoning": None,
            "usage": {"prompt_tokens": 50, "completion_tokens": 5, "total_tokens": 55, "estimated_cost_usd": 0.001},
        }


class PipelineIntegrationTests(LogDirCase):
    def _pipeline(self, score=5.0):
        self.llm = _LLM()
        cache = SemanticCache(path=self.dir / "cache.jsonl", embed_fn=fake_embed, threshold=0.9)
        return SimpleRAGPipeline(
            retrieval=_Retrieval(), rerank=_Rerank(score), llm=self.llm, cache=cache, pdf_hash="h1"
        )

    def test_repeat_question_is_served_from_cache_at_zero_cost(self):
        pipe = self._pipeline()
        first = pipe.run("who is the candidate")
        second = pipe.run("Who is the candidate?")
        self.assertEqual(self.llm.calls, 1)
        self.assertEqual(second.answer, first.answer)
        self.assertTrue(second.trace["cache"]["hit"])
        self.assertEqual(second.trace["usage"]["estimated_cost_usd"], 0.0)
        s = observability.summarize()
        self.assertEqual((s["queries"], s["cache_hits"]), (2, 1))
        self.assertAlmostEqual(s["saved_cost_usd"], 0.001)

    def test_use_cache_false_bypasses_cache(self):
        pipe = self._pipeline()
        pipe.run("who is the candidate")
        pipe.run("who is the candidate", use_cache=False)
        self.assertEqual(self.llm.calls, 2)

    def test_failed_answers_are_logged_and_never_cached(self):
        pipe = self._pipeline(score=-3.0)  # low_relevance issue
        pipe.run("who is the candidate")
        pipe.run("who is the candidate")
        self.assertEqual(self.llm.calls, 2)
        failures = observability.list_failures()
        self.assertEqual(len(failures), 2)
        self.assertEqual(failures[0]["kinds"], ["issue:low_relevance"])
        self.assertEqual(failures[0]["pdf_hash"], "h1")

    def test_exception_is_recorded_then_reraised(self):
        pipe = self._pipeline()
        pipe.llm.generate_with_reasoning = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("groq down"))
        with self.assertRaises(RuntimeError):
            pipe.run("who is the candidate")
        self.assertEqual(observability.list_failures()[0]["kinds"], ["exception"])
        self.assertEqual(observability.summarize()["errors"], 1)


@unittest.skipUnless(
    os.getenv("GROQ_API_KEY") and failure_loop.load_cases(),
    "needs GROQ_API_KEY and promoted cases in eval/failure_cases.jsonl",
)
class FailureCaseReplayTests(unittest.TestCase):
    """Every failure promoted from the Observability page becomes a test here."""

    def test_promoted_failures_stay_fixed(self):
        results = failure_loop.replay(failure_loop.load_cases())
        failed = [r for r in results if not r["passed"]]
        self.assertFalse(failed, json.dumps(failed, indent=2, default=str)[:2000])


if __name__ == "__main__":
    unittest.main()
