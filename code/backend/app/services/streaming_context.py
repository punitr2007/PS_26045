import asyncio
import contextvars
from typing import Optional, Dict, Any

# Async task-local context variable holding the active SSE event queue
streaming_queue_var: contextvars.ContextVar[Optional[asyncio.Queue]] = contextvars.ContextVar(
    "streaming_queue_var", default=None
)


async def emit_stream_event(event: Dict[str, Any]) -> None:
    """Emits an event dictionary if an active streaming queue exists in the task context."""
    queue = streaming_queue_var.get()
    if queue is not None:
        await queue.put(event)
