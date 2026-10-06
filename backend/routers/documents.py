import hashlib
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend import store
from backend.schemas import DocumentIngestResponse
from rag.data_helper import read_document_bytes
from rag.llm import GroqLLM
from rag.pipeline import SimpleRAGPipeline
from rag.rerank import CrossEncoderRerank
from rag.semantic_cache import get_shared_cache
from rag.retrieval import ChromaRetrieval, _load_chroma_client
from rag.text_utils import text2chunk

router = APIRouter(tags=["documents"])

CHROMA_PERSIST_DIR = ".chroma_data"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _collection_name(pdf_hash: str) -> str:
    return f"doc-{pdf_hash}"


def _already_ingested(collection_name: str) -> int:
    """Returns the existing chunk count, or 0 if the collection doesn't
    exist yet / is empty. Checked directly against the on-disk Chroma
    client so this works even after an API server restart, when the
    in-memory `api.store` cache is empty but the vector data survives.
    """
    client = _load_chroma_client(CHROMA_PERSIST_DIR)
    try:
        return client.get_collection(name=collection_name).count()
    except Exception:
        return 0


def _build_pipeline(retrieval, pdf_hash: str, groq_api_key: str | None) -> SimpleRAGPipeline:
    return SimpleRAGPipeline(
        retrieval=retrieval,
        llm=GroqLLM(api_key=groq_api_key or None),
        rerank=CrossEncoderRerank(model_name=CROSS_ENCODER_MODEL),
        cache=get_shared_cache(),
        pdf_hash=pdf_hash,
    )


def rehydrate(pdf_hash: str) -> dict | None:
    """Rebuild the in-memory pipeline for a document whose vectors are still
    on disk (e.g. after an API restart), using the server's GROQ_API_KEY.
    Returns the store entry, or None if the document was never ingested.
    """
    collection_name = _collection_name(pdf_hash)
    n_chunks = _already_ingested(collection_name)
    if not n_chunks:
        return None
    retrieval = ChromaRetrieval(collection_name=collection_name, persist_dir=CHROMA_PERSIST_DIR)
    entry = {"pipeline": _build_pipeline(retrieval, pdf_hash, None), "filename": "(restored)", "n_chunks": n_chunks}
    store.put(pdf_hash, entry)
    return entry


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(file: UploadFile = File(...), groq_api_key: str = Form("")):
    start = time.perf_counter()
    pdf_bytes = await file.read()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()[:32]
    collection_name = _collection_name(pdf_hash)

    n_existing = _already_ingested(collection_name)
    from_cache = n_existing > 0

    if from_cache:
        retrieval = ChromaRetrieval(collection_name=collection_name, persist_dir=CHROMA_PERSIST_DIR)
        n_chunks = n_existing
    else:
        try:
            text = read_document_bytes(pdf_bytes, file.filename)
        except ValueError as error:
            raise HTTPException(status_code=415, detail=str(error))
        if not text.strip():
            raise HTTPException(status_code=422, detail="No extractable text found in this document.")
        chunks = text2chunk(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        retrieval = ChromaRetrieval(
            collection_name=collection_name, persist_dir=CHROMA_PERSIST_DIR, documents=chunks
        )
        n_chunks = len(chunks)

    pipeline = _build_pipeline(retrieval, pdf_hash, groq_api_key)
    store.put(
        pdf_hash,
        {"pipeline": pipeline, "filename": file.filename, "n_chunks": n_chunks},
    )

    duration_ms = (time.perf_counter() - start) * 1000
    return DocumentIngestResponse(
        pdf_hash=pdf_hash,
        filename=file.filename,
        n_chunks=n_chunks,
        from_cache=from_cache,
        duration_ms=round(duration_ms, 1),
    )
