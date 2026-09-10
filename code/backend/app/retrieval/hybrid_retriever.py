import asyncio
from typing import List, Optional, Union
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, MatchAny, MatchText
from loguru import logger

from app.schemas.pipeline import RetrievedChunk
from app.schemas.enums import Jurisdiction
from app.retrieval.vector_store import get_vector_store


LEGAL_AREA_ALIASES = {
    "abs": ["abs", "biodiversity", "ABS / Biodiversity", "abs / biodiversity"],
    "biodiversity": ["biodiversity", "abs", "ABS / Biodiversity", "abs / biodiversity"],
    "patent": ["patent", "patents"],
    "trademark": ["trademark", "trademarks"],
    "drug_regulation": ["drug_regulation", "drugs", "drug", "d&c"],
    "gi": ["gi", "geographical_indication"],
}


def _build_legal_area_filter(legal_area_filter: Optional[Union[str, List[str]]]) -> Optional[Filter]:
    """
    Constructs a native Qdrant Filter for the `legal_area` payload field.
    Matches against both 'metadata.legal_area' (LangChain format) and 'legal_area' (top-level),
    with automatic alias expansion (e.g. abs <-> biodiversity <-> ABS / Biodiversity).
    """
    if not legal_area_filter:
        return None
    
    if isinstance(legal_area_filter, str):
        raw_areas = [legal_area_filter.strip().lower()]
    elif isinstance(legal_area_filter, (list, tuple, set)):
        raw_areas = [str(a).strip().lower() for a in legal_area_filter if a]
    else:
        return None

    if not raw_areas:
        return None

    expanded_areas = set()
    for a in raw_areas:
        expanded_areas.add(a)
        expanded_areas.update(LEGAL_AREA_ALIASES.get(a, []))
        expanded_areas.add(a.upper())
        expanded_areas.add(a.capitalize())

    clean_areas = list(expanded_areas)

    conditions = [
        FieldCondition(key="metadata.legal_area", match=MatchAny(any=clean_areas)),
        FieldCondition(key="legal_area", match=MatchAny(any=clean_areas)),
    ]

    return Filter(should=conditions)


# Collections known to lack an applicable_product index; skipped automatically
# to avoid 400 Bad Request overhead, latency penalties, and terminal warning spam.
_UNINDEXED_PRODUCT_COLLECTIONS: set[str] = set()


def _build_applicable_product_filter(product_category: Optional[str]) -> Optional[Filter]:
    """
    Constructs a Qdrant Filter for the `applicable_product` payload field.
    Matches against both 'metadata.applicable_product' and 'applicable_product' using
    keyword MatchValue (never MatchText, which requires an incompatible text index).
    """
    if not product_category or product_category.strip().lower() in ("", "unclassified"):
        return None

    norm_cat = product_category.strip().lower().replace("-", "_").replace(" ", "_")

    return Filter(
        should=[
            FieldCondition(key="metadata.applicable_product", match=MatchValue(value="all")),
            FieldCondition(key="applicable_product", match=MatchValue(value="all")),
            FieldCondition(key="metadata.applicable_product", match=MatchValue(value=norm_cat)),
            FieldCondition(key="applicable_product", match=MatchValue(value=norm_cat)),
        ]
    )


def _merge_filters(
    legal_area_filter: Optional[Filter],
    applicable_product_filter: Optional[Filter],
) -> Optional[Filter]:
    """
    Combines legal_area and applicable_product filters with AND semantics (must).
    If only one filter is present, returns it directly (no unnecessary wrapping).
    """
    active = [f for f in [legal_area_filter, applicable_product_filter] if f is not None]
    if not active:
        return None
    if len(active) == 1:
        return active[0]
    # Both filters must match: legal_area AND (applicable_product == "all" OR category match)
    return Filter(must=active)


def _simple_keyword_overlap(query: str, text: str) -> float:
    """Calculates term overlap ratio between query tokens and document content."""
    tokens = [t.lower() for t in query.split() if len(t) > 2]
    if not tokens:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for t in tokens if t in text_lower)
    return round(min(1.0, matches / len(tokens)), 4)


