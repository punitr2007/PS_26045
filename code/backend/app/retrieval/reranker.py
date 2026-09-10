from typing import List, Dict, Any
from app.schemas.pipeline import EvidencePack, RankedEvidence
from langchain_core.documents import Document
from app.retrieval.reranker_engine import LegalReranker
from loguru import logger

reranker_instance = LegalReranker(enable_mmr_dedup=True)

def rerank(evidence_packs: List[EvidencePack], state: Dict[str, Any]) -> List[EvidencePack]:
    """
    Reranks the retrieved evidences in each pack using the LegalReranker engine.
    Returns a new list of EvidencePacks with reranked evidences.
    """
    # 1. Build query_context from state
    classification = state.get("classification")
    jurisdiction = state.get("jurisdiction")
    
    query_context = {
        "jurisdiction": jurisdiction.value if jurisdiction else None,
        "product_category": classification.category.value if classification else None,
    }
    
    query = state.get("query", "")
    reranked_packs = []
    
    for pack in evidence_packs:
        # Update context with the specific sub_query's legal area
        query_context["legal_area"] = [pack.sub_query.legal_area.value]
        
        # 2. Convert Evidence back to LangChain Documents for the reranker
        documents = []
        for ev in pack.evidences:
            doc = Document(
                page_content=ev.chunk.text,
                metadata={
                    "chunk_id": ev.chunk.chunk_id,
                    "section": ev.chunk.provision,
                    "article": ev.chunk.provision,
                    "source_title": ev.chunk.title,
                    "document_id": ev.chunk.title,
                    "jurisdiction": ev.chunk.jurisdiction.value,
                    "authority_level": ev.chunk.authority_level if ev.chunk.authority_level is not None else ev.chunk.source_authority,
                    "document_type": ev.chunk.document_type,
                    # Use the chunk's actual legal_area from Qdrant payload.
                    # Falling back to the sub-query area only when the chunk has no stored area.
                    # Stamping all chunks with pack.sub_query.legal_area.value makes every chunk
                    # score 1.0 on applicability — defeating the signal entirely.
                    "legal_area": ev.chunk.legal_area or pack.sub_query.legal_area.value,
                    "status": "active" # Assume active if not present
                }
            )
            # v_score is raw_score
            documents.append((doc, ev.chunk.vector_score or 0.5))
            
        # 3. Call LegalReranker with effective query combining user query + sub-query terms
        sq_text = getattr(pack.sub_query, "query_text", "")
        effective_query = f"{query} - {sq_text}" if sq_text else query

        try:
            reranked_tuples = reranker_instance.rerank(
                query=effective_query,
                results=documents,
                query_context=query_context
            )
        except Exception as e:
            logger.error(f"LegalReranker failed: {e}. Falling back to original order.")
            # Fallback if something goes wrong
            reranked_tuples = [(doc, float(score), {}) for doc, score in documents]
        
        # 4. Map back to RankedEvidence
        new_evidences = []
        # Create a fast lookup for chunk mapping
        chunk_map = {ev.chunk.chunk_id: ev.chunk for ev in pack.evidences}
        
        for doc, composite_score, signals in reranked_tuples:
            chunk_id = doc.metadata.get("chunk_id")
            chunk = chunk_map.get(chunk_id)
            if chunk:
                new_ev = RankedEvidence(
                    chunk=chunk,
                    relevance_score=signals.get("relevance", 0.0),
                    authority_score=signals.get("authority", 0.0),
                    jurisdiction_score=signals.get("jurisdiction", 0.0),
                    freshness_score=signals.get("freshness", 0.0),
                    applicability_score=signals.get("applicability", 0.0),
                    final_score=composite_score
                )
                new_evidences.append(new_ev)
                
        reranked_packs.append(EvidencePack(
            sub_query=pack.sub_query,
            evidences=new_evidences
        ))
        
    return reranked_packs


async def rerank_async(evidence_packs: List[EvidencePack], state: Dict[str, Any]) -> List[EvidencePack]:
    """
    Asynchronously reranks retrieved evidences with non-blocking neural cross-encoder inference if enabled.
    """
    classification = state.get("classification")
    jurisdiction = state.get("jurisdiction")
    
    query_context = {
        "jurisdiction": jurisdiction.value if jurisdiction else None,
        "product_category": classification.category.value if classification else None,
    }
    
    query = state.get("query", "")
    reranked_packs = []
    
    for pack in evidence_packs:
        query_context["legal_area"] = [pack.sub_query.legal_area.value]
        
        documents = []
        for ev in pack.evidences:
            doc = Document(
                page_content=ev.chunk.text,
                metadata={
                    "chunk_id": ev.chunk.chunk_id,
                    "section": ev.chunk.provision,
                    "article": ev.chunk.provision,
                    "source_title": ev.chunk.title,
                    "document_id": ev.chunk.title,
                    "jurisdiction": ev.chunk.jurisdiction.value,
                    "authority_level": ev.chunk.authority_level if ev.chunk.authority_level is not None else ev.chunk.source_authority,
                    "document_type": ev.chunk.document_type,
                    # Use chunk's actual legal_area (not the sub-query area) for meaningful applicability scoring.
                    "legal_area": ev.chunk.legal_area or pack.sub_query.legal_area.value,
                    "status": "active"
                }
            )
            documents.append((doc, ev.chunk.vector_score or 0.5))
            
        # Call LegalReranker async with effective query combining user query + sub-query terms
        sq_text = getattr(pack.sub_query, "query_text", "")
        effective_query = f"{query} - {sq_text}" if sq_text else query

        try:
            reranked_tuples = await reranker_instance.rerank_async(
                query=effective_query,
                results=documents,
                query_context=query_context
            )
        except Exception as e:
            logger.error(f"LegalReranker async failed: {e}. Falling back to original order.")
            reranked_tuples = [(doc, float(score), {}) for doc, score in documents]
        
        new_evidences = []
        chunk_map = {ev.chunk.chunk_id: ev.chunk for ev in pack.evidences}
        
        for doc, composite_score, signals in reranked_tuples:
            chunk_id = doc.metadata.get("chunk_id")
            chunk = chunk_map.get(chunk_id)
            if chunk:
                new_ev = RankedEvidence(
                    chunk=chunk,
                    relevance_score=signals.get("relevance", 0.0),
                    authority_score=signals.get("authority", 0.0),
                    jurisdiction_score=signals.get("jurisdiction", 0.0),
                    freshness_score=signals.get("freshness", 0.0),
                    applicability_score=signals.get("applicability", 0.0),
                    final_score=composite_score
                )
                new_evidences.append(new_ev)
                
        reranked_packs.append(EvidencePack(
            sub_query=pack.sub_query,
            evidences=new_evidences
        ))
        
    return reranked_packs

