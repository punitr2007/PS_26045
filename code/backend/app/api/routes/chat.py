from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from app.schemas.schemas import ChatRequest, ChatResponse, ConversationHistoryResponse
from app.services.memory_service import memory_service
from app.services.chatbot_service import chatbot_service

router = APIRouter()


def _resolve_session_and_jurisdiction(request: ChatRequest):
    session_id = request.session_id or memory_service.create_session()
    jurisdiction = "national"
    if request.filters:
        if isinstance(request.filters, dict):
            jurisdiction = request.filters.get("jurisdiction", "national")
        elif hasattr(request.filters, "jurisdiction") and request.filters.jurisdiction:
            jurisdiction = request.filters.jurisdiction
    return session_id, jurisdiction


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Explicit SSE streaming endpoint delivering real-time status, citations, and AI tokens."""
    session_id, jurisdiction = _resolve_session_and_jurisdiction(request)
    return StreamingResponse(
        chatbot_service.process_chat_stream(
            session_id=session_id,
            query=request.message,
            top_k=request.top_k,
            known_facts=request.known_facts,
            jurisdiction=jurisdiction,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, raw_request: Request):
    """Primary chat endpoint. Streams SSE when requested, or returns full JSON payload."""
    session_id, jurisdiction = _resolve_session_and_jurisdiction(request)
    accept = raw_request.headers.get("accept", "")

    if request.stream or "text/event-stream" in accept:
        return StreamingResponse(
            chatbot_service.process_chat_stream(
                session_id=session_id,
                query=request.message,
                top_k=request.top_k,
                known_facts=request.known_facts,
                jurisdiction=jurisdiction,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    try:
        result = await chatbot_service.process_chat_async(
            session_id=session_id,
            query=request.message,
            top_k=request.top_k,
            known_facts=request.known_facts,
            jurisdiction=jurisdiction,
        )
        return ChatResponse(**result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/history", response_model=ConversationHistoryResponse)
async def get_history(session_id: str):
    history = memory_service.get_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found or empty")
    
    return ConversationHistoryResponse(
        session_id=session_id,
        turns=history
    )


@router.delete("/{session_id}")
async def clear_session(session_id: str):
    success = memory_service.clear(session_id)
    if success:
        return {"message": f"Session {session_id} cleared"}
    raise HTTPException(status_code=404, detail="Session not found")