async def retrieve(
    query: str, 
    legal_area_filter: Optional[Union[str, List[str]]] = None, 
    top_k: int = 10, 
    collection_name: str = "legal_acts",
    product_category: Optional[str] = None,
) -> List[RetrievedChunk]:
    """
    Retrieves chunks from Qdrant using native server-side payload filters.

    Applies two independent filters combined with AND logic:
      1. legal_area filter  — matches the legal domain of the sub-query.
      2. applicable_product filter — matches chunks whose `applicable_product`
         payload field is "all" OR contains the classified product category
         (e.g. "classical", "proprietary"). Skipped when product_category is
         absent, unclassified, or when the collection lacks a payload index.

    If the applicable_product index is missing on the collection, the retrieval
    is automatically retried without that filter (graceful degradation) and remembered
    to prevent subsequent 400 Bad Request calls.
    """
    vs = get_vector_store(collection_name)
    if vs is None:
        return []

    legal_filter = _build_legal_area_filter(legal_area_filter)
    if collection_name in _UNINDEXED_PRODUCT_COLLECTIONS:
        product_filter = None
    else:
        product_filter = _build_applicable_product_filter(product_category)
    combined_filter = _merge_filters(legal_filter, product_filter)
    
    # Execute native filtered search directly on Qdrant with cascading fallbacks
    try:
        results = await asyncio.to_thread(
            vs.similarity_search_with_score,
            query,
            k=top_k,
            filter=combined_filter
        )
    except Exception as e:
        err_msg = str(e)
        if "applicable_product" in err_msg:
            _UNINDEXED_PRODUCT_COLLECTIONS.add(collection_name)
            logger.info(
                f"Collection '{collection_name}' has no index for 'applicable_product'. "
                f"Bypassing filter for future calls (reranker scores product category in-memory)."
            )
        else:
            logger.warning(
                f"Filtered vector search failed in '{collection_name}' ({e}). "
                f"Retrying with legal_area filter only..."
            )
        try:
            results = await asyncio.to_thread(
                vs.similarity_search_with_score,
                query,
                k=top_k,
                filter=legal_filter
            )
        except Exception as e2:
            logger.warning(
                f"Legal area filter also failed in '{collection_name}' ({e2}). "
                f"Retrying unfiltered search..."
            )
            try:
                results = await asyncio.to_thread(
                    vs.similarity_search_with_score,
                    query,
                    k=top_k,
                    filter=None
                )
            except Exception as e3:
                logger.error(f"Unfiltered vector search also failed: {e3}. Returning empty candidates.")
                return []

    chunks = []
    for doc, raw_score in results:
        meta = doc.metadata or {}
        text_content = meta.get("original_content", doc.page_content)
        v_score = round(max(0.0, min(1.0, float(raw_score))), 4)
        kw_score = _simple_keyword_overlap(query, text_content)

        chunks.append(RetrievedChunk(
            chunk_id=meta.get("chunk_id", "unknown"),
            text=text_content,
            provision=meta.get("provision_ref") or meta.get("section") or meta.get("section_number") or "N/A",
            title=meta.get("section_title") or meta.get("source_title") or meta.get("title") or "N/A",
            chapter=meta.get("chapter", "N/A"),
            pages=f"{meta.get('start_page', '?')} to {meta.get('end_page', '?')}",
            source_authority=meta.get("source_title") or meta.get("title") or meta.get("document_id") or meta.get("source_id_external") or "Unknown Document",
            authority_level=meta.get("authority_level"),
            document_type=meta.get("document_type"),
            jurisdiction=Jurisdiction.INDIA if meta.get("jurisdiction", "india").lower() == "india" else Jurisdiction.INTERNATIONAL,
            legal_area=meta.get("legal_area"),
            vector_score=v_score,
            keyword_score=kw_score
        ))

    return chunks
