import os
import sys

from dotenv import load_dotenv

from rag.data_helper import PDFReader
from rag.llm import GroqLLM
from rag.pipeline import Answer, SimpleRAGPipeline
from rag.rerank import CrossEncoderRerank
from rag.retrieval import EmbeddingRetrieval
from rag.text_utils import text2chunk

load_dotenv()

RESUME_PATH = sys.argv[1] if len(sys.argv) > 1 else "resume.pdf"


def build_pipeline(pdf_path: str) -> SimpleRAGPipeline:
    contents = PDFReader(pdf_paths=[pdf_path]).read()
    text = " ".join(contents)
    chunks = text2chunk(text, chunk_size=200, overlap=50)
    print(f"Loaded '{pdf_path}' into {len(chunks)} chunks.")

    retrieval = EmbeddingRetrieval(documents=chunks)
    llm = GroqLLM()
    rerank = CrossEncoderRerank(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
    return SimpleRAGPipeline(retrieval=retrieval, llm=llm, rerank=rerank)


if __name__ == "__main__":
    if not os.path.exists(RESUME_PATH):
        raise SystemExit(
            f"Resume not found at '{RESUME_PATH}'. "
            "Place your resume PDF there, or pass a path: python main.py path/to/resume.pdf"
        )

    pipeline = build_pipeline(RESUME_PATH)
    print("Ask questions about the resume (Ctrl+C to quit).\n")
    while True:
        query = input("Your question: ")
        if not query.strip():
            continue
        response: Answer = pipeline.run(query)
        print(response.answer)
        print()
