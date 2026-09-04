# Simple RAG

Ask questions about a PDF (e.g. your resume) using a small retrieval-augmented
generation pipeline: embedding-based (vector) retrieval, cross-encoder
reranking, and Groq for the answer.

## Pre-requisites

- Python 3.9+
- Poppler (needed for PDF text extraction)

Install Poppler:
```bash
# Debian/Ubuntu
sudo apt install build-essential libpoppler-cpp-dev pkg-config python3-dev

# Fedora/RHEL
sudo yum install gcc-c++ pkgconfig poppler-cpp-devel python3-devel

# macOS
brew install pkg-config poppler python

# Windows (using conda)
conda install -c conda-forge poppler
```

## Setup

```bash
pip install -e .
cp .env.example .env
```

Add your Groq API key to `.env` (get one at https://console.groq.com/keys):
```
GROQ_API_KEY=your-key-here
```

## Usage

Drop your PDF in the project root as `resume.pdf`, then run:
```bash
python main.py
```

Or point it at any PDF:
```bash
python main.py path/to/file.pdf
```

You'll get a prompt to ask questions about the document.

## Web UI (FastAPI backend + Streamlit frontend)

The web UI is two processes: a FastAPI backend (pipeline, vector DB, judge, eval)
and a Streamlit frontend that talks to it over HTTP. Run both, in two terminals:

```bash
# Terminal 1 — API backend (loads the embedding/rerank models on first request)
.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — Streamlit frontend
.venv/Scripts/python.exe -m streamlit run app.py --server.port 8501
```

Open http://localhost:8501. Upload a PDF, ask questions, and use "Rate this
answer" to run the LLM judge and add your own score. The **Evaluation** page
(in the sidebar nav) runs the judge calibration check and the before/after
regression suite, and shows every rating you've saved.

Uploaded PDFs are chunked and embedded into a persistent [Chroma](https://www.trychroma.com/)
collection under `.chroma_data/`, keyed by a hash of the file's bytes — so
re-uploading the same PDF (even after restarting the backend) skips
re-embedding entirely.
