import os
import sys

from dotenv import load_dotenv

from rag.data_helper import read_document_bytes
from rag.llm import GroqLLM
from rag.pipeline import Answer, SimpleRAGPipeline
from rag.rerank import CrossEncoderRerank
from rag.retrieval import EmbeddingRetrieval
from rag.text_utils import text2chunk
from observability.tracing import configure_logging

load_dotenv()
configure_logging()

DOC_PATH = sys.argv[1] if len(sys.argv) > 1 else "document.pdf"


def build_pipeline(pdf_path: str) -> SimpleRAGPipeline:
    with open(pdf_path, "rb") as f:
        text = read_document_bytes(f.read(), pdf_path)
    chunks = text2chunk(text, chunk_size=1000, overlap=200)
    print(f"Loaded '{pdf_path}' into {len(chunks)} chunks.")

    retrieval = EmbeddingRetrieval(documents=chunks)
    llm = GroqLLM()
    rerank = CrossEncoderRerank(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
    return SimpleRAGPipeline(retrieval=retrieval, llm=llm, rerank=rerank)


if __name__ == "__main__":
    if not os.path.exists(DOC_PATH):
        raise SystemExit(
            f"Document not found at '{DOC_PATH}'. "
            "Pass a path: python cli.py path/to/file.(pdf|docx|txt|md|html)"
        )

    pipeline = build_pipeline(DOC_PATH)
    print("Ask questions about the document (Ctrl+C to quit).\n")
    while True:
        query = input("Your question: ")
        if not query.strip():
            continue
        response: Answer = pipeline.run(query)
        print(response.answer)
        print()
