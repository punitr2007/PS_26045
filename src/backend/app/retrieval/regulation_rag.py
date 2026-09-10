from typing import List, Optional
from app.schemas.pipeline import SubQuery, EvidencePack, RankedEvidence
from app.retrieval.base import RAGPipeline
from app.retrieval import hybrid_retriever

class RegulationRAG(RAGPipeline):
    
    @classmethod
    async def retrieve_batch(cls, sub_queries: List[SubQuery]) -> List[EvidencePack]:
        packs = []
        collection_name = "legal_acts_patent"
        for sq in sub_queries:
            product_category: Optional[str] = getattr(sq, "product_category", None)
            chunks = await hybrid_retriever.retrieve(
                query=sq.query_text,
                legal_area_filter="regulation",
                top_k=5,
                collection_name=collection_name,
                product_category=product_category,
            )
            
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

retrieve_batch = RegulationRAG.retrieve_batch
