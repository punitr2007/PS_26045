import os
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from loguru import logger


class EmbeddingFactory:
    """
    Factory for instantiating, managing dimensions, and configuring embedding models.
    Supports:
      - Google Gemini (e.g. 'models/gemini-embedding-001', 'models/gemini-embedding-2') -> 3072 dimensions
      - HuggingFace (e.g. 'BAAI/bge-small-en-v1.5', 'all-MiniLM-L6-v2') -> 384 dimensions
    """

    @staticmethod
    def get_dimension(provider: str, model_name: str) -> int:
        """Returns standard vector dimension for the given provider and model."""
        prov = provider.lower()
        if prov in ("gemini", "google", "google-genai"):
            # Gemini embedding models (gemini-embedding-001, gemini-embedding-2) output 3072 dims
            return 3072
        else:
            if "bge-m3" in model_name:
                return 1024  # BAAI/bge-m3 outputs 1024-dim
            if "bge-base" in model_name:
                return 768
            if "bge-large" in model_name:
                return 1024
            return 384  # BAAI/bge-small-en-v1.5 / all-MiniLM-L6-v2

    @staticmethod
    def create_embeddings(
        provider: str = "gemini",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Embeddings:
        """
        Creates an Embeddings instance based on provider ('gemini' or 'huggingface').
        """
        provider = (provider or os.getenv("EMBEDDING_PROVIDER", "gemini")).lower()

        if provider in ("gemini", "google", "google-genai"):
            selected_model = model_name or "models/gemini-embedding-001"
            gemini_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not gemini_key:
                raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is required when using provider='gemini'.")
            dim = EmbeddingFactory.get_dimension("gemini", selected_model)
            logger.info(f"Initializing Google Gemini Embeddings model: '{selected_model}' (dim={dim})...")
            return GoogleGenerativeAIEmbeddings(
                model=selected_model,
                google_api_key=gemini_key
            )
        else:
            selected_model =  "BAAI/bge-m3"
            dim = EmbeddingFactory.get_dimension("huggingface", selected_model)
            logger.info(f"Initializing HuggingFace Embeddings model: '{selected_model}' (dim={dim})...")
            return HuggingFaceEmbeddings(
                model_name=selected_model,
                cache_folder="./models",
                show_progress=True,
                model_kwargs={"trust_remote_code": True, "device": "cpu"},
                encode_kwargs={"batch_size": 4, "normalize_embeddings": True}
            )
