from typing import Dict, Any
from app.graph.state import RAGState, CLEAR_SENTINEL
from app.core import query_decomposer
from app.schemas.enums import LegalArea
from app.schemas.pipeline import SubQuery

def decompose_node(state: RAGState) -> Dict[str, Any]:
    current_retry = state.get("retry_count", 0)
    
    decomposition = query_decomposer.decompose(
        state["understanding"], 
        state["classification"], 
        state["jurisdiction"],
        state["query"]
    )
    
    if current_retry > 0:
        # On retry, expand to all legal areas if needed, but preserve the specialized
        # _reframe_for_area statutory templates and inject any unverified citations
        # that caused the guardrail failure.
        gr = state.get("guardrail_result")
        unverified = getattr(gr, "unverified_citations", []) if gr else []
        citation_hint = f" {', '.join(unverified)}" if unverified else ""

        all_areas = list(LegalArea)
        retry_subqueries = []
        for area in all_areas:
            base_query = f"{state['query']}{citation_hint}"
            reframed = query_decomposer._reframe_for_area(base_query, area)
            retry_subqueries.append(SubQuery(
                legal_area=area,
                query_text=reframed,
                jurisdiction=state["jurisdiction"]
            ))
        decomposition.sub_queries = retry_subqueries

    return {
        "decomposition": decomposition,
        "retry_count": current_retry + 1,
        "evidence_packs": CLEAR_SENTINEL
    }
