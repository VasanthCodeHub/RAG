from pypdf import PdfReader as _PdfReader


class PDFReader:
    def __init__(self, pdf_paths: list[str] | str):
        if isinstance(pdf_paths, str):
            pdf_paths = [pdf_paths]
        self.pdf_path = pdf_paths

    def read(self) -> list[str]:
        texts = []
        for pdf_path in self.pdf_path:
            reader = _PdfReader(pdf_path)
            pages = [page.extract_text() or "" for page in reader.pages]
            # Join all pages into a single string by \n\n
            texts.append("\n\n".join(pages))
        return texts


SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md", ".csv", ".json", ".log", ".docx", ".html", ".htm")


def _docx_text(data: bytes) -> str:
    """Extract paragraph text from a .docx (a zip of XML) without extra deps."""
    import io
    import re
    import zipfile
    from xml.etree import ElementTree

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = ["".join(t.text or "" for t in p.iter(f"{ns}t")) for p in root.iter(f"{ns}p")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(paragraphs)).strip()


def _html_text(text: str) -> str:
    import re

    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    return re.sub(r"<[^>]+>", " ", text)


def read_document_bytes(data: bytes, filename: str) -> str:
    """Return the plain text of any supported document (PDF, DOCX, HTML or
    text-like files). PDFs go through the existing `PDFReader` unchanged.
    """
    import os
    import tempfile

    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext or filename}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}")
    if ext == ".pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            return " ".join(PDFReader(pdf_paths=[path]).read())
        finally:
            os.unlink(path)
    if ext == ".docx":
        return _docx_text(data)
    text = data.decode("utf-8", errors="replace")
    return _html_text(text) if ext in (".html", ".htm") else text
