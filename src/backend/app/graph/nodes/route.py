from typing import Dict, Any
from app.graph.state import RAGState
from app.schemas.enums import Jurisdiction
from app.core import jurisdiction_router

def route_node(state: RAGState) -> Dict[str, Any]:
    known = state.get("known_facts", {})
    assumptions = list(state.get("unresolved_assumptions", []))
    
    if "jurisdiction" in known:
        jur_val = str(known["jurisdiction"]).lower().strip()
        jurisdiction = Jurisdiction.INTERNATIONAL if "international" in jur_val or "us" in jur_val or "pct" in jur_val else Jurisdiction.INDIA
    else:
        jurisdiction = jurisdiction_router.route(state["understanding"], state["query"])
        if state.get("clarification_round", 0) >= state.get("max_clarification_rounds", 2) and "jurisdiction" in state.get("missing_facts", []):
            assumptions.append("Assumed Indian jurisdiction")
            jurisdiction = Jurisdiction.INDIA
            
    return {
        "jurisdiction": jurisdiction,
        "unresolved_assumptions": assumptions,
        "awaiting_clarification": False,
        "pending_questions": []
    }
