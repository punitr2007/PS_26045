import re
import bisect
from typing import List, Tuple, Optional, NamedTuple
from langchain_core.documents import Document
from loguru import logger
import pymupdf as fitz

from .models import SectionCandidate


class TocEntry(NamedTuple):
    """
    A single entry from the PDF's embedded Table of Contents.
    ``level`` mirrors PyMuPDF's TOC level (1 = top-level heading).
    The ``HierarchyBuilder`` uses level to infer node_type rather than
    assuming level-1 always means 'chapter'.
    """
    level: int
    title: str
    page: int


class TocStructuralIndex:
    """
    Builds an authoritative chapter structural index from the PDF's embedded
    Table of Contents via PyMuPDF ``fitz.get_toc()``.

    Primary strategy:
      Reads ``[(level, title, page), ...]`` from the PDF, filters to chapter-
      level entries, and exposes ``get_chapter_for_page(page_no)`` — a bisect
      lookup that maps any page number to its enclosing chapter.  This is
      immune to TOC-text poisoning and regex formatting variations.

    Fallback (no embedded TOC):
      ``has_toc`` returns False; ``CandidateDetector`` then falls back to its
      regex scan, but deduplicates chapter matches so body occurrences are
      preferred over TOC-page occurrences.
    """

    def __init__(self, pdf_path: str):
        self._chapter_entries: List[Tuple[int, str]] = []  # (start_page, label)
        self._toc_entries: List[TocEntry] = []             # full generic TOC entries
        self._toc_boundary_page: int = 0
        self._pages: List[int] = []                         # cached page list for O(log n) lookup
        self._build_index(pdf_path)

    # ------------------------------------------------------------------
    def _build_index(self, pdf_path: str) -> None:
        try:
            doc = fitz.open(pdf_path)
            raw_toc = doc.get_toc()
            doc.close()
            logger.debug(f"Raw TOC from PDF: {raw_toc}")
        except Exception as exc:
            logger.warning(
                f"TocStructuralIndex: failed to open PDF for TOC extraction ({exc}). "
                "Regex fallback will be used."
            )
            return

        if not raw_toc:
            logger.warning(
                "TocStructuralIndex: PDF has no embedded TOC. "
                "Regex fallback with deduplication will be used."
            )
            return

        # Build generic TocEntry list (preserves level for hierarchy inference)
        self._toc_entries = [
            TocEntry(level=level, title=title.strip(), page=page)
            for level, title, page in raw_toc
        ]

        entries: List[Tuple[int, str]] = []
        for level, title, page in raw_toc:
            clean = title.strip()
            # Accept level-1 TOC entries, or any entry whose title names a chapter
            if level == 1 or re.match(r'(?i)chapter\s+[IVXLCDM\d]+', clean):
                entries.append((page, clean.upper()))

        if not entries:
            # Broader fallback: treat all level-1 entries as structural headings
            entries = [
                (page, title.strip().upper())
                for level, title, page in raw_toc
                if level == 1
            ]

        entries.sort(key=lambda x: x[0])
        self._chapter_entries = entries
        # Cache page list once — reused by every get_chapter_for_page() call
        self._pages = [e[0] for e in entries]
        if entries:
            self._toc_boundary_page = entries[0][0]

        logger.info(
            f"TocStructuralIndex: {len(entries)} chapter entries indexed; "
            f"body starts at page {self._toc_boundary_page}."
        )
        for pg, lbl in entries:
            logger.debug(f"  TOC entry -> page {pg}: {lbl!r}")

    # ------------------------------------------------------------------
    @property
    def has_toc(self) -> bool:
        """True when a machine-readable TOC was successfully parsed."""
        return bool(self._chapter_entries)

    @property
    def toc_boundary_page(self) -> int:
        """First body page (chapters start here); 0 when no TOC was found."""
        return self._toc_boundary_page

    def get_chapter_for_page(self, page_no: int) -> Optional[str]:
        """
        Returns the chapter label whose page range covers *page_no*.
        Uses ``bisect_right`` with the pre-cached ``_pages`` list so the
        lookup is O(log n) and rebuilds no intermediate data structures.
        """
        if not self._chapter_entries:
            return None
        idx = bisect.bisect_right(self._pages, page_no) - 1
        return self._chapter_entries[idx][1] if idx >= 0 else None

    def get_entry_for_page(self, page_no: int) -> Optional[TocEntry]:
        """
        Returns the full ``TocEntry`` (level, title, page) for the TOC entry
        whose page range covers *page_no*.

        Unlike ``get_chapter_for_page`` which filters to chapter-level entries,
        this returns the raw generic TOC entry so the ``HierarchyBuilder`` can
        infer what structural level that entry represents for *this* document.
        """
        if not self._toc_entries:
            return None
        toc_pages = [e.page for e in self._toc_entries]
        idx = bisect.bisect_right(toc_pages, page_no) - 1
        return self._toc_entries[idx] if idx >= 0 else None

    @property
    def toc_entries(self) -> List[TocEntry]:
        """All raw TOC entries — useful for document-type inference."""
        return self._toc_entries


