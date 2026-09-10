import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
load_dotenv()
class Settings(BaseSettings):
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    
    # Qdrant Vector Database
    qdrant_api_key: str | None = None
    cluster_endpoint: str | None = None
    
    # Embedding Configuration
    embedding_provider: str = "gemini"  # "gemini", "lm_studio", or "huggingface"
    embedding_model: str | None = None
    
    # LLM Providers & Models (Segregated per pipeline task)
    llm_provider: str = "gemini"  # Default global fallback: "gemini", "lm_studio", "groq", or "ollama"
    extraction_provider: str | None = None  # e.g. "groq" for fast JSON slot-filling
    extraction_model: str = "gemini-2.5-flash"
    
    generation_provider: str | None = None  # e.g. "gemini" for authoritative statutory synthesis
    generation_model: str = "gemini-2.5-flash"
    
    lm_studio_base_url: str = "http://127.0.0.1:1234/v1"
    
    # Neural Reranker Configuration
    use_neural_reranker: bool = False
    neural_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    
    # Clarification Configuration
    max_clarification_rounds: int = 2
    
    # Memory & Checkpoint Configuration
    checkpoint_dir: str = "checkpoints"
    memory_window_size: int = 5
    postgres_uri: str | None = None  # e.g. "postgresql://user:password@localhost:5432/ip_sakti"
    langsmith_tracing: bool = False
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
