import os
import json
import time
import random
import hashlib
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from loguru import logger

from .contextual_prompt import CONTEXTUAL_PROMPT

load_dotenv()




class LegalChunker:
    """
    Splits legal sections using RecursiveCharacterTextSplitter with legal delimiters,
    preserving full section context & metadata in every chunk, and optionally enriching
    each chunk with situated contextual retrieval summaries.

    Resilience & Performance:
      - Persistent On-Disk Cache (data/.context_cache.json): zero repeat API calls
      - Primary Model: Gemini (ChatGoogleGenerativeAI)
      - Fallback Model: Groq (ChatGroq qwen/qwen3.6-27b)
      - Instant Structural Fallback: If APIs hit rate limits, seamlessly uses authoritative
        statutory heading without blocking execution.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        enable_contextual_retrieval: bool = True,
        llm_model: str = "openai/gpt-oss-120b",
        gen_model: str = "gemini-2.5-flash",
        fallback_model: str = "qwen/qwen3.6-27b",
        max_retries: int = 2,
        cache_path: str = "data/.context_cache.json",
    ):
        self.delimiters = ["\n\n", "\n(?=\\([a-z0-9]+\\))", "\n", ";\n", ";", ".", " "]
        self.splitter = RecursiveCharacterTextSplitter(
            separators=self.delimiters,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            is_separator_regex=True,
        )
        self.enable_contextual_retrieval = enable_contextual_retrieval
        self.llm_model = llm_model
        self.gen_model = gen_model or "gemini-2.5-flash"
        if not fallback_model or "safeguard" in fallback_model.lower():
            fallback_model = "qwen/qwen3.6-27b"
        self.fallback_model = fallback_model
        self.max_retries = max_retries
        self.cache_path = cache_path

        # Load or initialize on-disk cache
        self.cache: Dict[str, str] = self._load_cache()

        # Initialize clients
        self.primary_client = self._create_primary_client() if self.enable_contextual_retrieval else None
        self.fallback_client = self._create_fallback_client() if self.enable_contextual_retrieval else None

    # ------------------------------------------------------------------
    # Persistent Disk Cache Helpers
    # ------------------------------------------------------------------

    def _load_cache(self) -> Dict[str, str]:
        """Loads cached contextual summaries from local disk."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} cached contextual summaries from '{self.cache_path}'.")
                    return data
            except Exception as e:
                logger.warning(f"Could not load cache file '{self.cache_path}': {e}")
        return {}

    def _save_cache(self):
        """Persists cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist cache to '{self.cache_path}': {e}")

    @staticmethod
    def _compute_cache_key(parent_context: str, chunk_content: str) -> str:
        """Computes a deterministic hash for a given parent context and chunk."""
        content = f"{parent_context.strip()}|||{chunk_content.strip()}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # LLM Clients
    # ------------------------------------------------------------------

    def _create_primary_client(self) -> Optional[ChatGoogleGenerativeAI]:
        """Creates the primary Gemini generative client."""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found. Primary contextual generation client disabled.")
            return None
        try:
            return ChatGoogleGenerativeAI(model=self.gen_model, google_api_key=api_key, temperature=0.0)
        except Exception as e:
            logger.error(f"Failed to initialize ChatGoogleGenerativeAI primary client: {e}")
            return None

    def _create_fallback_client(self) -> Optional[ChatGroq]:
        """Creates the fallback Groq generative client."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not found. Fallback contextual generation client disabled.")
            return None
        try:
            return ChatGroq(model=self.fallback_model, groq_api_key=api_key, temperature=0.0)
        except Exception as e:
            logger.error(f"Failed to initialize ChatGroq fallback client: {e}")
            return None

    # ------------------------------------------------------------------
    # Context Generation with Resilience
    # ------------------------------------------------------------------

    def create_gen_chunk_context(
        self,
        whole_document_context: str,
        chunk_content: str,
        sec_num: str = "",
        sec_title: str = "",
        chapter: str = "",
        doc_title: str = "",
    ) -> str:
        """
        Generates contextual summary using:
          1. Local Disk Cache check (0.001s, 0 API calls)
          2. Primary Gemini model (with bounded retry)
          3. Fallback Groq model (with bounded retry)
          4. Deterministic Statutory Structural Fallback (instant)
        """
        cache_key = self._compute_cache_key(whole_document_context, chunk_content)
        if cache_key in self.cache:
            logger.debug(f"[Cache Hit] Reusing cached contextual summary for key {cache_key[:8]}...")
            return self.cache[cache_key]

        # Truncate whole_document_context to max 3500 chars to avoid TPM token overflows
        truncated_doc_context = whole_document_context[:3500]
        prompt_text = CONTEXTUAL_PROMPT.format(
            WHOLE_DOCUMENT=truncated_doc_context,
            CHUNK_CONTENT=chunk_content
        )
        messages = [HumanMessage(content=prompt_text)]

        # --- Tier 1: Try Primary (Gemini) ---
        if self.primary_client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = self.primary_client.invoke(messages)
                    if response and hasattr(response, "text") and response.text:
                        res_text = response.text.strip()
                        self.cache[cache_key] = res_text
                        self._save_cache()
                        return res_text
                    elif response and hasattr(response, "content") and response.content:
                        res_text = str(response.content).strip()
                        self.cache[cache_key] = res_text
                        self._save_cache()
                        return res_text
                except Exception as e:
                    logger.warning(f"[Primary - Gemini] Attempt {attempt}/{self.max_retries} failed: {e}")
                    if attempt < self.max_retries:
                        time.sleep(1.5)

        # --- Tier 2: Try Fallback (Groq) ---
        if self.fallback_client:
            logger.info(f"[Failover] Trying fallback model '{self.fallback_model}' on Groq...")
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = self.fallback_client.invoke(messages)
                    if response and hasattr(response, "content") and response.content:
                        res_text = str(response.content).strip()
                        self.cache[cache_key] = res_text
                        self._save_cache()
                        return res_text
                except Exception as e:
                    logger.warning(f"[Fallback - Groq] Attempt {attempt}/{self.max_retries} failed: {e}")
                    if attempt < self.max_retries:
                        time.sleep(1.5)

        # --- Tier 3: Deterministic Statutory Structural Fallback ---
        # Immediate fallback: generates rich statutory contextual sentence
        logger.warning(f"[Tier 3 Fallback] Using structural legal context for Section {sec_num}.")
        structural_context = (
            f"This chunk is part of {doc_title}, Chapter {chapter}, "
            f"Section {sec_num}: '{sec_title}'."
        )
        self.cache[cache_key] = structural_context
        self._save_cache()
        return structural_context

    # ------------------------------------------------------------------
    # Chunking Execution
    # ------------------------------------------------------------------

    def chunk_sections(self, section_docs: List[Document]) -> List[Document]:
        all_chunks: List[Document] = []
        for s_idx, sec_doc in enumerate(section_docs):
            sec_chunks = self.splitter.split_documents([sec_doc])
            total_sec_chunks = len(sec_chunks)
            sec_num = sec_doc.metadata.get("section_number", f"sec_{s_idx}")
            sec_title = sec_doc.metadata.get("section_title", "")
            chapter = sec_doc.metadata.get("chapter", "N/A")
            doc_title = sec_doc.metadata.get("title", "The Patents Act, 1970")

            parent_context = (
                f"Document: {doc_title}\n"
                f"Chapter: {chapter}\n"
                f"Section: {sec_num} ({sec_title})\n\n"
                f"Full Section Text:\n{sec_doc.page_content}"
            )

            for c_idx, chunk in enumerate(sec_chunks):
                original_text = chunk.page_content

                gen_context = ""
                if self.enable_contextual_retrieval:
                    logger.info(
                        f"Generating contextual retrieval info for Section {sec_num} "
                        f"chunk {c_idx+1}/{total_sec_chunks}..."
                    )
                    gen_context = self.create_gen_chunk_context(
                        whole_document_context=parent_context,
                        chunk_content=original_text,
                        sec_num=sec_num,
                        sec_title=sec_title,
                        chapter=chapter,
                        doc_title=doc_title,
                    )

                chunk.metadata["chunk_index"] = c_idx
                chunk.metadata["total_chunks_in_section"] = total_sec_chunks
                chunk.metadata["chunk_id"] = f"{sec_doc.metadata.get('source_id_external', 'DOC')}_Sec{sec_num}_c{c_idx}"
                chunk.metadata["original_content"] = original_text
                chunk.metadata["generated_context"] = gen_context

                chunk.page_content = f"{gen_context}\n\n{original_text}" if gen_context else original_text
                all_chunks.append(chunk)

        logger.info(f"Recursive Chunking: Created {len(all_chunks)} chunks from {len(section_docs)} sections.")
        return all_chunks


