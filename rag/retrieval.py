from abc import ABC
from typing import Optional

import numpy as np
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
