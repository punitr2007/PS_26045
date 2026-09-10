import os
from collections import Counter
from typing import List, Optional

from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader
from loguru import logger


# ---------------------------------------------------------------------------
# pdfplumber-based PDF loader (font-aware heading detection)
# ---------------------------------------------------------------------------

class PdfPlumberLoader:
    """
    Loads a PDF using pdfplumber and tags lines that are visually distinct
    (larger than the modal body font size, or bold) with sentinel markers::

        <<<HEADING>>>Section 3. What are not inventions.<<<END_HEADING>>>

    This lets CandidateDetector match structural headings purely by visual
    evidence rather than fragile text patterns — body text that coincidentally
    looks like a heading (e.g. "12. The applicant shall...") is invisible to
    the detector because it lacks the sentinel tags.

    Falls back to PyMuPDF-style page-by-page plain text if pdfplumber fails.
    """

    HEADING_START = "<<<HEADING>>>"
    HEADING_END = "<<<END_HEADING>>>"

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed — falling back to PyMuPDF plain text loader.")
            return self._pymupdf_fallback()

        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"PDF file not found at: {self.file_path}")

        logger.info(f"Loading PDF with pdfplumber (font-aware): {self.file_path}")
        docs: List[Document] = []

        try:
            with pdfplumber.open(self.file_path) as pdf:
                total_pages = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, start=1):
                    words = page.extract_words(
                        extra_attrs=["size", "fontname"],
                        x_tolerance=3,
                        y_tolerance=3,
                    )
                    if not words:
                        continue

                    # Compute modal (most common) body font size for this page.
                    # Headings are typically larger OR bold.
                    sizes = [round(float(w.get("size", 0))) for w in words if w.get("size")]
                    modal_size = Counter(sizes).most_common(1)[0][0] if sizes else 12

                    # Group words by Y-coordinate (line)
                    lines: dict = {}
                    for w in words:
                        y_key = round(float(w.get("top", 0)))
                        lines.setdefault(y_key, []).append(w)

                    text_parts: List[str] = []
                    for y_key in sorted(lines):
                        line_words = lines[y_key]
                        line_text = " ".join(w["text"] for w in line_words)

                        # Determine if this line is visually a heading:
                        # condition 1 — font size larger than modal body size
                        max_size = max(
                            round(float(w.get("size", 0))) for w in line_words
                        )
                        # condition 2 — any word is in a bold font
                        is_bold = any(
                            "bold" in str(w.get("fontname", "")).lower()
                            for w in line_words
                        )

                        if max_size > modal_size or is_bold:
                            text_parts.append(
                                f"\n{self.HEADING_START}{line_text}{self.HEADING_END}"
                            )
                        else:
                            text_parts.append(line_text)

                    page_text = "\n".join(text_parts)
                    docs.append(Document(
                        page_content=page_text,
                        metadata={
                            "page": page_num,
                            "source": self.file_path,
                            "modal_font_size": modal_size,
                            "total_pages": total_pages,
                        }
                    ))

            logger.info(f"pdfplumber: loaded {len(docs)} pages from '{self.file_path}'.")
            return docs

        except Exception as exc:
            logger.warning(
                f"pdfplumber extraction failed ({exc}). "
                "Falling back to PyMuPDF plain text loader."
            )
            return self._pymupdf_fallback()

    def _pymupdf_fallback(self) -> List[Document]:
        """PyMuPDF plain-text fallback — no heading sentinels, raw text only."""
        try:
            from langchain_community.document_loaders import PyMuPDFLoader
            logger.info(f"PyMuPDF fallback loader: {self.file_path}")
            loader = PyMuPDFLoader(file_path=self.file_path, extract_images=False)
            docs = loader.load()
            logger.info(f"PyMuPDF fallback: loaded {len(docs)} pages.")
            return docs
        except Exception as exc:
            logger.error(f"PyMuPDF fallback also failed: {exc}")
            return []


# ---------------------------------------------------------------------------
# Text loader
# ---------------------------------------------------------------------------

class LegalTextLoader:
    """Loads .txt files (OCR output or plain legal text)."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"TXT file not found at: {self.file_path}")
        logger.info(f"Loading txt document: {self.file_path}")
        loader = TextLoader(file_path=self.file_path, encoding="utf-8", autodetect_encoding=True)
        docs = loader.load()
        logger.info(f"Successfully loaded {len(docs)} pages from TXT.")
        return docs


# ---------------------------------------------------------------------------
# Unified loader (backwards-compatible entry point)
# ---------------------------------------------------------------------------

class LegalPDFLoader:
    """
    Unified legal document loader.

    Routes to the appropriate backend based on file extension:
      .pdf → PdfPlumberLoader (font-aware, heading-sentinel tagging)
      .txt → LegalTextLoader  (plain text, already clean)

    The public API (``load() -> List[Document]``) is unchanged.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        ext = os.path.splitext(self.file_path)[1].lower().lstrip(".")

        if ext == "txt":
            return LegalTextLoader(self.file_path).load()

        if ext == "pdf":
            return PdfPlumberLoader(self.file_path).load()

        raise ValueError(
            f"Unsupported file extension '.{ext}' for '{self.file_path}'. "
            "Supported: .pdf, .txt"
        )