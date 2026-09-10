import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Config(BaseSettings):
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
    CLUSTER_ENDPOINT: Optional[str] = os.getenv("CLUSTER_ENDPOINT")
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "gemini")  # "gemini" or "huggingface"

    class Config:
        env_file = ".env"
        extra = "ignore"


config = Config()