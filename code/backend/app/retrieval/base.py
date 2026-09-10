import abc
from typing import List
from app.schemas.pipeline import SubQuery, EvidencePack

class RAGPipeline(abc.ABC):
    """Protocol for domain-specific RAG modules."""
    
    @classmethod
    @abc.abstractmethod
    async def retrieve_batch(cls, sub_queries: List[SubQuery]) -> List[EvidencePack]:
        """
        Takes a list of SubQuery objects (all mapped to this domain),
        runs retrieval, and returns EvidencePacks for each.
        """
        pass
