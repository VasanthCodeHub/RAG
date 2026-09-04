import logging
import time
from abc import ABC
from datetime import datetime, timezone

from .llm import BaseLLM
from .prompt import ANSWER_PROMPT
from .rerank import BaseRerank
from .retrieval import BaseRetrieval
from .tracing import detect_issues, new_trace_id, preview_text, record_query_trace, traced_stage

logger = logging.getLogger("rag.pipeline")


class Answer:
    def __init__(self, answer: str, contexts: list[str], issues: list[dict] | None = None):
        self.answer = answer
        self.contexts = contexts
        self.issues = issues or []


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

    def run(self, query: str) -> Answer:
        query_id = new_trace_id()
        start = time.perf_counter()
        logger.info("query_id=%s stage=start query=%r", query_id, query)

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
            answer = self.llm.generate(prompt)
            info["answer_len"] = len(answer) if answer else 0
        generate_ms = (time.perf_counter() - generate_start) * 1000

        total_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "query_id=%s stage=complete status=ok total_duration_ms=%.1f",
            query_id,
            total_ms,
        )

        issues, _ = detect_issues(relevant_docs, reranked_docs, scores, answer)
        record_query_trace(
            query_id,
            {
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
                    },
                },
                "total_duration_ms": round(total_ms, 1),
                "issues": issues,
                "status": "issues_found" if issues else "ok",
            },
        )

        return Answer(answer=answer, contexts=reranked_docs, issues=issues)
