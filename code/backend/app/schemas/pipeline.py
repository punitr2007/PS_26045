from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.schemas.enums import Jurisdiction, ProductCategory, LegalArea

class AnswerRelevanceResult(BaseModel):
    """Represents the output of the answer relevance check."""
    is_relevant: bool = Field(default=False)
    extracted_facts: Dict[str, Any] = Field(default={})
    is_new_topic: bool = Field(default=False)
    reasoning: Optional[str] = None

class QueryUnderstanding(BaseModel):
    """Represents extracted intent, entities, and product information from the query."""
    intent: str
    entities: List[str] = Field(default=[])
    mentions_jurisdiction: Optional[str] = None
    raw_product_description: Optional[str] = None

class ClarificationQuestion(BaseModel):
    """A single clarifying question to ask the user."""
    field: str
    question: str
    options: Optional[List[str]] = None

class ProductClassification(BaseModel):
    """Represents the statutory classification of the Ayurvedic product."""
    ingredients: List[str] = Field(default=[])
    category: ProductCategory = Field(default=ProductCategory.UNCLASSIFIED)
    route_of_administration: str = "unknown"
    intended_use: str = "unknown"
    dosage_form: Optional[str] = None
    confidence: float = Field(default=0.5)
    reasoning: str = Field(default="Initial classification.")
    missing_facts: List[str] = Field(default=[])
    hyde_context: Optional[str] = None  # Declarative product description for retrieval (HyDE)

class SubQuery(BaseModel):
    """Represents a single sub-query targeted to a specific legal domain."""
    legal_area: LegalArea
    query_text: str
    jurisdiction: Jurisdiction
    # Product category (e.g. "classical", "proprietary") carried from classification
    # so RAG pipelines can apply applicable_product Qdrant payload filtering.
    product_category: Optional[str] = None

class QueryDecomposition(BaseModel):
    """Collection of subqueries generated for multi-domain legal retrieval."""
    sub_queries: List[SubQuery] = Field(default=[])
    product_classification: Optional[ProductClassification] = None
    jurisdiction: Optional[Jurisdiction] = None

class RetrievedChunk(BaseModel):
    """Represents a chunk retrieved from the Qdrant vector store."""
    chunk_id: str
    text: str
    provision: str = "N/A"
    title: str = "N/A"
    chapter: str = "N/A"
    pages: str = "?"
    source_authority: str = "Unknown Document"
    authority_level: Optional[int] = None
    document_type: Optional[str] = None
    jurisdiction: Jurisdiction = Jurisdiction.INDIA
    legal_area: Optional[str] = None   # Actual legal_area from Qdrant payload metadata
    vector_score: float = 0.0
    keyword_score: float = 0.0


class RankedEvidence(BaseModel):
    """Represents a retrieved chunk scored across legal signals by LegalReranker."""
    chunk: RetrievedChunk
    relevance_score: float = 0.0
    authority_score: float = 0.0
    jurisdiction_score: float = 0.0
    freshness_score: float = 0.0
    applicability_score: float = 0.0
    final_score: float = 0.0

class EvidencePack(BaseModel):
    """Pairs a SubQuery with its set of ranked legal evidence chunks."""
    sub_query: SubQuery
    evidences: List[RankedEvidence] = Field(default=[])

class GuardrailResult(BaseModel):
    """Evaluation result from the legal grounding and evidence sufficiency guardrail."""
    passed: bool
    enough_evidence: bool = True
    current_law: bool = True
    correct_jurisdiction: bool = True
    reason: Optional[str] = None
    verified_citations: List[str] = Field(default_factory=list)
    unverified_citations: List[str] = Field(default_factory=list)