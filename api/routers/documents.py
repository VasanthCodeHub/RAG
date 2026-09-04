import hashlib
import tempfile
import time

from fastapi import APIRouter, File, Form, UploadFile

from api import store
from api.schemas import DocumentIngestResponse
from rag.data_helper import PDFReader
from rag.llm import GroqLLM
from rag.pipeline import SimpleRAGPipeline
from rag.rerank import CrossEncoderRerank
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


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(file: UploadFile = File(...), groq_api_key: str = Form(...)):
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
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        contents = PDFReader(pdf_paths=[tmp_path]).read()
        text = " ".join(contents)
        chunks = text2chunk(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        retrieval = ChromaRetrieval(
            collection_name=collection_name, persist_dir=CHROMA_PERSIST_DIR, documents=chunks
        )
        n_chunks = len(chunks)

    rerank = CrossEncoderRerank(model_name=CROSS_ENCODER_MODEL)
    llm = GroqLLM(api_key=groq_api_key)
    pipeline = SimpleRAGPipeline(retrieval=retrieval, llm=llm, rerank=rerank)

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
