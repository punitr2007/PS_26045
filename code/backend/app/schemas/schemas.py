from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., description="User question or query about Ayurvedic legal regulations")
    session_id: Optional[str] = Field(default=None, description="Optional conversation session ID for multi-turn history")
    top_k: int = Field(default=4, description="Number of top retrieved sources to return")
    known_facts: Optional[Dict[str, Any]] = Field(default=None, description="Optional pre-seeded product facts (category, route, etc.)")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional search filters e.g. jurisdiction")
    stream: Optional[bool] = Field(default=False, description="Whether to stream response tokens via SSE")

class SourceCitation(BaseModel):
    id: str
    provision: str
    title: str
    chapter: Optional[str] = None
    pages: Optional[str] = None
    source_url: Optional[str] = None
    breadcrumb: Optional[str] = None
    statute_id: Optional[str] = None
    clause_id: Optional[str] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    source_authority: Optional[str] = None
    document_type: Optional[str] = None
    legal_area: Optional[str] = None
    text: Optional[str] = None
    excerpts: Optional[List[str]] = None
    chunk_ids: Optional[List[str]] = None
    chunk_count: Optional[int] = None

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[Dict[str, Any]] = Field(default=[])
    turn_index: int
    timestamp: str
    status: str
    questions: Optional[List[Dict[str, Any]]] = None

class ConversationHistoryResponse(BaseModel):
    session_id: str
    turns: List[Dict[str, Any]]

class AuditRequest(BaseModel):
    abstract: str
    classification: str
    synergy_description: Optional[str] = ""
    ingredients: Optional[str] = ""

class AuditResponse(BaseModel):
    verdict: str
    tkdl_band: str
    s3e_band: str
    nba_band: str
    analysis: str
    sources: Optional[List[SourceCitation]] = None

