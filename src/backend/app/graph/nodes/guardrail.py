from typing import Dict, Any
from app.graph.state import RAGState, CLEAR_SENTINEL
from app.guardrails import guardrail_checker

def guardrail_node(state: RAGState) -> Dict[str, Any]:
    intent = state.get("understanding").intent if state.get("understanding") else "other"
    if intent in ("general_info", "other"):
        return {"status": "answered"}
    
    # Read from top_evidences (written by generate_node) instead of re-merging
    # evidence_packs, which may contain pre-rerank duplicates.
    top_evidences = state.get("top_evidences") or []
    
    jurisdiction = state.get("jurisdiction")
    
    result = guardrail_checker.check(
        draft_answer=state["final_answer"], 
        top_evidences=top_evidences, 
        jurisdiction=jurisdiction
    )
    
    if not result.passed:
        return {
            "status": "abstained",
            "final_answer": f"I don't have sufficient grounded evidence to answer confidently. {result.reason}",
            "guardrail_result": result
        }
    
    return {
        "status": "answered",
        "guardrail_result": result
    }

