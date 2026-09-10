from typing import Optional
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_core.embeddings import Embeddings
from loguru import logger

from app.config import settings

_qdrant_client: Optional[QdrantClient] = None
_embeddings: Optional[Embeddings] = None
_vector_stores: dict[str, QdrantVectorStore] = {}


def get_qdrant_client() -> Optional[QdrantClient]:
    """
    Initializes and returns a singleton QdrantClient connection.
    Reads credentials from app.config.settings (cluster_endpoint & qdrant_api_key).
    """
    global _qdrant_client
    if _qdrant_client is None:
        endpoint = settings.cluster_endpoint
        if not endpoint:
            logger.warning("CLUSTER_ENDPOINT is not configured. Vector retrieval will operate in fallback mode.")
            return None
        try:
            logger.info(f"Connecting to Qdrant cluster at: {endpoint}")
            _qdrant_client = QdrantClient(
                url=endpoint,
                api_key=settings.qdrant_api_key or None,
                timeout=60
            )
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant cluster: {e}")
            return None
    return _qdrant_client


def get_embeddings() -> Optional[Embeddings]:
    """
    Initializes the embedding model configured in settings:
    - 'gemini': GoogleGenerativeAIEmbeddings
    - 'lm_studio': OpenAI-compatible embeddings from local LM Studio
    - 'huggingface': HuggingFaceEmbeddings (e.g. BAAI/bge-m3)
    """
    global _embeddings
    if _embeddings is None:
        provider = settings.embedding_provider.lower()
        try:
            if provider in ("gemini", "google", "google-genai"):
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                model = settings.embedding_model or "models/gemini-embedding-001"
                api_key = settings.gemini_api_key
                if not api_key:
                    logger.warning("GEMINI_API_KEY is not set for Gemini embeddings.")
                _embeddings = GoogleGenerativeAIEmbeddings(
                    model=model,
                    google_api_key=api_key,
                    output_dimensionality = 1024
                )
                logger.info(f"Initialized Google Gemini Embeddings: {model}")
            elif provider == "lm_studio":
                from langchain_openai import OpenAIEmbeddings
                model = settings.embedding_model or "text-embedding-bge-large-en-v1.5"
                _embeddings = OpenAIEmbeddings(
                    base_url=settings.lm_studio_base_url,
                    api_key="lm-studio",
                    model=model,
                    check_embedding_ctx_length=False
                )
                logger.info(f"Initialized LM Studio Embeddings: {model} at {settings.lm_studio_base_url}")
            else:
                from langchain_huggingface import HuggingFaceEmbeddings
                model = settings.embedding_model or "BAAI/bge-m3"
                _embeddings = HuggingFaceEmbeddings(
                    model_name=model,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True}
                )
                logger.info(f"Initialized HuggingFace Embeddings: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize embedding model ({provider}): {e}")
            return None
    return _embeddings


def _ensure_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    """
    Attempts to create keyword payload indexes for legal_area and applicable_product
    if they don't already exist. Safely ignores any errors if the index exists or
    permissions are restricted.
    """
    for field in ["metadata.legal_area", "legal_area", "metadata.applicable_product", "applicable_product"]:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema="keyword",
            )
        except Exception:
            pass


def get_vector_store(qdrant_collection: str = "legal_acts") -> Optional[QdrantVectorStore]:
    """
    Returns a QdrantVectorStore instance backed by the backend's native QdrantClient
    and selected embedding model, cached per collection.
    """
    global _vector_stores
    target_collection = qdrant_collection
    if target_collection not in _vector_stores:
        client = get_qdrant_client()
        embeddings = get_embeddings()
        if client is None or embeddings is None:
            return None
        try:
            store = QdrantVectorStore(
                client=client,
                collection_name=target_collection,
                embedding=embeddings
            )
            _ensure_payload_indexes(client, target_collection)
            _vector_stores[target_collection] = store
            logger.info(f"Connected to Qdrant collection: '{target_collection}'")
        except Exception as e:
            logger.error(f"Failed to initialize QdrantVectorStore for collection '{target_collection}': {e}")
            return None
    return _vector_stores[target_collection]


def ping_qdrant() -> bool:
    """
    Lightweight health check for Qdrant connectivity.
    """
    client = get_qdrant_client()
    if client is None:
        return False
    try:
        client.get_collections()
        return True
    except Exception as e:
        logger.warning(f"Qdrant ping health check failed: {e}")
        return False
