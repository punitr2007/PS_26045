from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from loguru import logger

from structure.models import LegalDocumentConfig, LegalNode
from structure.hierarchy_builder import find_ancestors, flatten_tree


class MetadataEnricher:
    """Enriches section and chunk documents with global legal metadata schema and structural lineage."""

    def __init__(self, config: LegalDocumentConfig):
        self.config = config

    def _get_global_meta(self) -> Dict[str, Any]:
        return {
            "source_id_external": self.config.source_id_external,
            "title": self.config.title,
            "document_type": self.config.document_type,
            "jurisdiction": self.config.jurisdiction,
            "legal_area": self.config.legal_area,
            "authority_level": self.config.authority_level,
            "publication_date": self.config.publication_date,
            "effective_from": self.config.effective_from,
            "status": self.config.status,
            "source_url": self.config.source_url,
            "is_amendment": self.config.is_amendment,
            "parent_document": self.config.parent_document or "",
            "applicable_product": self.config.applicable_product,
        }

    def enrich(self, section_docs: List[Document]) -> List[Document]:
        """Enriches documents with global metadata while preserving and defaulting hierarchy fields."""
        global_meta = self._get_global_meta()

        for doc in section_docs:
            # 1. Apply global configuration metadata
            doc.metadata.update(global_meta)

            # 2. Ensure generic hierarchy fields exist with sensible defaults if not already present
            sec_num = doc.metadata.get("section_number", "")
            sec_title = doc.metadata.get("section_title", "")
            ch = doc.metadata.get("chapter", "N/A")

            hierarchy_defaults = {
                "node_type": doc.metadata.get("node_type", "section"),
                "node_number": doc.metadata.get("node_number", sec_num),
                "node_title": doc.metadata.get("node_title", sec_title),
                "part": doc.metadata.get("part", ""),
                "chapter": ch,
                "section": doc.metadata.get("section", sec_num if doc.metadata.get("node_type", "section") == "section" else ""),
                "article": doc.metadata.get("article", ""),
                "rule": doc.metadata.get("rule", ""),
                "regulation": doc.metadata.get("regulation", ""),
                "subsection": doc.metadata.get("subsection", ""),
                "subrule": doc.metadata.get("subrule", ""),
                "clause": doc.metadata.get("clause", ""),
                "subclause": doc.metadata.get("subclause", ""),
                "start_page": doc.metadata.get("start_page", doc.metadata.get("page", 1)),
                "end_page": doc.metadata.get("end_page", doc.metadata.get("start_page", doc.metadata.get("page", 1))),
                "original_text": doc.metadata.get("original_text", doc.metadata.get("original_content", doc.page_content)),
                "contextual_text": doc.metadata.get("contextual_text", doc.metadata.get("generated_context", "")),
                "parent_id": doc.metadata.get("parent_id", ""),
                "references": doc.metadata.get("references", []),
                "structure_confidence": doc.metadata.get("structure_confidence", 1.0),
            }

            for k, v in hierarchy_defaults.items():
                if k not in doc.metadata:
                    doc.metadata[k] = v

        logger.info(
            f"Metadata Enrichment complete for {len(section_docs)} documents "
            f"[{self.config.source_id_external}: '{self.config.title}']."
        )
        return section_docs

    def enrich_node(self, node: LegalNode, ancestors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Creates a complete metadata dictionary for a single LegalNode."""
        meta = self._get_global_meta()
        anc = ancestors or {}

        meta.update({
            "node_id": node.node_id,
            "node_type": node.node_type,
            "node_number": node.number or "",
            "node_title": node.title or "",
            "section_number": node.number if node.node_type in ("section", "article", "rule") else anc.get("section", anc.get("rule", anc.get("article", ""))),
            "section_title": node.title if node.node_type in ("section", "article", "rule") else anc.get("section_title", ""),
            "chapter": anc.get("chapter", "N/A"),
            "part": anc.get("part", ""),
            "section": node.number if node.node_type == "section" else anc.get("section", ""),
            "article": node.number if node.node_type == "article" else anc.get("article", ""),
            "rule": node.number if node.node_type == "rule" else anc.get("rule", ""),
            "regulation": node.number if node.node_type == "regulation" else anc.get("regulation", ""),
            "subsection": node.number if node.node_type == "subsection" else anc.get("subsection", ""),
            "subrule": node.number if node.node_type == "subrule" else anc.get("subrule", ""),
            "clause": node.number if node.node_type == "clause" else anc.get("clause", ""),
            "subclause": node.number if node.node_type == "subclause" else anc.get("subclause", ""),
            "start_page": node.start_page,
            "end_page": node.end_page,
            "original_text": node.original_text or node.text,
            "contextual_text": node.text,
            "parent_id": node.parent_id or "",
            "references": node.references or [],
            "structure_confidence": node.confidence,
        })
        return meta

