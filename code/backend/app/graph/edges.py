from langgraph.constants import Send, END
from app.graph.state import RAGState
from app.schemas.enums import LegalArea

def distribute_queries(state: RAGState):
    """
    Dynamic Fan-out edge logic.
    Reads the SubQueries from the state decomposition and yields Send objects
    to the appropriate retrieval nodes.

    Routing rules:
    - PATENT, GI, TRADEMARK → retrieve_patent  (legal_acts_patent collection)
    - TK_PRIOR_ART → retrieve_patent  (Section 3(p) of the Patents Act IS the primary
      traditional-knowledge provision; it lives in legal_acts_patent, NOT in the ABS
      biodiversity collection)
    - ABS → retrieve_abs  (Biological Diversity Act, NBA provisions)
    - DRUG_REGULATION → retrieve_regulation
    """
    decomposition = state.get("decomposition")
    if not decomposition or not hasattr(decomposition, "sub_queries"):
        return []
    sub_queries = decomposition.sub_queries or []
    
    # We yield a Send object for each subquery
    sends = []
    for sq in sub_queries:
        if sq.legal_area in (LegalArea.PATENT, LegalArea.GI, LegalArea.TRADEMARK, LegalArea.TK_PRIOR_ART):
            sends.append(Send("retrieve_patent", sq))
        elif sq.legal_area == LegalArea.ABS:
            sends.append(Send("retrieve_abs", sq))
        elif sq.legal_area == LegalArea.DRUG_REGULATION:
            sends.append(Send("retrieve_regulation", sq))
        else:
            sends.append(Send("retrieve_regulation", sq)) # Default fallback
            
    return sends


def guardrail_condition(state: RAGState):
    """
    Conditional edge from guardrail node.
    If the status is abstained (or guardrail_result is failed) and retry_count is < 2, loop back to decompose.
    Otherwise, END.
    """
    status = state.get("status")
    gr = state.get("guardrail_result")
    is_abstained = (status == "abstained") or (gr is not None and not getattr(gr, "passed", True))
    if is_abstained:
        if state.get("retry_count", 0) < 2:
            return "retry_loop"
    return END

def understand_condition(state: RAGState):
    """
    Conditional edge from understand node.
    If the intent is 'general_info' or 'other', we skip the heavy RAG pipeline
    and jump straight to generation to answer quickly.
    """
    understanding = state.get("understanding")
    intent = getattr(understanding, "intent", "other") if understanding else "other"
    if intent == "general_info":
        return "bypass"
    return "continue"


LOAD_BEARING_FIELDS = {"category", "jurisdiction", "route_of_administration", "intended_use"}

def clarify_condition(state: RAGState) -> str:
    """
    Conditional edge from classify node.
    1. Intent check: If general_info or other, always bypass clarification.
    2. Load-bearing check: If load-bearing fields are missing (calculated precisely by product_classifier
       based on raw_product_description presence) and clarification_round < max_rounds, route to clarify_node.
    3. Else: proceed to route/decompose.
    """
    understanding = state.get("understanding")
    intent = getattr(understanding, "intent", "legal_query") if understanding else "legal_query"
    if intent in ("general_info", "other"):
        return "continue"

    classification = state.get("classification")
    class_missing = getattr(classification, "missing_facts", []) if classification else []
    missing = set(state.get("missing_facts") or class_missing or [])
    load_bearing = missing.intersection(LOAD_BEARING_FIELDS)
    round_num = state.get("clarification_round", 0)
    max_rounds = state.get("max_clarification_rounds", 2)
    
    if load_bearing and round_num < max_rounds:
        return "clarify"
        
    return "continue"

