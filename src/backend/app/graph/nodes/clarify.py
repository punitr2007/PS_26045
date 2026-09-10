from typing import Dict, Any
from app.graph.state import RAGState
from app.core.clarification_manager import generate_clarification_questions
from app.services.streaming_context import emit_stream_event


async def clarify_node(state: RAGState) -> Dict[str, Any]:
    """
    Generates targeted, constrained clarifying questions for missing regulatory/IP facts.
    Sets awaiting_clarification: True and status: needs_clarification to halt the graph at END.
    """
    missing = state.get("missing_facts", [])
    known = state.get("known_facts", {})
    
    questions = generate_clarification_questions(missing_fields=missing, known_facts=known)
    
    # Formulate a helpful explanation text for the chat response
    intro_lines = [
        "To provide precise legal and regulatory guidance under Indian & International IP frameworks, I need a few specific details regarding your formulation:"
    ]
    for idx, q in enumerate(questions, 1):
        opts = f" (Options: {', '.join(q.options)})" if q.options else ""
        intro_lines.append(f"{idx}. {q.question}{opts}")
        
    intro_lines.append("\nPlease reply with these details so I can determine statutory patentability, TKDL prior art, or regulatory compliance.")
    clarification_message = "\n".join(intro_lines)
    questions_dump = [q.model_dump() for q in questions]

    await emit_stream_event({
        "type": "clarification",
        "questions": questions_dump,
        "answer": clarification_message,
    })

    return {
        "awaiting_clarification": True,
        "status": "needs_clarification",
        "pending_questions": questions_dump,
        "final_answer": clarification_message
    }
