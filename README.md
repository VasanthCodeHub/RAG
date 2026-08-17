# Simple RAG

Ask questions about a PDF (e.g. your resume) using a small retrieval-augmented
generation pipeline: embedding-based (vector) retrieval, cross-encoder
reranking, and Gemini for the answer.

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

Add your Gemini API key to `.env` (get one at https://aistudio.google.com/app/apikey):
```
GOOGLE_API_KEY=your-key-here
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
