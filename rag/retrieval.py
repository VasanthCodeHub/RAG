from abc import ABC
from typing import Optional

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


class BaseRetrieval(ABC):

    def __init__(self, *args, **kwargs):
        pass

    def ingest(
        self, documents: list[str], metadata: Optional[list[dict]] = None
    ) -> bool:
        raise NotImplementedError

    def retrieve(self, query: str, top_k: int = 10) -> list[dict]:
        raise NotImplementedError

    def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        # Some retrieval models might not need reranking
        raise NotImplementedError("This retrieval model does not support reranking.")


class EmbeddingRetrieval(BaseRetrieval):

    def __init__(self, *args, **kwargs):
        """Initialize the embedding-based (vector) retrieval model.
        - documents: list[str]: The list of documents to ingest.
        - metadata: list[dict]: The metadata associated with the documents.
        - model_name: str: The sentence-transformers embedding model to use.
        """
        super().__init__(*args, **kwargs)
        documents = kwargs.get("documents")
        metadata = kwargs.get("metadata")
        if not documents:
            raise ValueError("Please provide a list of documents.")
        self.model = SentenceTransformer(
            kwargs.get("model_name", "all-MiniLM-L6-v2")
        )
        self.embeddings = None
        self.documents = None
        self.metadata = None
        self.__ingest__(documents, metadata)

    def __ingest__(self, documents: list[str], metadata=None):
        """Embed and ingest the documents.
        - documents: list[str]: The list of documents to ingest.
        - metadata: list[dict]: The metadata associated with the documents.
        """
        assert len(documents) > 0, "List of documents is empty."
        if metadata is not None:
            assert len(documents) == len(
                metadata
            ), "Length of metadata should be same as length of documents."
        embeddings = self.model.encode(
            documents, convert_to_numpy=True, normalize_embeddings=True
        )
        self.embeddings = embeddings
        self.metadata = metadata
        self.documents = documents
        return True

    def retrieve(self, query: str, top_k: int = 10):
        """Retrieve the top-k most semantically similar documents to the query.
        - query: str: The query to retrieve the documents with.
        - top_k: int: The number of documents to return.
        """
        if self.embeddings is None:
            raise RuntimeError(
                "Embedding index has not been initialized. Call ingest() first."
            )
        query_embedding = self.model.encode(
            query, convert_to_numpy=True, normalize_embeddings=True
        )
        # Embeddings are normalized, so dot product == cosine similarity.
        scores = self.embeddings @ query_embedding
        top_n = np.argsort(scores)[::-1][:top_k]
        metadata = None
        if self.metadata:
            metadata = [self.metadata[i] for i in top_n]
        documents = [self.documents[i] for i in top_n]
        return documents, metadata


class HybridRetrieval(BaseRetrieval):
    """Combines BM25 (lexical/keyword) and embedding (semantic) retrieval.

    BM25 catches exact keyword/term overlap that an embedding model can miss
    (e.g. a rare term like "subrogation"); the embedding side catches
    paraphrases that share no words at all (e.g. "get their money back" ->
    "reimbursement"). Combining both covers more failure modes than either
    alone.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the hybrid retrieval model.
        - documents: list[str]: The list of documents to ingest.
        - metadata: list[dict]: The metadata associated with the documents.
        - model_name: str: The sentence-transformers embedding model to use.
        - alpha: float in [0, 1]: weight given to the vector score vs the
          BM25 score when combining. alpha=1.0 -> pure vector search,
          alpha=0.0 -> pure BM25. Defaults to 0.5 (equal weight).
        """
        super().__init__(*args, **kwargs)
        documents = kwargs.get("documents")
        metadata = kwargs.get("metadata")
        if not documents:
            raise ValueError("Please provide a list of documents.")
        self.alpha = kwargs.get("alpha", 0.5)
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be between 0.0 and 1.0.")
        self.embedding_model = SentenceTransformer(
            kwargs.get("model_name", "all-MiniLM-L6-v2")
        )
        self.bm25 = None
        self.embeddings = None
        self.documents = None
        self.metadata = None
        self.__ingest__(documents, metadata)

    def __ingest__(self, documents: list[str], metadata=None):
        """Build both the BM25 index and the embedding index.
        - documents: list[str]: The list of documents to ingest.
        - metadata: list[dict]: The metadata associated with the documents.
        """
        assert len(documents) > 0, "List of documents is empty."
        if metadata is not None:
            assert len(documents) == len(
                metadata
            ), "Length of metadata should be same as length of documents."
        tokenized_docs = [doc.lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        self.embeddings = self.embedding_model.encode(
            documents, convert_to_numpy=True, normalize_embeddings=True
        )
        self.documents = documents
        self.metadata = metadata
        return True

    @staticmethod
    def _normalize(scores: np.ndarray) -> np.ndarray:
        """Min-max normalize a query's scores to [0, 1] so BM25's unbounded
        scale and cosine similarity's [-1, 1] scale can be weighted together.
        """
        lo, hi = scores.min(), scores.max()
        if hi - lo < 1e-12:
            return np.zeros_like(scores)
        return (scores - lo) / (hi - lo)

    def retrieve(self, query: str, top_k: int = 10):
        """Retrieve the top-k documents by combined BM25 + embedding score.
        - query: str: The query to retrieve the documents with.
        - top_k: int: The number of documents to return.
        """
        if self.bm25 is None or self.embeddings is None:
            raise RuntimeError(
                "Hybrid index has not been initialized. Call ingest() first."
            )
        bm25_scores = np.asarray(self.bm25.get_scores(query.lower().split()))
        query_embedding = self.embedding_model.encode(
            query, convert_to_numpy=True, normalize_embeddings=True
        )
        vector_scores = self.embeddings @ query_embedding

        combined_scores = self.alpha * self._normalize(vector_scores) + (
            1 - self.alpha
        ) * self._normalize(bm25_scores)

        top_n = np.argsort(combined_scores)[::-1][:top_k]
        metadata = None
        if self.metadata:
            metadata = [self.metadata[i] for i in top_n]
        documents = [self.documents[i] for i in top_n]
        return documents, metadata
