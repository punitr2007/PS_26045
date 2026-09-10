from typing import Dict, Any
from app.graph.state import RAGState
from app.core import product_classifier

def classify_node(state: RAGState) -> Dict[str, Any]:
    classification = product_classifier.classify(
        understanding=state["understanding"],
        jurisdiction=state.get("jurisdiction"),
        known_facts=state.get("known_facts", {}),
        existing_classification=state.get("classification")
    )
    return {
        "classification": classification,
        "missing_facts": classification.missing_facts
    }
