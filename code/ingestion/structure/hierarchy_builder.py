"""
structure/hierarchy_builder.py
================================
Converts a flat list of validated LegalCandidates into a LegalNode hierarchy tree.

This is a pure function module — it has NO side effects and does not call any LLM.
The tree is inferred from:
  1. Numbering prefix matching  (e.g. "3(a)" → parent is section "3")
  2. Node type rank ordering    (clause < subsection < section < chapter < part)
  3. TOC page-based chapter lookup (when TocStructuralIndex is available)

Design principles:
  - Never hardcode "section.parent = chapter" as the only valid hierarchy.
  - Works for Acts, Rules, Regulations, Constitutions, Judgments.
  - Unknown node types are placed below the nearest lower-ranked ancestor.
"""

import re
import uuid
from typing import List, Optional, Dict, Tuple

from loguru import logger

from .models import LegalCandidate, LegalNode


# ---------------------------------------------------------------------------
# Node type rank table — lower rank = higher in the document tree
# ---------------------------------------------------------------------------
NODE_RANK: Dict[str, int] = {
    "document":     0,
    "part":         1,
    "chapter":      2,
    "section":      3,
    "article":      3,
    "rule":         3,
    "regulation":   3,
    "heading":      3,
    "subsection":   4,
    "subrule":      4,
    "subregulation": 4,
    "clause":       5,
    "subclause":    6,
    "paragraph":    7,
    "subparagraph": 8,
}

_DEFAULT_RANK = 5  # fallback for unknown types — treat as clause-level


def _rank(node_type: str) -> int:
    return NODE_RANK.get(node_type.lower(), _DEFAULT_RANK)


# ---------------------------------------------------------------------------
# Numbering prefix matcher
# ---------------------------------------------------------------------------

def _extract_numbering_prefix(number: Optional[str]) -> Optional[str]:
    """
    Given a numbering string, return the parent numbering prefix if detectable.

    Examples:
        "3(a)"  → "3"
        "3(1)"  → "3"
        "3A(b)" → "3A"
        "(a)"   → None  (top-level clause; parent resolved by rank)
        "3"     → None
        "14.1"  → "14"
    """
    if not number:
        return None

    # Pattern: 3(a), 3(1), 3A(b)
    m = re.match(r'^(\d+[A-Z]?)\(', number)
    if m:
        return m.group(1)

    # Pattern: 14.1, 14.1.2
    m = re.match(r'^(\d+)\.\d', number)
    if m:
        return m.group(1)

    return None


# ---------------------------------------------------------------------------
# Node ID generator
# ---------------------------------------------------------------------------

def _make_node_id(source_id: str, node_type: str, number: Optional[str], idx: int) -> str:
    base = f"{source_id}_{node_type}_{number or idx}"
    # Sanitize for use as a stable identifier
    return re.sub(r'[^\w\-]', '_', base)


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

