import time
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from app.config import settings

router = APIRouter()

@router.get("", summary="Liveness probe")
@router.get("/live", summary="Liveness probe (K8s /healthz)")
async def liveness_check() -> Dict[str, Any]:
    """
    Lightweight Liveness probe.
    Confirms the FastAPI server process is running and accepting HTTP requests.
    Does not make external network or database calls.
    """
    return {
        "status": "healthy",
        "service": "ip-sakti-backend",
        "type": "liveness"
    }


@router.get("/ready", summary="Readiness probe")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe (K8s /readyz).
    Verifies critical dependencies (Qdrant cluster connectivity, LLM API keys)
    before traffic is routed to this replica. Returns 503 if dependencies fail.
    """
    components: Dict[str, Any] = {}
    is_ready = True

    # 1. Check LLM Configuration
    has_llm_key = bool(settings.gemini_api_key or settings.groq_api_key)
    components["llm_configuration"] = {
        "status": "configured" if has_llm_key else "missing_api_key",
        "provider": "gemini" if settings.gemini_api_key else ("groq" if settings.groq_api_key else "none"),
        "model": settings.generation_model
    }
    if not has_llm_key:
        is_ready = False

    # 2. Check Vector Store Connectivity (Lightweight ping)
    try:
        from app.retrieval.vector_store import get_qdrant_client
        client = get_qdrant_client()
        if client is not None:
            start_t = time.perf_counter()
            collections = client.get_collections()
            ping_latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            components["vector_store"] = {
                "status": "connected",
                "endpoint": settings.cluster_endpoint or "cloud",
                "collection_count": len(collections.collections),
                "latency_ms": ping_latency_ms
            }
        else:
            # Fallback to ingestion manager if available locally
            try:
                from structure.models import LegalDocumentConfig
                from vectorstore.manager import VectorStoreManager
                start_t = time.perf_counter()
                config = LegalDocumentConfig()
                manager = VectorStoreManager(config)
                collections = manager.client.get_collections()
                ping_latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                components["vector_store"] = {
                    "status": "connected",
                    "endpoint": config.qdrant_url or "cloud",
                    "collection_count": len(collections.collections),
                    "latency_ms": ping_latency_ms
                }
            except Exception:
                components["vector_store"] = {
                    "status": "unconfigured",
                    "message": "Cluster endpoint not set or client unavailable"
                }
                is_ready = False
    except Exception as e:
        logger.warning(f"Readiness check: Vector store probe failed ({e})")
        components["vector_store"] = {
            "status": "unreachable",
            "error": str(e)
        }
        is_ready = False

    # 3. Check Neural Reranker Configuration
    components["neural_reranker"] = {
        "enabled": settings.use_neural_reranker,
        "model": settings.neural_reranker_model if settings.use_neural_reranker else "rule-based baseline"
    }

    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "reason": "One or more critical dependencies are unreachable or unconfigured",
                "components": components
            }
        )

    return {
        "status": "ready",
        "service": "ip-sakti-backend",
        "type": "readiness",
        "components": components
    }


@router.get("/detailed", summary="Detailed system diagnostics")
async def detailed_diagnostics() -> Dict[str, Any]:
    """
    Detailed diagnostic inspection endpoint for DevOps and monitoring dashboards.
    """
    try:
        ready_status = await readiness_check()
        ready_status["max_clarification_rounds"] = settings.max_clarification_rounds
        ready_status["checkpoint_dir"] = settings.checkpoint_dir
        return ready_status
    except HTTPException as e:
        return e.detail
