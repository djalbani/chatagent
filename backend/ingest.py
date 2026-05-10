"""Document ingestion: extract text, chunk, prepare for RAG."""
import io
import re
import uuid
from pathlib import Path


# ── Text extraction ────────────────────────────────────────────────────────────

def extract_text(content: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(content)
    elif ext == ".docx":
        return _extract_docx(content)
    elif ext in (".txt", ".md", ".rst"):
        return content.decode("utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: pdf, docx, txt, md")


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p.strip() for p in pages if p.strip())


def _extract_docx(content: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(content))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 600,
    overlap_words: int = 60,
) -> list[str]:
    """Split text into overlapping chunks. Returns non-empty chunks only."""
    # Normalise whitespace
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
                # carry overlap into next chunk
                words = current.split()
                overlap = " ".join(words[-overlap_words:]) if len(words) > overlap_words else current
                current = (overlap + "\n\n" + para).strip()
            else:
                # paragraph itself is longer than chunk_size — split by sentence
                for sent in re.split(r"(?<=[.!?])\s+", para):
                    if len(current) + len(sent) + 1 <= chunk_size:
                        current = (current + " " + sent).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = sent

    if current:
        chunks.append(current)

    return [c for c in chunks if len(c) > 80]


# ── Public API ─────────────────────────────────────────────────────────────────

def process_file(
    content: bytes,
    filename: str,
    source_name: str | None = None,
) -> list[dict]:
    """
    Extract text from a file, chunk it, and return records ready for RAG.
    Each record has: id, content, source, filename, chunk_id.
    """
    source = (source_name or filename).strip()
    text = extract_text(content, filename)

    if not text.strip():
        raise ValueError("No readable text found in this file.")

    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("File produced no usable text chunks.")

    return [
        {
            "id": f"{source}__{i}__{uuid.uuid4().hex[:8]}",
            "content": chunk,
            "source": source,
            "filename": filename,
            "chunk_id": i,
        }
        for i, chunk in enumerate(chunks)
    ]
