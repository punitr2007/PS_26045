from typing import Dict, Any
from app.schemas.pipeline import SubQuery
from app.retrieval.patent_rag import PatentRAG
from app.retrieval.abs_rag import AbsRAG
from app.retrieval.regulation_rag import RegulationRAG

async def patent_retrieval_node(state: SubQuery) -> Dict[str, Any]:
    packs = await PatentRAG.retrieve_batch([state])
    return {"evidence_packs": packs}

async def abs_retrieval_node(state: SubQuery) -> Dict[str, Any]:
    packs = await AbsRAG.retrieve_batch([state])
    return {"evidence_packs": packs}

async def regulation_retrieval_node(state: SubQuery) -> Dict[str, Any]:
    packs = await RegulationRAG.retrieve_batch([state])
    return {"evidence_packs": packs}
