import functools
from abc import ABC

from sentence_transformers import CrossEncoder


@functools.lru_cache(maxsize=4)
def _load_cross_encoder(model_name: str) -> CrossEncoder:
    """Loading a CrossEncoder's weights from disk takes seconds -- share one
    cached instance per model name instead of re-loading it every time a
    `CrossEncoderRerank` is constructed (e.g. every document upload).
    """
    return CrossEncoder(model_name)


class BaseRerank(ABC):

    def __init__(self, *args, **kwargs):
        pass

    def rerank(
        self, query: str, documents: list[str], top_k: int = 10
    ) -> tuple[list, list]:
        raise NotImplementedError


class CrossEncoderRerank(BaseRerank):
    def __init__(self, *args, **kwargs):
        """Initialize the Cross-Encoder reranker.
        - model_name: str: The name of the model to use."""
        super().__init__(*args, **kwargs)
        if "model_name" not in kwargs:
            raise ValueError("Please provide a model_name.")
        self.model = _load_cross_encoder(kwargs["model_name"])

    def rerank(
        self, query: str, documents: list[str], top_k: int = 10
    ) -> tuple[list, list]:
        """Rerank the documents based on the query.
        - query: str: The query to rerank the documents with.
        - documents: list[str]: The documents to rerank.
        - top_k: int: The number of documents to return.
        """
        cross_inp = [[query, passage] for passage in documents]
        cross_scores = self.model.predict(cross_inp)
        # sorted by cross-encoder scores desc
        sorted_idx = sorted(
            range(len(documents)), key=lambda i: cross_scores[i], reverse=True
        )
        top_idx = sorted_idx[:top_k]
        relevants = [documents[i] for i in top_idx]
        scores = [cross_scores[i] for i in top_idx]
        return relevants, scores