class HierarchyBuilder:
    """
    Converts a flat validated ``List[LegalCandidate]`` into a list of root-level
    ``LegalNode`` objects with fully populated ``parent_id`` and ``children``.

    Usage::

        builder = HierarchyBuilder(source_id="IN-PAT-001")
        roots = builder.build(candidates, page_resolver=extractor.get_page_range)
    """

    def __init__(self, source_id: str = "UNKNOWN"):
        self.source_id = source_id

    # ------------------------------------------------------------------
    def build(
        self,
        candidates: List[LegalCandidate],
        page_resolver=None,          # callable(start_idx, end_idx) -> (start_page, end_page)
        toc_index=None,              # Optional[TocStructuralIndex]
    ) -> List[LegalNode]:
        """
        Build the hierarchy.

        Args:
            candidates:    Flat list of validated ``LegalCandidate`` objects, ordered by
                           ``start_char_idx`` (ascending).
            page_resolver: Optional callable ``(start_char, end_char) -> (start_page, end_page)``.
                           When provided, page provenance is populated on every node.
            toc_index:     Optional ``TocStructuralIndex``.  Used to authoratively assign
                           chapter/part labels to chapter-rank nodes.

        Returns:
            List of root-level ``LegalNode`` objects (tree roots, typically Chapter or Part nodes).
            The full tree is accessible via ``.children`` recursion.
        """
        if not candidates:
            logger.warning("HierarchyBuilder: received empty candidate list.")
            return []

        # Sort by position in document (should already be sorted, but be defensive)
        ordered = sorted(candidates, key=lambda c: c.start_char_idx)

        nodes: List[LegalNode] = []
        # Stack tracks open ancestor nodes (most recent ancestor at top)
        # Each stack entry is a LegalNode that is still "open" (may gain children)
        stack: List[LegalNode] = []

        # Index for stable ID generation when number is absent
        number_index: Dict[str, int] = {}

        for candidate in ordered:
            idx = number_index.get(candidate.node_type, 0)
            number_index[candidate.node_type] = idx + 1

            node_id = _make_node_id(self.source_id, candidate.node_type, candidate.number, idx)

            # Resolve pages
            start_page: Optional[int] = None
            end_page: Optional[int] = None
            if page_resolver:
                try:
                    start_page, end_page = page_resolver(candidate.start_char_idx, candidate.end_char_idx)
                except Exception as e:
                    logger.debug(f"HierarchyBuilder: page resolver failed for {node_id}: {e}")

            # Authoritative chapter label from TOC index (for chapter-rank nodes)
            toc_chapter: Optional[str] = None
            if toc_index and toc_index.has_toc and start_page is not None:
                if _rank(candidate.node_type) <= _rank("chapter"):
                    toc_chapter = toc_index.get_chapter_for_page(start_page)

            node = LegalNode(
                node_id=node_id,
                node_type=candidate.node_type,
                number=candidate.number,
                title=toc_chapter or candidate.title,
                text="",               # text is populated from raw_text by the caller
                original_text="",      # populated by caller after slicing full_text
                start_char_idx=candidate.start_char_idx,
                end_char_idx=candidate.end_char_idx,
                start_page=start_page,
                end_page=end_page,
                confidence=candidate.confidence,
                parent_id=None,
                children=[],
                references=[],
            )

            parent = self._find_parent(node, stack, candidate)
            if parent is not None:
                node.parent_id = parent.node_id
                parent.children.append(node)
            else:
                # This is a root node (chapter, part, or orphan section)
                roots = [n for n in nodes if n.parent_id is None]
                nodes.append(node)

            # Push onto stack
            # Pop everything with rank >= current node's rank first
            self._trim_stack(stack, node)
            stack.append(node)

        root_nodes = [n for n in nodes if n.parent_id is None]
        logger.info(
            f"HierarchyBuilder [{self.source_id}]: built {len(nodes)} nodes, "
            f"{len(root_nodes)} roots from {len(candidates)} candidates."
        )
        self._log_tree(root_nodes, depth=0)
        return root_nodes

    # ------------------------------------------------------------------
    def _find_parent(
        self,
        node: LegalNode,
        stack: List[LegalNode],
        candidate: LegalCandidate,
    ) -> Optional[LegalNode]:
        """
        Find the closest open ancestor for ``node``.

        Priority order:
          1. Numbering prefix match (e.g. "3(a)" → parent number "3")
          2. Stack-based rank: nearest ancestor with lower rank
          3. parent_hint from candidate (e.g. chapter heading text)
        """
        node_rank = _rank(node.node_type)
        prefix = _extract_numbering_prefix(node.number)

        # 1. Exact numbering prefix match on the stack
        if prefix:
            for ancestor in reversed(stack):
                if ancestor.number == prefix:
                    return ancestor

        # 2. Rank-based: nearest open ancestor with strictly lower rank
        for ancestor in reversed(stack):
            if _rank(ancestor.node_type) < node_rank:
                return ancestor

        # 3. Parent hint match (chapter heading text)
        if candidate.parent_hint:
            hint = candidate.parent_hint.upper()
            for ancestor in reversed(stack):
                if ancestor.title and hint in ancestor.title.upper():
                    return ancestor
                if ancestor.number and hint in ancestor.number.upper():
                    return ancestor

        return None

    def _trim_stack(self, stack: List[LegalNode], node: LegalNode) -> None:
        """
        Remove from the stack all nodes whose rank is >= the new node's rank.
        This ensures siblings don't become parents of each other.
        """
        node_rank = _rank(node.node_type)
        while stack and _rank(stack[-1].node_type) >= node_rank:
            stack.pop()

    def _log_tree(self, nodes: List[LegalNode], depth: int) -> None:
        """Debug-logs the constructed hierarchy tree (max depth 3)."""
        if depth > 2:
            return
        indent = "  " * depth
        for node in nodes:
            logger.debug(
                f"{indent}[{node.node_type.upper()}] "
                f"{node.number or ''} {node.title or ''} "
                f"(conf={node.confidence:.2f}, pages {node.start_page}-{node.end_page})"
            )
            self._log_tree(node.children, depth + 1)


# ---------------------------------------------------------------------------
# Utility: flatten tree back to list (useful for chunking)
# ---------------------------------------------------------------------------

def flatten_tree(roots: List[LegalNode]) -> List[LegalNode]:
    """
    Yields all nodes in pre-order (parent before children).
    Useful for chunking, where you iterate over all nodes in document order.
    """
    result: List[LegalNode] = []

    def _walk(node: LegalNode) -> None:
        result.append(node)
        for child in node.children:
            _walk(child)

    for root in roots:
        _walk(root)
    return result


def find_ancestors(node: LegalNode, all_nodes: List[LegalNode]) -> Dict[str, str]:
    """
    Walks up the tree and returns a dict of {node_type: number_or_title} for all ancestors.
    Used by MetadataEnricher to populate part/chapter/section/clause fields.

    Example result:
        {"part": "I", "chapter": "II", "section": "3", "clause": "(d)"}
    """
    index: Dict[str, LegalNode] = {n.node_id: n for n in flatten_tree(all_nodes)}
    result: Dict[str, str] = {}
    current = node
    while current.parent_id and current.parent_id in index:
        ancestor = index[current.parent_id]
        label = ancestor.number or ancestor.title or ""
        if ancestor.node_type and label:
            result[ancestor.node_type] = label
        current = ancestor
    return result
