from typing import Optional, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import RAGState
from app.graph.nodes.understand import understand_node
from app.graph.nodes.route import route_node
from app.graph.nodes.classify import classify_node
from app.graph.nodes.clarify import clarify_node
from app.graph.nodes.decompose import decompose_node
from app.graph.nodes.retrieve import patent_retrieval_node, abs_retrieval_node, regulation_retrieval_node
from app.graph.nodes.generate import generate_node
from app.graph.nodes.guardrail import guardrail_node
from app.graph.edges import distribute_queries, guardrail_condition, understand_condition, clarify_condition
from loguru import logger

def build_graph(checkpointer: Optional[Any] = None):
    """
    Builds and compiles the cyclical LangGraph state machine.
    Accepts an optional checkpointer (e.g. AsyncPostgresSaver or MemorySaver).
    """
    workflow = StateGraph(RAGState)
    
    # 1. Add Core Nodes
    workflow.add_node("understand", understand_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("route", route_node)
    workflow.add_node("decompose", decompose_node)
    
    # 2. Add Retrieval Nodes
    workflow.add_node("retrieve_patent", patent_retrieval_node)
    workflow.add_node("retrieve_abs", abs_retrieval_node)
    workflow.add_node("retrieve_regulation", regulation_retrieval_node)
    
    # 3. Add Generation & Guardrail Nodes
    workflow.add_node("rerank_and_generate", generate_node)
    workflow.add_node("guardrail", guardrail_node)
    
    # 4. Define Linear Execution & Intake Paths
    workflow.set_entry_point("understand")
    workflow.add_conditional_edges(
        "understand",
        understand_condition,
        {
            "continue": "classify",
            "bypass": "rerank_and_generate"
        }
    )
    
    # 5. Clarification Gate (Slot Filling)
    workflow.add_conditional_edges(
        "classify",
        clarify_condition,
        {
            "clarify": "clarify",
            "continue": "route"
        }
    )
    # Clarify pauses and checkpoints at END
    workflow.add_edge("clarify", END)
    
    # Route flows to Decompose
    workflow.add_edge("route", "decompose")
    
    # 5. Dynamic Fan-out
    workflow.add_conditional_edges(
        "decompose",
        distribute_queries,
        ["retrieve_patent", "retrieve_abs", "retrieve_regulation"]
    )
    
    # 6. Fan-in
    workflow.add_edge("retrieve_patent", "rerank_and_generate")
    workflow.add_edge("retrieve_abs", "rerank_and_generate")
    workflow.add_edge("retrieve_regulation", "rerank_and_generate")
    
    # 7. Guardrails and Retry Loop
    workflow.add_edge("rerank_and_generate", "guardrail")
    workflow.add_conditional_edges(
        "guardrail",
        guardrail_condition,
        {"retry_loop": "decompose", END: END}
    )
    
    # Default to MemorySaver if no custom checkpointer provided
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return workflow.compile(checkpointer=checkpointer)

# Global compiled graph instance (initialized with MemorySaver by default)
rag_app = build_graph()

def get_rag_app():
    """Returns the active compiled LangGraph instance."""
    global rag_app
    return rag_app

def set_rag_app(compiled_app):
    """Updates the active compiled LangGraph instance."""
    global rag_app
    rag_app = compiled_app

_postgres_pool = None

async def init_postgres_checkpointer(postgres_uri: str):
    """
    Initializes an async PostgreSQL connection pool and AsyncPostgresSaver checkpointer,
    runs table migrations (.setup()), and updates the global rag_app instance.
    """
    global _postgres_pool
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool
        from psycopg.rows import dict_row

        logger.info("Initializing PostgreSQL persistent checkpointer connection pool...")
        _postgres_pool = AsyncConnectionPool(
            conninfo=postgres_uri,
            max_size=20,
            open=False,
            timeout=5.0,
            kwargs={"autocommit": True, "row_factory": dict_row}
        )
        import asyncio
        await asyncio.wait_for(_postgres_pool.open(), timeout=6.0)

        checkpointer = AsyncPostgresSaver(_postgres_pool)
        # Automatically run table migrations (creates checkpoints, blobs, writes tables)
        await asyncio.wait_for(checkpointer.setup(), timeout=6.0)
        
        # Compile graph with persistent PostgreSQL checkpointer
        persistent_app = build_graph(checkpointer=checkpointer)
        set_rag_app(persistent_app)
        logger.info("PostgreSQL checkpointer configured and active successfully.")
        return checkpointer
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}. Falling back to in-memory checkpointer.")
        if _postgres_pool is not None:
            try:
                await _postgres_pool.close()
            except Exception:
                pass
            _postgres_pool = None
        return None

async def close_postgres_checkpointer():
    """Closes the async PostgreSQL connection pool during server shutdown."""
    global _postgres_pool
    if _postgres_pool is not None:
        try:
            await _postgres_pool.close()
            logger.info("PostgreSQL connection pool closed cleanly.")
        except Exception as e:
            logger.warning(f"Error closing PostgreSQL connection pool: {e}")
        _postgres_pool = None
