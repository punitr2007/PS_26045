from typing import Dict, Any
from app.graph.state import RAGState, CLEAR_SENTINEL
from app.retrieval import reranker
from app.generation import evidence_pack, llm_answerer
from app.services.streaming_context import streaming_queue_var, emit_stream_event


async def generate_node(state: RAGState) -> Dict[str, Any]:
    ev_packs = state.get("evidence_packs", [])
    if ev_packs == CLEAR_SENTINEL:
        ev_packs = []
        
    await emit_stream_event({"type": "status", "message": "Reranking statutory provisions & ABS guidelines..."})

    ranked_packs = await reranker.rerank_async(ev_packs, state)
    context, top_evidences = evidence_pack.merge(ranked_packs, top_n_total=8)
    
    queue = streaming_queue_var.get()

    # Emit retrieved sources immediately so the frontend citations render before generation finishes
    if queue is not None and top_evidences:
        sources = evidence_pack.format_sources(top_evidences, max_sources=8)
        await emit_stream_event({"type": "sources", "sources": sources})

    await emit_stream_event({"type": "status", "message": "Synthesizing legal opinion..."})

    # If this is a retry attempt from the guardrail loop, signal the client to clear previously streamed tokens
    if queue is not None and state.get("retry_count", 0) > 0:
        await emit_stream_event({"type": "reset", "message": "Refining statutory opinion..."})

    chat_history = state.get("chat_history")

    # Stream tokens if an SSE streaming queue is active
    if queue is not None:
        draft_answer = ""
        async for token in llm_answerer.generate_stream(
            context,
            state.get("understanding"),
            state["query"],
            chat_history=chat_history,
        ):
            draft_answer += token
            await emit_stream_event({"type": "token", "token": token})
    else:
        draft_answer = await llm_answerer.generate(
            context,
            state.get("understanding"),
            state["query"],
            chat_history=chat_history,
        )
    
    # If fallback assumptions were made, append a clear statutory caveat
    assumptions = state.get("unresolved_assumptions", [])
    if assumptions and draft_answer:
        caveat_block = "\n\n> **Regulatory Assumptions Applied (Max Clarification Reached):**\n> - " + "\n> - ".join(assumptions)
        draft_answer += caveat_block
        if queue is not None:
            await emit_stream_event({"type": "token", "token": caveat_block})

    return {
        "final_answer": draft_answer,
        # Store reranked results in dedicated state fields to avoid the LangGraph
        # add_evidence reducer concatenating pre-rerank + post-rerank packs (double-append bug).
        # guardrail_node reads from top_evidences directly.
        "top_evidences": top_evidences,
        "context_str": context,
    }
