import logging
import time
from abc import ABC
from datetime import datetime, timezone

from observability import metrics as observability
from .llm import BaseLLM
from .prompt import ANSWER_PROMPT
from .rerank import BaseRerank
from .retrieval import BaseRetrieval
from observability.tracing import detect_issues, new_trace_id, preview_text, record_query_trace, traced_stage

logger = logging.getLogger("rag.pipeline")


class Answer:
    def __init__(
        self,
        answer: str,
        contexts: list[str],
        issues: list[dict] | None = None,
        reasoning: str | None = None,
        trace: dict | None = None,
    ):
        self.answer = answer
        self.contexts = contexts
        self.issues = issues or []
        self.reasoning = reasoning
        # Full per-stage trace record (same shape written to
        # eval/trace_report.json) -- lets callers (e.g. the API layer) show
        # the whole pipeline without recomputing or re-deriving it.
        self.trace = trace or {}


class Pipeline(ABC):
    def __init__(self, *args, **kwargs):
        pass

    def run(self, query: str) -> Answer:
        raise NotImplementedError


class SimpleRAGPipeline(Pipeline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not kwargs.get("retrieval"):
            raise ValueError("Please provide a `retrieval` model.")
        if not kwargs.get("llm"):
            raise ValueError("Please provide a `llm` model.")
        self.retrieval = kwargs.get("retrieval")
        # assert retrieval must be BaseRetrieval class or it inherits from BaseRetrieval
        assert issubclass(self.retrieval.__class__, BaseRetrieval)
        self.rerank = kwargs.get("rerank")
        if self.rerank:
            # assert rerank must be BaseRerank class or it inherits from BaseRerank
            assert issubclass(self.rerank.__class__, BaseRerank)
        self.llm = kwargs.get("llm")
        # assert llm must be BaseLLM class or it inherits from BaseLLM
        assert issubclass(self.llm.__class__, BaseLLM)
        self.retrieval_top_k = kwargs.get("retrieval_top_k", 100)
        self.rerank_top_k = kwargs.get("rerank_top_k", 3)
        # Optional semantic cache + the document it is scoped to. The
        # namespace includes the model so switching models never serves an
        # answer another model produced.
        self.cache = kwargs.get("cache")
        self.pdf_hash = kwargs.get("pdf_hash")
        self.cache_namespace = f"{self.pdf_hash or 'default'}:{getattr(self.llm, 'model_name', 'llm')}"

    def run(self, query: str, use_cache: bool = True) -> Answer:
        """Answer `query`. `use_cache=False` forces the full pipeline (used
        when replaying failure cases, which must test the real path).
        """
        query_id = new_trace_id()
        token = observability.query_id_var.set(query_id)
        try:
            return self._run(query, query_id, use_cache)
        except Exception as error:
            logger.exception("query_id=%s stage=failed error=%r", query_id, error)
            observability.record_query_metrics(
                {"query_id": query_id, "query": query, "steps": {}, "issues": []},
                pdf_hash=self.pdf_hash,
                error=repr(error),
            )
            observability.record_failure(
                query_id, "exception", query=query, pdf_hash=self.pdf_hash, detail=repr(error)
            )
            raise
        finally:
            observability.query_id_var.reset(token)

    def _answer_from_cache(self, query, query_id, start, lookup) -> Answer:
        entry = lookup["entry"]
        cached = entry["payload"]
        total_ms = (time.perf_counter() - start) * 1000
        saved = (cached.get("usage") or {}).get("estimated_cost_usd", 0.0) or 0.0
        cache_info = {
            "hit": True,
            "similarity": lookup["similarity"],
            "matched_query": entry["query"],
            "age_s": round(time.time() - entry["created"], 1),
            "saved_cost_usd": saved,
        }
        rerank_step = {**cached["rerank_step"], "duration_ms": 0.0}
        record = {
            "query_id": query_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "steps": {
                "retrieve": {"duration_ms": 0.0, "docs_retrieved": 0, "from_cache": True},
                "rerank": rerank_step,
                "generate": {
                    "duration_ms": 0.0,
                    "answer": cached["answer"],
                    "reasoning": cached.get("reasoning"),
                    "usage": None,
                },
            },
            # Zero spend on a hit; what it *would* have cost is in cache.saved_cost_usd.
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
            "total_duration_ms": round(total_ms, 1),
            "issues": [],
            "status": "ok",
            "cache": cache_info,
        }
        logger.info(
            "query_id=%s stage=cache status=hit similarity=%s matched_query=%r "
            "total_duration_ms=%.1f saved_cost_usd=%.5f",
            query_id, lookup["similarity"], entry["query"], total_ms, saved,
        )
        record_query_trace(query_id, record)
        observability.record_query_metrics(record, pdf_hash=self.pdf_hash, cache=cache_info)
        return Answer(
            answer=cached["answer"],
            contexts=cached["contexts"],
            issues=[],
            reasoning=cached.get("reasoning"),
            trace=record,
        )

    def _run(self, query: str, query_id: str, use_cache: bool) -> Answer:
        start = time.perf_counter()
        logger.info("query_id=%s stage=start query=%r", query_id, query)

        cache_info = {"hit": False}
        if self.cache and use_cache:
            with traced_stage(logger, "cache_lookup", query_id=query_id) as info:
                lookup = self.cache.lookup(self.cache_namespace, query)
                info["hit"] = lookup["hit"]
                info["best_similarity"] = lookup["similarity"]
            if lookup["hit"]:
                return self._answer_from_cache(query, query_id, start, lookup)
            cache_info["similarity"] = lookup["similarity"]

        # Retrieve documents
        retrieve_start = time.perf_counter()
        with traced_stage(logger, "retrieve", query_id=query_id) as info:
            relevant_docs, relevant_meta = self.retrieval.retrieve(
                query, top_k=self.retrieval_top_k
            )
            info["docs_retrieved"] = len(relevant_docs)
        retrieve_ms = (time.perf_counter() - retrieve_start) * 1000

        # Rerank documents
        scores = []
        rerank_ms = 0.0
        top_score = None
        if self.rerank:
            rerank_start = time.perf_counter()
            with traced_stage(logger, "rerank", query_id=query_id) as info:
                reranked_docs, scores = self.rerank.rerank(
                    query, relevant_docs, top_k=self.rerank_top_k
                )
                info["docs_after_rerank"] = len(reranked_docs)
                top_score = float(scores[0]) if scores else None
                info["top_score"] = round(top_score, 4) if top_score is not None else None
            rerank_ms = (time.perf_counter() - rerank_start) * 1000
            if top_score is not None and top_score <= 0:
                logger.warning(
                    "query_id=%s stage=rerank status=low_relevance top_score=%.4f "
                    "reason=no_document_cleared_positive_score",
                    query_id,
                    top_score,
                )
        else:
            reranked_docs = relevant_docs
            logger.warning(
                "query_id=%s stage=rerank status=skipped reason=no_rerank_configured",
                query_id,
            )

        if not reranked_docs:
            logger.warning("query_id=%s stage=context status=empty", query_id)

        # Generate answer
        prompt = ANSWER_PROMPT.format(query=query, context="\n".join(reranked_docs))
        generate_start = time.perf_counter()
        with traced_stage(logger, "generate", query_id=query_id) as info:
            gen_result = self.llm.generate_with_reasoning(prompt)
            answer = gen_result["content"]
            reasoning = gen_result.get("reasoning")
            usage = gen_result.get("usage")
            info["answer_len"] = len(answer) if answer else 0
            info["has_reasoning"] = reasoning is not None
        generate_ms = (time.perf_counter() - generate_start) * 1000

        total_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "query_id=%s stage=complete status=ok total_duration_ms=%.1f",
            query_id,
            total_ms,
        )

        issues, _ = detect_issues(relevant_docs, reranked_docs, scores, answer)
        record = {
            "query_id": query_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "steps": {
                "retrieve": {
                    "duration_ms": round(retrieve_ms, 1),
                    "top_k": self.retrieval_top_k,
                    "docs_retrieved": len(relevant_docs),
                    "documents_preview": [preview_text(d) for d in relevant_docs],
                },
                "rerank": {
                    "duration_ms": round(rerank_ms, 1),
                    "docs_after_rerank": len(reranked_docs),
                    "top_score": round(top_score, 4) if top_score is not None else None,
                    "documents": [
                        {
                            "text": preview_text(doc),
                            "score": round(float(score), 4) if scores else None,
                        }
                        for doc, score in zip(
                            reranked_docs, scores or [None] * len(reranked_docs)
                        )
                    ],
                },
                "generate": {
                    "duration_ms": round(generate_ms, 1),
                    "answer": answer,
                    "reasoning": reasoning,
                    "usage": usage,
                },
            },
            "usage": usage,
            "total_duration_ms": round(total_ms, 1),
            "issues": issues,
            "status": "issues_found" if issues else "ok",
            "cache": cache_info if self.cache else None,
        }
        record_query_trace(query_id, record)
        observability.record_query_metrics(record, pdf_hash=self.pdf_hash, cache=cache_info)
        if issues:
            observability.record_failure(
                query_id,
                "issue:" + issues[0]["type"],
                query=query,
                answer=answer,
                pdf_hash=self.pdf_hash,
                detail="; ".join(i["type"] for i in issues),
                issues=issues,
            )
        elif self.cache and use_cache and answer and answer.strip():
            # Only clean, grounded answers are cached: never freeze a
            # low-relevance/empty-context answer into the cache.
            self.cache.store(
                self.cache_namespace,
                query,
                {
                    "answer": answer,
                    "reasoning": reasoning,
                    "contexts": reranked_docs,
                    "usage": usage,
                    "rerank_step": record["steps"]["rerank"],
                },
            )

        return Answer(
            answer=answer,
            contexts=reranked_docs,
            issues=issues,
            reasoning=reasoning,
            trace=record,
        )
