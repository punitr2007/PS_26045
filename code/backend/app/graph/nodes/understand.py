from typing import Dict, Any
from app.graph.state import RAGState, CLEAR_SENTINEL
from app.core import query_understanding
from app.core.clarification_manager import detect_answer_relevance
from app.services.streaming_context import emit_stream_event
from loguru import logger

async def understand_node(state: RAGState) -> Dict[str, Any]:
    await emit_stream_event({"type": "status", "message": "Analyzing Ayurvedic legal frameworks & ABS provisions..."})
    query = state.get("query", "")
    is_resuming_clarification = state.get("awaiting_clarification", False)
    current_known_facts = dict(state.get("known_facts") or {})
    
    chat_history = state.get("chat_history", [])
    
    if is_resuming_clarification:
        # Step 1: Detect whether user reply answers pending questions or drifts to a new topic
        pending = state.get("pending_questions", [])
        relevance = detect_answer_relevance(user_reply=query, pending_questions=pending)
        
        if relevance.is_new_topic:
            logger.info(f"Clarification drift detected for session '{state.get('session_id')}': resetting clarification session.")
            understanding = await query_understanding.process(query, chat_history=chat_history)
            return {
                "understanding": understanding,
                "retry_count": 0,
                "clarification_round": 0,
                "evidence_packs": CLEAR_SENTINEL,
                "awaiting_clarification": False,
                "pending_questions": [],
                "unresolved_assumptions": [],
                "status": "in_progress",
                "final_answer": "",
                "known_facts": current_known_facts,
                "chat_history": chat_history,
            }
        else:
            # Slot answered: merge newly extracted facts
            current_known_facts.update(relevance.extracted_facts)
            return {
                "known_facts": current_known_facts,
                "clarification_round": state.get("clarification_round", 0) + 1,
                "awaiting_clarification": False,
                "status": "in_progress",
                "chat_history": chat_history,
            }
    else:
        # Fresh Turn
        understanding = await query_understanding.process(query, chat_history=chat_history)
        if understanding:
            if understanding.mentions_jurisdiction and "jurisdiction" not in current_known_facts:
                current_known_facts["jurisdiction"] = understanding.mentions_jurisdiction
            if understanding.raw_product_description:
                current_known_facts["raw_product_description"] = understanding.raw_product_description
            elif current_known_facts.get("raw_product_description"):
                # Backfill from accumulated session known facts
                understanding.raw_product_description = current_known_facts["raw_product_description"]

        return {
            "understanding": understanding,
            "retry_count": 0,
            "clarification_round": state.get("clarification_round", 0),
            "evidence_packs": CLEAR_SENTINEL,
            "awaiting_clarification": False,
            "pending_questions": [],
            "unresolved_assumptions": [],
            "status": "in_progress",
            "final_answer": "",
            "known_facts": current_known_facts,
            "chat_history": chat_history,
        }
