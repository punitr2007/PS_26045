import os
import csv
from typing import Optional, Tuple, List, Dict, Any
from loguru import logger
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from structure.models import LegalDocumentConfig, SectionCandidate, LegalCandidate, LegalNode
from loaders.pdf_loader import LegalPDFLoader
from structure.section_extractor import TocStructuralIndex, LegalSectionExtractor
from structure.candidate_detector import CandidateDetector
from structure.validator import ContextValidator
from structure.hierarchy_builder import HierarchyBuilder, flatten_tree
from metadata.enricher import MetadataEnricher
from chunking.chunker import LegalChunker, LegalHierarchyChunker
from vectorstore.manager import VectorStoreManager


class LegalIngestionPipeline:
    """
    Executes the legal document ingestion pipeline for single or multiple documents:
    - Ingests from a single LegalDocumentConfig, or batch ingests from a CSV manifest.
    - Connects directly to Qdrant Cloud Vector Database.
    - Skips documents already ingested in the shared Qdrant collection unless force_reingest=True.
    - V2 Universal Architecture:
        PDF -> PdfPlumberLoader (font/heading sentinels) ->
        Generic Candidate Detection (Part/Chapter/Section/Article/Rule/Regulation) ->
        Context Validation -> Hierarchy Building (Tree Synthesis) ->
        Hierarchical Chunking (breadcrumbs + original_text preservation) ->
        Metadata Enrichment -> Qdrant Cloud
    - V1 Legacy Architecture available via use_v2=False or --legacy flag.
    """

    def __init__(self, config: Optional[LegalDocumentConfig] = None):
        self.config = config or LegalDocumentConfig()

    def ingest_document(
        self,
        config: LegalDocumentConfig,
        force_reingest: bool = False,
        use_v2: bool = True,
    ) -> Tuple[List[Any], List[Document], Optional[QdrantVectorStore]]:
        """Ingests a single legal document based on its configuration into Qdrant Cloud."""
        logger.info(
            f"=== Processing Document [{config.source_id_external}]: '{config.title}' "
            f"({config.document_type.upper()}) [Pipeline V{'2' if use_v2 else '1'}] ==="
        )
        vector_mgr = VectorStoreManager(config)

        # 0. Check if this specific document is already ingested
        if not force_reingest and vector_mgr.is_document_already_ingested(config.source_id_external):
            vector_store = vector_mgr.get_vector_store()
            logger.info(
                f"Document [{config.source_id_external}] already exists in Qdrant collection "
                f"'{config.collection_name}'. Skipping re-ingestion."
            )
            return [], [], vector_store

        # 1. Verify PDF existence
        if not os.path.exists(config.pdf_path):
            logger.error(
                f"PDF file not found for [{config.source_id_external}] at path: '{config.pdf_path}'. "
                f"Please ensure the file is present."
            )
            return [], [], None

        # 2. Load document (PDF or TXT)
        loader = LegalPDFLoader(config.pdf_path)
        page_docs = loader.load()

        is_txt = config.pdf_path.lower().endswith(".txt")

        if is_txt:
            # TXT files are already clean rich text — skip all PDF-specific structure
            # extraction (TOC, candidate detection, section splitting). Treat the
            # loaded docs directly as sections.
            logger.info(
                f"TXT document detected — bypassing structure extraction pipeline. "
                f"Treating {len(page_docs)} loaded doc(s) as sections directly."
            )
            section_docs = page_docs
            enricher = MetadataEnricher(config)
            enriched_sections = enricher.enrich(section_docs)
            chunker = LegalChunker(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                enable_contextual_retrieval=config.enable_contextual_retrieval,
                llm_model=config.llm_model,
                gen_model=config.gen_model
            )
            chunks = chunker.chunk_sections(enriched_sections)
            vector_store = vector_mgr.store_documents(chunks)
            return enriched_sections, chunks, vector_store

        # ==================================================================
        # V2 UNIVERSAL PIPELINE PATH
        # ==================================================================
        if use_v2:
            # 3. Build TOC structural index for authoritative chapter assignment
            toc_index = TocStructuralIndex(config.pdf_path)

            # 4. Generic Candidate Detection (Font sentinels + generic patterns)
            extractor_helper = LegalSectionExtractor(page_docs)
            detector = CandidateDetector()
            candidates = detector.detect_generic_candidates(
                extractor_helper.full_text,
                toc_index=toc_index,
            )

            # 5. Generic Validation
            validator = ContextValidator()
            validated_candidates = validator.validate_candidates(candidates, extractor_helper.full_text)
            low_conf_count = sum(1 for c in validated_candidates if c.confidence < 0.70)
            rejected_count = len(candidates) - len(validated_candidates)

            # 6. Hierarchy Building (Tree Synthesis)
            hierarchy_builder = HierarchyBuilder(source_id=config.source_id_external)
            roots = hierarchy_builder.build(
                candidates=validated_candidates,
                page_resolver=extractor_helper.get_page_range,
                toc_index=toc_index,
            )
            flat_nodes = flatten_tree(roots)

            # 7. Hierarchical Chunking (preserves lineage + original_text)
            chunker = LegalHierarchyChunker(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                enable_contextual_retrieval=config.enable_contextual_retrieval,
                llm_model=config.llm_model,
                gen_model=config.gen_model,
            )
            raw_chunks = chunker.chunk_nodes(
                roots=roots,
                full_text=extractor_helper.full_text,
                doc_config=config,
            )

            # 8. Metadata Enrichment
            enricher = MetadataEnricher(config)
            enriched_chunks = enricher.enrich(raw_chunks)

            # 9. Embeddings & Qdrant Cloud Storage
            vector_store = vector_mgr.store_documents(enriched_chunks)

            # 10. Summary Log Block
            logger.info("\n" + "=" * 60)
            logger.info(f"DOCUMENT INGESTION SUMMARY (V2) — [{config.source_id_external}]")
            logger.info(f"Title:         {config.title}")
            logger.info(f"Pages:         {len(page_docs)} | TOC: {'detected' if toc_index.has_toc else 'none'}")
            logger.info(f"Candidates:    {len(candidates)} total | Accepted: {len(validated_candidates)} | Low-conf: {low_conf_count} | Rejected: {rejected_count}")
            logger.info(f"Legal Nodes:   {len(flat_nodes)} (Roots: {len(roots)})")
            logger.info(f"Final Chunks:  {len(enriched_chunks)} in collection '{config.collection_name}'")
            logger.info("=" * 60 + "\n")

            return roots, enriched_chunks, vector_store

        # ==================================================================
        # V1 LEGACY PIPELINE PATH
        # ==================================================================
        # 3. Build TOC structural index for authoritative chapter assignment
        toc_index = TocStructuralIndex(config.pdf_path)

        # 4. Candidate Detection (Legacy)
        extractor_helper = LegalSectionExtractor(page_docs)
        detector = CandidateDetector()
        candidates = detector.detect_candidates(
            extractor_helper.full_text,
            toc_index=toc_index,
        )

        # 5. Context Validation (Legacy)
        validator = ContextValidator()
        validated: List[Tuple[SectionCandidate, str]] = []
        for cand in candidates:
            res = validator.validate_and_clean(cand, extractor_helper.full_text)
            if res:
                validated.append(res)
        logger.info(f"Context Validation: {len(validated)} valid sections retained.")

        # 6. Legal Sections extraction & chapter resolution
        section_docs = extractor_helper.extract_sections(validated, toc_index=toc_index)

        # 7. Metadata Enrichment
        enricher = MetadataEnricher(config)
        enriched_sections = enricher.enrich(section_docs)

        # 8. Recursive Chunking & Contextual Retrieval
        chunker = LegalChunker(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            enable_contextual_retrieval=config.enable_contextual_retrieval,
            llm_model=config.llm_model,
            gen_model=config.gen_model
        )
        chunks = chunker.chunk_sections(enriched_sections)

        # 9. Embeddings & Qdrant Cloud Storage
        vector_store = vector_mgr.store_documents(chunks)

        logger.info(
            f"=== Successfully Ingested [{config.source_id_external}]: "
            f"{len(enriched_sections)} sections, {len(chunks)} chunks into Qdrant '{config.collection_name}' ==="
        )
        return enriched_sections, chunks, vector_store

    def ingest_from_csv(
        self,
        csv_path: str = "data/legal_documents.csv",
        force_reingest: bool = False,
        update_csv_status: bool = True,
        use_v2: bool = True,
    ) -> Dict[str, Any]:
        """
        Batch ingests all documents listed in the specified CSV manifest into Qdrant Cloud.
        Updates the CSV manifest with `is_ingested=TRUE` for completed documents.
        """
        logger.info(f"=== Starting Multi-Document Ingestion from CSV: '{csv_path}' [Pipeline V{'2' if use_v2 else '1'}] ===")
        doc_configs = LegalDocumentConfig.load_from_csv(csv_path)
        logger.info(f"Discovered {len(doc_configs)} document entries in CSV manifest.")

        results_summary: Dict[str, Any] = {
            "total_documents": len(doc_configs),
            "successful_documents": [],
            "skipped_documents": [],
            "failed_documents": [],
            "total_sections_ingested": 0,
            "total_chunks_ingested": 0,
            "vector_store": None
        }

        last_vector_store: Optional[QdrantVectorStore] = None
        completed_ids = set()

        for idx, doc_config in enumerate(doc_configs, 1):
            logger.info(f"\n[{idx}/{len(doc_configs)}] Ingestion Task: {doc_config.source_id_external} - {doc_config.title}")

            if not force_reingest and doc_config.is_ingested:
                logger.info(f"Manifest indicates [{doc_config.source_id_external}] is already ingested. Skipping.")
                results_summary["skipped_documents"].append(doc_config.source_id_external)
                continue

            try:
                sections, chunks, store = self.ingest_document(
                    doc_config, force_reingest=force_reingest, use_v2=use_v2
                )
                if store is not None:
                    last_vector_store = store

                if chunks:
                    results_summary["successful_documents"].append(doc_config.source_id_external)
                    results_summary["total_sections_ingested"] += len(sections)
                    results_summary["total_chunks_ingested"] += len(chunks)
                    completed_ids.add(doc_config.source_id_external)
                elif store is not None:
                    results_summary["skipped_documents"].append(doc_config.source_id_external)
                else:
                    results_summary["failed_documents"].append(doc_config.source_id_external)

            except Exception as e:
                logger.error(f"Failed to ingest document [{doc_config.source_id_external}]: {e}")
                results_summary["failed_documents"].append(doc_config.source_id_external)

        results_summary["vector_store"] = last_vector_store

        # Update CSV manifest with ingestion status
        if update_csv_status and completed_ids:
            self._update_csv_status(csv_path, completed_ids)

        logger.info("\n" + "=" * 60)
        logger.info("BATCH INGESTION SUMMARY (QDRANT CLOUD):")
        logger.info(f"Total Configured:   {results_summary['total_documents']}")
        logger.info(f"Newly Ingested:     {len(results_summary['successful_documents'])} ({results_summary['successful_documents']})")
        logger.info(f"Skipped / Existing: {len(results_summary['skipped_documents'])} ({results_summary['skipped_documents']})")
        logger.info(f"Failed / Missing:   {len(results_summary['failed_documents'])} ({results_summary['failed_documents']})")
        logger.info(f"Total Chunks Added: {results_summary['total_chunks_ingested']}")
        logger.info("=" * 60 + "\n")

        return results_summary

    def _update_csv_status(self, csv_path: str, completed_ids: set) -> None:
        """Updates the is_ingested column in the CSV file for successfully processed documents."""
        try:
            rows: List[Dict[str, Any]] = []
            fieldnames = []
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                for row in reader:
                    if row.get("source_id_external") in completed_ids:
                        row["is_ingested"] = "TRUE"
                    rows.append(row)

            if fieldnames:
                with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                logger.info(f"Updated CSV manifest '{csv_path}' with completed ingestion status.")
        except Exception as e:
            logger.warning(f"Could not update CSV manifest status: {e}")

    def run(
        self,
        force_reingest: bool = False,
        csv_path: Optional[str] = None,
        use_v2: bool = True,
    ) -> Tuple[List[Any], List[Document], Optional[QdrantVectorStore]]:
        """
        Runs the ingestion pipeline:
        - If csv_path is provided, performs multi-document batch ingestion into Qdrant.
        - Otherwise, ingests the single document configured in self.config into Qdrant.
        """
        if csv_path:
            summary = self.ingest_from_csv(csv_path, force_reingest=force_reingest, use_v2=use_v2)
            return [], [], summary.get("vector_store")

        return self.ingest_document(self.config, force_reingest=force_reingest, use_v2=use_v2)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Legal Document Ingestion Pipeline for Qdrant Cloud")
    parser.add_argument("--csv", type=str, default="data/legal_documents.csv", help="Path to CSV manifest file")
    parser.add_argument("--pdf", type=str, default=None, help="Path to single PDF document to ingest")
    parser.add_argument("--force", action="store_true", help="Force re-ingestion even if already present")
    parser.add_argument("--legacy", action="store_true", help="Use legacy V1 section-only ingestion pipeline")
    parser.add_argument("--type" , type=str , default=None , choices=["legal","trademark"])
    args = parser.parse_args()

    pipeline = None

    if(getattr(args , "type" , None)):
        if args.type == "legal":
            pipeline = LegalIngestionPipeline()
        elif args.type == "trademark":
            pipeline = TrademarkIngestionPipeline()
        else:
            raise ValueError(f"Invalid type: {args.type}")

    use_v2 = not args.legacy

    if getattr(args, "pdf", None):
        # Ingest specific single PDF
        config = LegalDocumentConfig(pdf_path=args.pdf)
        pipeline.ingest_document(config, force_reingest=args.force, use_v2=use_v2)
    elif args.csv:
        if not os.path.exists(args.csv):
            print(f"\n[ERROR] CSV file not found: '{args.csv}'")
            if os.path.exists("data"):
                print(f"Files currently in data/ directory: {os.listdir('data')}")
        else:
            # Ingest batch from CSV manifest
            pipeline.ingest_from_csv(csv_path=args.csv, force_reingest=args.force, use_v2=use_v2)
    else:
        # Ingest default document
        pipeline.run(force_reingest=args.force, use_v2=use_v2)


if __name__ == "__main__":
    main()


