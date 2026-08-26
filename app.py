import os
import tempfile

import streamlit as st
from dotenv import load_dotenv

from rag.data_helper import PDFReader
from rag.llm import GroqLLM
from rag.pipeline import SimpleRAGPipeline
from rag.rerank import CrossEncoderRerank
from rag.retrieval import EmbeddingRetrieval
from rag.text_utils import text2chunk
from rag.tracing import configure_logging

load_dotenv()
configure_logging()

st.set_page_config(page_title="Simple RAG", page_icon="📄")
st.title("📄 Simple RAG — ask questions about a PDF")

with st.sidebar:
    st.subheader("Settings")
    api_key_input = st.text_input(
        "Groq API key",
        value=os.getenv("GROQ_API_KEY", ""),
        type="password",
        help="Get one at https://console.groq.com/keys",
    )
    if api_key_input:
        os.environ["GROQ_API_KEY"] = api_key_input

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])


@st.cache_resource(show_spinner="Building pipeline...")
def build_pipeline(pdf_bytes: bytes, api_key: str):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    contents = PDFReader(pdf_paths=[tmp_path]).read()
    text = " ".join(contents)
    chunks = text2chunk(text, chunk_size=1000, overlap=200)

    retrieval = EmbeddingRetrieval(documents=chunks)
    llm = GroqLLM(api_key=api_key)
    rerank = CrossEncoderRerank(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
    pipeline = SimpleRAGPipeline(retrieval=retrieval, llm=llm, rerank=rerank)
    return pipeline, len(chunks)


if "messages" not in st.session_state:
    st.session_state.messages = []

if not uploaded_file:
    st.info("Upload a PDF to get started.")
    st.stop()

if not os.getenv("GROQ_API_KEY"):
    st.warning("Enter your Groq API key in the sidebar to continue.")
    st.stop()

pipeline, n_chunks = build_pipeline(uploaded_file.getvalue(), os.environ["GROQ_API_KEY"])
st.caption(f"Loaded '{uploaded_file.name}' into {n_chunks} chunks.")

for role, content in st.session_state.messages:
    with st.chat_message(role):
        st.markdown(content)

query = st.chat_input("Ask a question about the document...")
if query:
    st.session_state.messages.append(("user", query))
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = pipeline.run(query)
        st.markdown(response.answer)
        with st.expander("Sources used"):
            for i, ctx in enumerate(response.contexts, 1):
                st.markdown(f"**Chunk {i}:** {ctx}")

    st.session_state.messages.append(("assistant", response.answer))
