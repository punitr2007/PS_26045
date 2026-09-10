import asyncio
from collections import defaultdict
from app.models.pipeline import QueryDecomposition, SubQuery, LegalArea, EvidencePack
from app.retrieval import patent_rag, abs_rag, regulation_rag

LEGAL_AREA_TO_RAG = {
    LegalArea.PATENT: patent_rag,
    LegalArea.GI: patent_rag,  # Fallback to patent rag logic for GI for now
    LegalArea.TRADEMARK: patent_rag, # Fallback to patent rag logic for Trademark for now
    LegalArea.ABS: abs_rag,
    LegalArea.TK_PRIOR_ART: abs_rag, # Fallback to abs rag logic for TK for now
    LegalArea.DRUG_REGULATION: regulation_rag,
}

async def distribute_and_retrieve(decomposition: QueryDecomposition) -> list[EvidencePack]:
    """Fans sub-queries out to the right RAG pipeline concurrently."""
    grouped: dict = defaultdict(list)
    for sub_query in decomposition.sub_queries:
        rag_module = LEGAL_AREA_TO_RAG.get(sub_query.legal_area, regulation_rag)
        grouped[rag_module].append(sub_query)

    tasks = [
        rag_module.retrieve_batch(sub_queries)
        for rag_module, sub_queries in grouped.items()
    ]
    results = await asyncio.gather(*tasks)
    return [pack for batch in results for pack in batch]
