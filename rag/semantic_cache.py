"""Semantic cache for repeated questions.

A repeat of (or close paraphrase of) a question already answered for the
same document returns the stored answer instead of re-running retrieve +
rerank + generate -- no LLM tokens spent, millisecond latency.

Lookup order: exact normalized-text match (free), then cosine similarity of
sentence embeddings against that namespace's entries. Entries are keyed by
`namespace` (document hash + model), so an answer never leaks across
documents.

Tradeoff to know about: similarity is not equivalence. "Who is X?" and
"Who is Y?" embed close together, so the default threshold is strict (0.92)
and only clean answers are cached (see SimpleRAGPipeline). Tune with
RAG_CACHE_THRESHOLD; disable with RAG_CACHE_ENABLED=0.

Persistence: append-only JSONL (survives API restarts), compacted on
eviction / invalidation / load.
"""

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np

logger = logging.getLogger("rag.cache")

DEFAULT_PATH = ".cache/semantic_cache.jsonl"
DEFAULT_THRESHOLD = 0.92
DEFAULT_TTL_S = 7 * 24 * 3600
DEFAULT_MAX_ENTRIES = 500


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower())).strip()


def _default_embed(text: str) -> np.ndarray:
    from rag.retrieval import _load_sentence_transformer

    model = _load_sentence_transformer("all-MiniLM-L6-v2")
    return model.encode(text, convert_to_numpy=True, normalize_embeddings=True)


class SemanticCache:
    def __init__(
        self,
        path: str | Path | None = None,
        threshold: float | None = None,
        ttl_s: float | None = None,
        max_entries: int | None = None,
        embed_fn: Callable[[str], np.ndarray] | None = None,
    ):
        self.path = Path(path or os.getenv("RAG_CACHE_FILE", DEFAULT_PATH))
        self.threshold = (
            threshold if threshold is not None
            else float(os.getenv("RAG_CACHE_THRESHOLD", DEFAULT_THRESHOLD))
        )
        self.ttl_s = (
            ttl_s if ttl_s is not None else float(os.getenv("RAG_CACHE_TTL_S", DEFAULT_TTL_S))
        )
        self.max_entries = max_entries or int(os.getenv("RAG_CACHE_MAX_ENTRIES", DEFAULT_MAX_ENTRIES))
        self._embed = embed_fn or _default_embed
        self._lock = threading.Lock()
        self._entries: list[dict] = []
        self._load()

    # -- persistence -------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        now = time.time()
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if now - entry["created"] <= self.ttl_s:
                    entry["vec"] = np.asarray(entry["vec"], dtype=np.float32)
                    self._entries.append(entry)
        self._entries = self._entries[-self.max_entries:]
        logger.info("semantic cache loaded entries=%d path=%s", len(self._entries), self.path)

    def _serialize(self, entry: dict) -> str:
        return json.dumps({**entry, "vec": [round(float(x), 5) for x in entry["vec"]]}, ensure_ascii=False)

    def _compact(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for entry in self._entries:
                f.write(self._serialize(entry) + "\n")
        os.replace(tmp, self.path)

    # -- API ---------------------------------------------------------------

    def lookup(self, namespace: str, query: str) -> dict:
        """Returns {"hit": bool, "similarity": float|None, "entry": dict|None}.
        `similarity` is the best score seen even on a miss, so near-misses
        are visible in logs when tuning the threshold.
        """
        now = time.time()
        norm = normalize(query)
        with self._lock:
            candidates = [
                e for e in self._entries
                if e["namespace"] == namespace and now - e["created"] <= self.ttl_s
            ]
        if not candidates:
            return {"hit": False, "similarity": None, "entry": None}
        for entry in candidates:
            if entry["norm"] == norm:
                return {"hit": True, "similarity": 1.0, "entry": entry}
        query_vec = self._embed(query)
        matrix = np.stack([e["vec"] for e in candidates])
        sims = matrix @ query_vec
        best = int(np.argmax(sims))
        similarity = round(float(sims[best]), 4)
        if similarity >= self.threshold:
            return {"hit": True, "similarity": similarity, "entry": candidates[best]}
        return {"hit": False, "similarity": similarity, "entry": None}

    def store(self, namespace: str, query: str, payload: dict) -> None:
        entry = {
            "namespace": namespace,
            "query": query,
            "norm": normalize(query),
            "vec": np.asarray(self._embed(query), dtype=np.float32),
            "created": time.time(),
            "payload": payload,
        }
        with self._lock:
            # Same question re-stored (e.g. after a cache-bypassing replay)
            # replaces the old answer instead of piling up duplicates.
            self._entries = [
                e for e in self._entries
                if not (e["namespace"] == namespace and e["norm"] == entry["norm"])
            ]
            self._entries.append(entry)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]
                self._compact()
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(self._serialize(entry) + "\n")

    def invalidate(self, namespace_prefix: str | None = None) -> int:
        """Drop every entry (or those whose namespace starts with the prefix,
        e.g. one document hash). Returns how many were removed.
        """
        with self._lock:
            before = len(self._entries)
            if namespace_prefix is None:
                self._entries = []
            else:
                self._entries = [
                    e for e in self._entries if not e["namespace"].startswith(namespace_prefix)
                ]
            self._compact()
            return before - len(self._entries)

    def stats(self) -> dict:
        with self._lock:
            by_ns: dict[str, int] = {}
            for e in self._entries:
                by_ns[e["namespace"]] = by_ns.get(e["namespace"], 0) + 1
        return {
            "entries": sum(by_ns.values()),
            "namespaces": by_ns,
            "threshold": self.threshold,
            "ttl_s": self.ttl_s,
            "max_entries": self.max_entries,
        }


_shared: SemanticCache | None = None


def get_shared_cache() -> SemanticCache | None:
    """Process-wide cache, or None when RAG_CACHE_ENABLED=0."""
    global _shared
    if os.getenv("RAG_CACHE_ENABLED", "1").lower() in ("0", "false", "no", ""):
        return None
    if _shared is None:
        _shared = SemanticCache()
    return _shared
