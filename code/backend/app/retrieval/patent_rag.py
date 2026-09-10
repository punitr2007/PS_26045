from typing import List, Optional
from app.schemas.pipeline import SubQuery, EvidencePack, RankedEvidence
from app.retrieval.base import RAGPipeline
from app.retrieval import hybrid_retriever
from app.schemas.enums import LegalArea

# Mapping from sub-query legal_area to the Qdrant payload legal_area values that are relevant.
_AREA_FILTER_MAP = {
    LegalArea.PATENT:      ["patent"],
    LegalArea.GI:          ["gi", "patent"],   # GI Act + Patents Act Section 3(p) both relevant
    LegalArea.TRADEMARK:   ["trademark"],
    LegalArea.TK_PRIOR_ART: ["patent", "tk_prior_art"],
}

class PatentRAG(RAGPipeline):
    
    @classmethod
    async def retrieve_batch(cls, sub_queries: List[SubQuery]) -> List[EvidencePack]:
        packs = []
        collection_name = "legal_acts_patent"
        for sq in sub_queries:
            # Pick the right filter for this sub-query's legal area
            area_filter = _AREA_FILTER_MAP.get(sq.legal_area, ["patent"])
            
            product_category: Optional[str] = getattr(sq, "product_category", None)
            chunks = await hybrid_retriever.retrieve(
                query=sq.query_text,
                legal_area_filter=area_filter,
                top_k=5,
                collection_name=collection_name,
                product_category=product_category,
            )
            
            # Wrap chunks in unranked Evidence objects for the reranker
            evidences = [
                RankedEvidence(
                    chunk=c,
                    relevance_score=0.0,
                    authority_score=0.0,
                    jurisdiction_score=0.0,
                    freshness_score=0.0,
                    applicability_score=0.0,
                    final_score=0.0
                ) for c in chunks
            ]
            packs.append(EvidencePack(sub_query=sq, evidences=evidences))
        return packs

retrieve_batch = PatentRAG.retrieve_batch