class LegalSectionExtractor:
    """
    Assembles validated legal section Document objects with character and page offsets.
    """

    def __init__(self, page_docs: List[Document]):
        self.page_docs = page_docs
        self._build_page_index_map()

    def _build_page_index_map(self):
        """Builds a cumulative character index map to resolve character offsets to page numbers."""
        self.page_offsets = []
        cumulative_len = 0
        full_text_list = []
        for idx, doc in enumerate(self.page_docs):
            page_num = doc.metadata.get("page", idx + 1)
            content = doc.page_content
            start = cumulative_len
            cumulative_len += len(content) + 1  # accounting for join delimiter
            self.page_offsets.append((start, cumulative_len, page_num))
            full_text_list.append(content)
        self.full_text = "\n".join(full_text_list)

    def get_page_range(self, start_idx: int, end_idx: int) -> Tuple[int, int]:
        start_page = 1
        end_page = 1
        for start, end, page in self.page_offsets:
            if start <= start_idx <= end:
                start_page = page
            if start <= end_idx <= end:
                end_page = page
        return start_page, end_page

    def extract_sections(
        self,
        validated_candidates: List[Tuple[SectionCandidate, str]],
        toc_index: Optional[TocStructuralIndex] = None,
    ) -> List[Document]:
        """
        Assembles validated section Documents.

        When *toc_index* is provided and has an embedded TOC, the chapter field
        is resolved authoritatively via ``toc_index.get_chapter_for_page()``
        instead of the regex-derived ``candidate.chapter_ref``.  This is the
        final, accurate chapter assignment step in the pipeline.
        """
        use_toc = toc_index is not None and toc_index.has_toc
        toc_misses = 0

        section_docs: List[Document] = []
        for candidate, text in validated_candidates:
            start_p, end_p = self.get_page_range(candidate.start_char_idx, candidate.end_char_idx)

            # --- Chapter resolution ---
            if use_toc:
                chapter = toc_index.get_chapter_for_page(start_p)  # type: ignore[union-attr]
                if chapter is None:
                    toc_misses += 1
                    # Graceful degradation: fall back to regex-derived ref if available
                    chapter = candidate.chapter_ref or "N/A"
                    logger.debug(
                        f"Section {candidate.section_number} (page {start_p}): "
                        "TOC index returned no chapter — using regex fallback value."
                    )
            else:
                chapter = candidate.chapter_ref or "N/A"

            metadata = {
                "section_number": candidate.section_number,
                "section_title": candidate.section_title,
                "provision_ref": f"Section {candidate.section_number}",
                "chapter": chapter,
                "start_page": start_p,
                "end_page": end_p,
                "token_estimate": len(text.split()),
            }
            doc = Document(page_content=text, metadata=metadata)
            section_docs.append(doc)

        if use_toc and toc_misses:
            logger.warning(
                f"{toc_misses} section(s) had no TOC chapter match for their page — "
                "regex fallback value used for those sections."
            )
        logger.info(f"Extracted {len(section_docs)} validated Legal Section documents.")
        return section_docs