# ---------------------------------------------------------------------------
# Phase 3: Generic Hierarchy-Based Legal Chunker (V2)
# ---------------------------------------------------------------------------

def strip_sentinels(text: str) -> str:
    """Removes <<<HEADING>>> and <<<END_HEADING>>> sentinels from text."""
    if not text:
        return ""
    import re
    return re.sub(r'<<<END_HEADING>>>|<<<HEADING>>>', '', text).strip()


class LegalHierarchyChunker(LegalChunker):
    """
    Hierarchical legal chunker operating on LegalNode tree structures.
    Preserves hierarchical lineage (Part -> Chapter -> Section -> Subsection -> Clause),
    verbatim original_text, and contextual retrieval information.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        enable_contextual_retrieval: bool = True,
        llm_model: str = "openai/gpt-oss-120b",
        gen_model: str = "gemini-2.5-flash",
        fallback_model: str = "qwen/qwen3.6-27b",
        max_retries: int = 2,
        cache_path: str = "data/.context_cache.json",
    ):
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            enable_contextual_retrieval=enable_contextual_retrieval,
            llm_model=llm_model,
            gen_model=gen_model,
            fallback_model=fallback_model,
            max_retries=max_retries,
            cache_path=cache_path,
        )

    def _split_text_semantically(self, text: str) -> List[str]:
        """
        Splits text by paragraphs (\\n\\n) first.
        If a paragraph exceeds chunk_size, splits with recursive character splitter.
        """
        if len(text) <= self.splitter._chunk_size:
            return [text]

        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(para) > self.splitter._chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_len = 0
                sub_chunks = self.splitter.split_text(para)
                chunks.extend(sub_chunks)
            else:
                if current_len + len(para) + 2 > self.splitter._chunk_size and current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = [para]
                    current_len = len(para)
                else:
                    current_chunk.append(para)
                    current_len += len(para) + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [text]

    def chunk_nodes(
        self,
        roots: List[Any],
        full_text: Optional[str] = None,
        doc_config: Optional[Any] = None,
    ) -> List[Document]:
        """
        Transforms a hierarchy of LegalNode objects into a list of chunk Documents.
        
        Args:
            roots: Root nodes of the legal document tree.
            full_text: Optional full document text (used to populate original_text if empty).
            doc_config: Optional configuration with global metadata and title.
            
        Returns:
            List of LangChain Documents enriched with full hierarchy metadata.
        """
        from structure.hierarchy_builder import flatten_tree, find_ancestors
        from structure.models import LegalNode

        all_nodes = flatten_tree(roots)
        if not all_nodes:
            logger.warning("LegalHierarchyChunker: received empty node list.")
            return []

        doc_title = getattr(doc_config, "title", "Legal Document") if doc_config else "Legal Document"
        source_id = getattr(doc_config, "source_id_external", "DOC") if doc_config else "DOC"

        # Populate text/original_text from full_text if needed
        if full_text:
            for n in all_nodes:
                if not n.original_text and n.start_char_idx < len(full_text):
                    end = min(n.end_char_idx, len(full_text)) if n.end_char_idx > n.start_char_idx else len(full_text)
                    n.original_text = full_text[n.start_char_idx:end]
                if not n.text:
                    n.text = strip_sentinels(n.original_text)

        chunks: List[Document] = []

        # Identify substantive nodes to chunk
        nodes_to_chunk: List[LegalNode] = []
        for n in all_nodes:
            # Containers with child sections/articles/rules are not chunked directly
            if n.children and n.node_type.lower() in ("document", "part", "chapter"):
                continue
            # Large nodes with children: chunk children instead of whole node
            if n.children and len(n.text) > self.splitter._chunk_size:
                continue
            if not n.text.strip():
                continue
            nodes_to_chunk.append(n)

        for n_idx, node in enumerate(nodes_to_chunk):
            ancestors = find_ancestors(node, all_nodes)
            clean_node_text = strip_sentinels(node.text or node.original_text)
            if not clean_node_text:
                continue

            # Build breadcrumb path
            breadcrumb_parts = [f"Document: {doc_title}"]
            if ancestors.get("part"):
                breadcrumb_parts.append(f"Part: {ancestors['part']}")
            if ancestors.get("chapter"):
                breadcrumb_parts.append(f"Chapter: {ancestors['chapter']}")
            if ancestors.get("section"):
                breadcrumb_parts.append(f"Section: {ancestors['section']}")
            if ancestors.get("rule"):
                breadcrumb_parts.append(f"Rule: {ancestors['rule']}")
            if ancestors.get("article"):
                breadcrumb_parts.append(f"Article: {ancestors['article']}")

            curr_desc = f"{node.node_type.capitalize()}: {node.number or ''}"
            if node.title:
                curr_desc += f" ({node.title})"
            if node.node_type not in ("part", "chapter", "document"):
                breadcrumb_parts.append(curr_desc)

            breadcrumb = " | ".join(breadcrumb_parts)

            # Split into chunk texts
            text_splits = self._split_text_semantically(clean_node_text)
            total_chunks = len(text_splits)

            for c_idx, split_text in enumerate(text_splits):
                gen_context = ""
                if self.enable_contextual_retrieval:
                    parent_context = f"{breadcrumb}\n\nFull Provision Content:\n{clean_node_text}"
                    gen_context = self.create_gen_chunk_context(
                        whole_document_context=parent_context,
                        chunk_content=split_text,
                        sec_num=node.number or str(n_idx),
                        sec_title=node.title or "",
                        chapter=ancestors.get("chapter", "N/A"),
                        doc_title=doc_title,
                    )

                chunk_id = f"{source_id}_{node.node_type}_{node.number or n_idx}_c{c_idx}"
                chunk_doc = Document(
                    page_content=f"{gen_context}\n\n{split_text}" if gen_context else split_text,
                    metadata={
                        "chunk_id": chunk_id,
                        "chunk_index": c_idx,
                        "total_chunks_in_section": total_chunks,
                        "node_id": node.node_id,
                        "node_type": node.node_type,
                        "node_number": node.number or "",
                        "node_title": node.title or "",
                        "section_number": node.number if node.node_type in ("section", "article", "rule") else ancestors.get("section", ancestors.get("rule", ancestors.get("article", ""))),
                        "section_title": node.title if node.node_type in ("section", "article", "rule") else ancestors.get("section_title", ""),
                        "chapter": ancestors.get("chapter", "N/A"),
                        "part": ancestors.get("part", ""),
                        "section": node.number if node.node_type == "section" else ancestors.get("section", ""),
                        "article": node.number if node.node_type == "article" else ancestors.get("article", ""),
                        "rule": node.number if node.node_type == "rule" else ancestors.get("rule", ""),
                        "regulation": node.number if node.node_type == "regulation" else ancestors.get("regulation", ""),
                        "subsection": node.number if node.node_type == "subsection" else ancestors.get("subsection", ""),
                        "subrule": node.number if node.node_type == "subrule" else ancestors.get("subrule", ""),
                        "clause": node.number if node.node_type == "clause" else ancestors.get("clause", ""),
                        "subclause": node.number if node.node_type == "subclause" else ancestors.get("subclause", ""),
                        "start_page": node.start_page,
                        "end_page": node.end_page,
                        "parent_id": node.parent_id or "",
                        "references": node.references or [],
                        "structure_confidence": node.confidence,
                        "original_text": split_text,
                        "original_content": split_text,
                        "generated_context": gen_context,
                        "breadcrumb": breadcrumb,
                    }
                )
                chunks.append(chunk_doc)

        logger.info(
            f"LegalHierarchyChunker [{source_id}]: Created {len(chunks)} chunks from {len(nodes_to_chunk)} substantive nodes."
        )
        return chunks