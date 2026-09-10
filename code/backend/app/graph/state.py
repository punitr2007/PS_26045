from typing import TypedDict, List, Dict, Any, Annotated, Optional
import operator
from app.schemas.pipeline import QueryUnderstanding, QueryDecomposition, EvidencePack, ProductClassification, RankedEvidence
from app.schemas.enums import Jurisdiction

CLEAR_SENTINEL = "__CLEAR_SENTINEL__"

def add_evidence(left: List[EvidencePack], right: List[EvidencePack] | str) -> List[EvidencePack]:
    if right == CLEAR_SENTINEL:
        return []
    if left is None:
        left = []
    if right is None:
        return left
    return left + right

class RAGState(TypedDict):
    query: str
    session_id: str
    understanding: QueryUnderstanding
    jurisdiction: Jurisdiction
    classification: ProductClassification
    decomposition: QueryDecomposition
    chat_history: Optional[List[Dict[str, str]]]
    # Custom reducer allows clearing the list on retry by passing CLEAR_SENTINEL
    evidence_packs: Annotated[List[EvidencePack], add_evidence]
    final_answer: str
    status: str
    retry_count: int
    
    # Post-rerank outputs — written by generate_node instead of mutating evidence_packs
    # to avoid the LangGraph add_evidence reducer double-appending pre+post rerank packs.
    top_evidences: Optional[List[RankedEvidence]]
    context_str: Optional[str]
    guardrail_result: Optional[Any]

    # Dual-ingress & Clarification Slot-Filling fields
    known_facts: Dict[str, Any]
    clarification_round: int
    max_clarification_rounds: int
    missing_facts: List[str]
    pending_questions: List[Dict[str, Any]]
    awaiting_clarification: bool
    unresolved_assumptions: List[str]

