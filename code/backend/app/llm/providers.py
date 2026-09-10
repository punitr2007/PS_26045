import os
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger
from app.config import settings

def _create_llm(
    provider_override: Optional[str],
    model_name: Optional[str],
    temperature: float,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    Factory that lazily instantiates the appropriate chat model based on provider.
    Supported providers:
      - 'gemini': Google Generative AI (requires langchain-google-genai and GEMINI_API_KEY)
      - 'lm_studio': Local LM Studio server (OpenAI-compatible)
      - 'groq': Groq Cloud API (OpenAI-compatible, ultra-low latency)
      - 'ollama': Local Ollama instance (OpenAI-compatible)
    """
    provider = (provider_override or settings.llm_provider or "gemini").lower()
    effective_max_tokens = max_tokens or 4096

    # 1. Local LM Studio (OpenAI-compatible local server)
    if provider == "lm_studio":
        from langchain_openai import ChatOpenAI
        selected_model = model_name or "qwen3.5-9b"
        logger.info(f"Connecting to LM Studio LLM: '{selected_model}' at {settings.lm_studio_base_url} (max_tokens={effective_max_tokens})")
        return ChatOpenAI(
            base_url=settings.lm_studio_base_url,
            model=selected_model,
            api_key="lm-studio",
            temperature=temperature,
            max_tokens=effective_max_tokens,
            timeout=180.0,
        )

    # 2. Groq Cloud (Ultra-fast OpenAI-compatible API)
    elif provider == "groq":
        from langchain_openai import ChatOpenAI
        selected_model = model_name or "llama-3.3-70b-versatile"
        api_key = settings.groq_api_key
        if not api_key:
            logger.warning("GROQ_API_KEY is not set. Groq calls may fail.")
        logger.info(f"Connecting to Groq LLM: '{selected_model}'")
        return ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            model=selected_model,
            api_key=api_key or "missing-key",
            temperature=temperature,
            max_tokens=effective_max_tokens,
            timeout=180.0,
        )

    # 3. Local Ollama (OpenAI-compatible local engine)
    elif provider == "ollama":
        from langchain_openai import ChatOpenAI
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        selected_model = model_name or "qwen2.5:7b"
        logger.info(f"Connecting to Ollama LLM: '{selected_model}' at {ollama_url}")
        return ChatOpenAI(
            base_url=ollama_url,
            model=selected_model,
            api_key="ollama",
            temperature=temperature,
            max_tokens=effective_max_tokens,
            timeout=180.0,
        )

    # 4. Google Gemini (Default cloud provider)
    else:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            selected_model = model_name or "gemini-2.5-flash"
            kwargs = {
                "temperature": temperature,
                "model": selected_model,
                "max_output_tokens": effective_max_tokens,
            }
            if settings.gemini_api_key:
                kwargs["google_api_key"] = settings.gemini_api_key
            logger.info(f"Connecting to Google Gemini LLM: '{selected_model}'")
            return ChatGoogleGenerativeAI(**kwargs)
        except ImportError:
            logger.error(
                "langchain_google_genai is not installed. "
                "To use Gemini, run: pip install langchain-google-genai. "
                "Alternatively, set EXTRACTION_PROVIDER / GENERATION_PROVIDER in .env."
            )
            # Automatic fallback to Groq or LM Studio
            if settings.groq_api_key:
                logger.info("Falling back to Groq Cloud using GROQ_API_KEY...")
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    model="llama-3.3-70b-versatile",
                    api_key=settings.groq_api_key,
                    temperature=temperature,
                    max_tokens=effective_max_tokens,
                    timeout=60.0,
                )
            from langchain_openai import ChatOpenAI
            logger.info("Falling back to LM Studio at http://127.0.0.1:1234/v1...")
            return ChatOpenAI(
                base_url=settings.lm_studio_base_url,
                model="local-model",
                api_key="lm-studio",
                temperature=temperature,
                max_tokens=effective_max_tokens,
                timeout=60.0,
            )


def get_extraction_llm(temperature: float = 0.0, max_tokens: int = 512) -> BaseChatModel:
    """
    Returns the LLM for structured extraction and classification tasks (low temperature).
    Uses extraction_provider if configured, otherwise falls back to llm_provider.
    """
    provider = settings.extraction_provider or settings.llm_provider
    return _create_llm(provider, settings.extraction_model, temperature, max_tokens=max_tokens)


def get_generation_llm(temperature: float = 0.2, max_tokens: int = 4096) -> BaseChatModel:
    """
    Returns the LLM for generating final legal synthesis answers.
    Uses generation_provider if configured, otherwise falls back to llm_provider.
    """
    provider = settings.generation_provider or settings.llm_provider
    return _create_llm(provider, settings.generation_model, temperature, max_tokens=max_tokens)

get_llm = get_generation_llm



_cross_encoder_instance = None

def get_cross_encoder():
    """
    Returns the singleton CrossEncoder instance if neural reranking is enabled in config.
    Lazy-loads sentence_transformers to preserve instant startup when disabled.
    """
    global _cross_encoder_instance
    if _cross_encoder_instance is None and settings.use_neural_reranker:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder_instance = CrossEncoder(settings.neural_reranker_model)
        except Exception as e:
            logger.warning(f"Could not initialize CrossEncoder ({settings.neural_reranker_model}): {e}. Falling back to rule scoring.")
            _cross_encoder_instance = None
    return _cross_encoder_instance
