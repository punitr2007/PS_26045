import os
import csv
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()



class SectionCandidate(BaseModel):
    section_number: str
    section_title: str
    start_char_idx: int
    end_char_idx: int
    chapter_ref: Optional[str] = None


class LegalDocumentConfig(BaseModel):
    pdf_path: str = "patent.pdf"
    source_id_external: str = "IN-PAT-001"
    title: str = "The Patents Act, 1970"
    document_type: str = "act"
    jurisdiction: str = "india"
    legal_area: str = "patent"
    authority_level: int = 0
    publication_date: str = "1970-09-19"
    effective_from: str = "1972-04-20"
    status: str = "active"
    source_url: str = "https://www.ipindia.gov.in/pages/patents/publications/acts"
    collection_name: str = "legal_acts"
    qdrant_url: Optional[str] = os.getenv("CLUSTER_ENDPOINT")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    # Embedding Provider Toggle: "gemini" or "huggingface"
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "gemini")
    embedding_model: Optional[str] = None  # auto-defaults to models/gemini-embedding-001 or BAAI/bge-small-en-v1.5
    
    chunk_size: int = 1000
    chunk_overlap: int = 200
    enable_contextual_retrieval: bool = True
    is_amendment: bool = False
    parent_document: Optional[str] = None
    is_ingested: bool = False
    applicable_product: str = "all"
    llm_model: str = "openai/gpt-oss-120b"
    gen_model: str = "gemma-4-31b-it"

    @classmethod
    def from_csv_row(cls, row: Dict[str, Any], base_dir: str = ".") -> "LegalDocumentConfig":
        """Builds a LegalDocumentConfig from a CSV row dictionary."""
        def parse_bool(val: Any, default: bool = False) -> bool:
            if isinstance(val, bool):
                return val
            if val is None:
                return default
            if isinstance(val, (int, float)):
                return bool(val)
            if isinstance(val, str):
                v = val.strip().lower()
                if v in ("true", "1", "yes", "y", "t"):
                    return True
                if v in ("false", "0", "no", "n", "f", ""):
                    return False
            return default

        raw_pdf_path = str(row.get("pdf_path", "")).strip()
        clean_path = raw_pdf_path.lstrip("/\\")
        resolved_pdf_path = clean_path

        if clean_path:
            dir_name = os.path.dirname(clean_path)
            file_name = os.path.basename(clean_path)
            
            # Generate potential filename variants (e.g. handle multi-ID comma-separated names)
            name_variants = [file_name]
            if "," in file_name:
                ext = os.path.splitext(file_name)[1]
                base_parts = file_name[: -len(ext) if ext else len(file_name)].split(",")
                for part in base_parts:
                    part = part.strip()
                    if part:
                        name_variants.append(part + ext)
            
            path_candidates = []
            for nv in name_variants:
                sub_clean = os.path.join(dir_name, nv) if dir_name else nv
                path_candidates.extend([
                    sub_clean,
                    os.path.join(base_dir, sub_clean),
                    os.path.join("data", sub_clean),
                    os.path.join("..", "data", sub_clean),
                ])
            
            for p in path_candidates:
                if os.path.isfile(p):
                    resolved_pdf_path = p
                    break

            # If not directly found, check directory listing with whitespace normalization
            if not os.path.isfile(resolved_pdf_path):
                import re
                for search_dir in [
                    os.path.join(base_dir, dir_name) if dir_name else base_dir,
                    os.path.join("data", dir_name) if dir_name else "data",
                    os.path.join("data", "abs"),
                ]:
                    if os.path.isdir(search_dir):
                        dir_files = {re.sub(r"\s+", " ", f.lower()): f for f in os.listdir(search_dir)}
                        for nv in name_variants:
                            norm_nv = re.sub(r"\s+", " ", nv.lower())
                            if norm_nv in dir_files:
                                candidate = os.path.join(search_dir, dir_files[norm_nv])
                                if os.path.isfile(candidate):
                                    resolved_pdf_path = candidate
                                    break
                        if os.path.isfile(resolved_pdf_path):
                            break

        if not os.path.isfile(resolved_pdf_path) and row.get("source_id_external"):
            # If path not resolved to a file, attempt resolution by source_id_external.pdf
            sid = str(row.get("source_id_external", "")).strip()
            sid_candidates = [sid]
            if "/" in sid:
                sid_candidates.extend([s.strip() for s in sid.split("/") if s.strip()])
            for sid_cand in sid_candidates:
                for cand in [
                    os.path.join(base_dir, f"{sid_cand}.pdf"),
                    os.path.join(base_dir, "abs", f"{sid_cand}.pdf"),
                    os.path.join("data", "abs", f"{sid_cand}.pdf"),
                    os.path.join("..", "data", "abs", f"{sid_cand}.pdf"),
                ]:
                    if os.path.isfile(cand):
                        resolved_pdf_path = cand
                        break
                if os.path.isfile(resolved_pdf_path):
                    break

        provider = str(row.get("embedding_provider", "")).strip().lower() or os.getenv("EMBEDDING_PROVIDER", "gemini")
        model = str(row.get("embedding_model", "")).strip() or None

        return cls(
            pdf_path=resolved_pdf_path,
            source_id_external=str(row.get("source_id_external", "")).strip(),
            title=str(row.get("title", "")).strip(),
            document_type=str(row.get("document_type", "act")).strip(),
            jurisdiction=str(row.get("jurisdiction", "india")).strip(),
            legal_area=str(row.get("legal_area", "patent")).strip(),
            authority_level=int(row.get("authority_level", 0)) if str(row.get("authority_level", "")).isdigit() else 0,
            publication_date=str(row.get("publication_date", "")).strip(),
            effective_from=str(row.get("effective_from", "")).strip(),
            status=str(row.get("status", "active")).strip(),
            source_url=str(row.get("source_url", "")).strip(),
            collection_name=str(row.get("collection_name", "legal_acts")).strip() or "legal_acts",
            embedding_provider=provider,
            embedding_model=model,
            enable_contextual_retrieval=parse_bool(row.get("enable_contextual_retrieval"), True),
            is_amendment=parse_bool(row.get("is_amendment"), False),
            parent_document=str(row.get("parent_document", "")).strip() or None,
            is_ingested=parse_bool(row.get("is_ingested"), False),
            applicable_product=str(row.get("applicable_product") or row.get("applicable_products") or "all").strip(),
            chunk_size=int(row.get("chunk_size", 1000)) if str(row.get("chunk_size", "")).isdigit() else 1000,
            chunk_overlap=int(row.get("chunk_overlap", 200)) if str(row.get("chunk_overlap", "")).isdigit() else 200,
        )

    @classmethod
    def load_from_csv(cls, csv_path: str) -> List["LegalDocumentConfig"]:
        """Loads a list of LegalDocumentConfig instances from a CSV file."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found at: {csv_path}")

        base_dir = os.path.dirname(csv_path) or "."
        configs: List["LegalDocumentConfig"] = []
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row or not row.get("source_id_external"):
                    continue
                configs.append(cls.from_csv_row(row, base_dir=base_dir))
        return configs


# ---------------------------------------------------------------------------
# Generic Legal Candidate — replaces SectionCandidate in new code paths
# ---------------------------------------------------------------------------

class LegalCandidate(BaseModel):
    """
    Generic structural unit detected from a legal document.

    ``node_type`` is open-ended: section, chapter, part, article, rule,
    regulation, subsection, subrule, clause, subclause, paragraph, heading, …

    ``detection_method`` records *how* this candidate was found so we can
    trace and audit detection quality:
        "toc"              → confirmed by embedded TOC entry
        "heading_sentinel" → identified by pdfplumber font/size tagging
        "regex"            → pure text regex (least reliable)
        "legacy"           → converted from old SectionCandidate
    """

    node_type: str
    number: Optional[str] = None
    title: Optional[str] = None

    start_char_idx: int
    end_char_idx: int

    confidence: float = 0.0
    detection_method: Optional[str] = None
    parent_hint: Optional[str] = None   # e.g. "CHAPTER II" when known from context


# ---------------------------------------------------------------------------
# Legal Node — node in the final legal hierarchy tree
# ---------------------------------------------------------------------------

class LegalNode(BaseModel):
    """
    A single node in the validated legal hierarchy tree.

    ``original_text`` is the exact text slice from the source document.
    It must NEVER be rewritten or modified after assignment.

    ``text`` may contain contextual prefix (used for embedding), but
    ``original_text`` is always the authoritative verbatim source.
    """

    node_id: str                         # deterministic: "{source_id}_{type}_{number}"
    node_type: str

    number: Optional[str] = None
    title: Optional[str] = None

    text: str = ""                        # contextual representation (for embedding)
    original_text: str = ""              # NEVER modified after extraction

    start_char_idx: int = 0
    end_char_idx: int = 0

    start_page: Optional[int] = None
    end_page: Optional[int] = None

    confidence: float = 0.0
    parent_id: Optional[str] = None
    children: List["LegalNode"] = []
    references: List[str] = []           # detected cross-references, e.g. ["Section 8", "Rule 5"]

    model_config = {"arbitrary_types_allowed": True}


# Required for Pydantic v2 self-referential model
LegalNode.model_rebuild()


# ---------------------------------------------------------------------------
# Backward Compatibility Shim
# ---------------------------------------------------------------------------

def section_candidate_to_legal_candidate(sc: "SectionCandidate") -> LegalCandidate:
    """
    Converts an old ``SectionCandidate`` to a ``LegalCandidate`` so that
    legacy callers can be gradually migrated without breaking changes.
    """
    return LegalCandidate(
        node_type="section",
        number=sc.section_number,
        title=sc.section_title,
        start_char_idx=sc.start_char_idx,
        end_char_idx=sc.end_char_idx,
        confidence=0.85,
        detection_method="legacy",
        parent_hint=sc.chapter_ref,
    )

