from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from app.config import settings
from app.services.chatbot_service import chatbot_service
from app.graph.builder import init_postgres_checkpointer, close_postgres_checkpointer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Initializing IP-SAKTI Legal RAG backend services...")
    
    # 1. Initialize Persistent PostgreSQL Checkpointer if configured
    if settings.postgres_uri:
        logger.info("Configuring PostgreSQL persistent checkpointer...")
        try:
            import asyncio
            await asyncio.wait_for(init_postgres_checkpointer(settings.postgres_uri), timeout=8.0)
        except asyncio.TimeoutError:
            logger.warning("PostgreSQL checkpointer setup timed out after 8s. Running with default in-memory checkpointer.")
        except Exception as e:
            logger.warning(f"PostgreSQL checkpointer setup failed: {e}. Running with default in-memory checkpointer.")
    else:
        logger.info("POSTGRES_URI not set. Running with default in-memory checkpointer (MemorySaver).")

    # 2. Initialize Chatbot service
    try:
        chatbot_service.initialize()
        logger.info("Chatbot service initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Chatbot service: {e}")

    # 3. Warm up embedding model in the background after Cloud Run startup probe succeeds
    async def _warmup_background():
        try:
            import asyncio
            # Wait 20 seconds so Cloud Run probes the container on port 8080 and marks it HEALTHY first
            await asyncio.sleep(20)
            from app.retrieval.vector_store import get_embeddings
            logger.info("Initiating background embedding model warmup...")
            await asyncio.to_thread(get_embeddings)
            logger.info("Embedding model warmed up successfully in background.")
        except Exception as e:
            logger.warning(f"Background embedding warmup skipped or failed: {e}")

    import asyncio
    asyncio.create_task(_warmup_background())
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down IP-SAKTI backend...")
    if settings.postgres_uri:
        await close_postgres_checkpointer()
    logger.info("Backend shutdown complete.")
