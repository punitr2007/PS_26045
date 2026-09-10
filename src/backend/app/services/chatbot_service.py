import datetime
from typing import Dict, Any, Optional

from app.services.memory_service import memory_service
from app.graph.builder import get_rag_app


class ChatbotService:
    def __init__(self):
        pass

    def initialize(self):
        pass

    def _get_formatted_history(self, session_id: str, max_turns: int = 4) -> list:
        """Retrieves and formats recent turns for the session as role/content pairs."""
        raw_history = memory_service.get_history(session_id) or []
        recent_turns = raw_history[-max_turns:] if len(raw_history) > max_turns else raw_history
        history = []
        for turn in recent_turns:
            user_msg = turn.get("user_query")
            asst_msg = turn.get("assistant_response")
            if user_msg:
                history.append({"role": "user", "content": str(user_msg)})
            if asst_msg:
                history.append({"role": "assistant", "content": str(asst_msg)})
        return history

    async def process_chat_async(
        self,
        session_id: str,
        query: str,
        top_k: int = 8,
        known_facts: Optional[Dict[str, Any]] = None,
        jurisdiction: str = "national",
    ) -> Dict[str, Any]:
        """
        Processes a single chat turn asynchronously using the LangGraph StateGraph.
        jurisdiction: "national" | "international" — forwarded from ChatFilter so the
        jurisdiction toggle in the frontend actually affects retrieval and generation.
        """
        # Load accumulated known_facts and prior dialogue history from memory
        prior_facts = memory_service.get_known_facts(session_id) or {}
        merged_facts = {**prior_facts, **(known_facts or {})}

        if jurisdiction:
            merged_facts["jurisdiction"] = jurisdiction

        chat_history = self._get_formatted_history(session_id)

        initial_state = {
            "query": query,
            "session_id": session_id,
            "evidence_packs": [],
            "retry_count": 0,
            "known_facts": merged_facts,
            "chat_history": chat_history,
        }
        
        # Invoke the LangGraph app with the current session thread
        config = {"configurable": {"thread_id": session_id}}
        
        app_instance = get_rag_app()
        final_state = await app_instance.ainvoke(initial_state, config=config)
        
        # Extract the outputs from the final state
        status = final_state.get("status", "answered")
        answer = final_state.get("final_answer", "")
        pending_questions = final_state.get("pending_questions", [])
        
        # Format sources from the final reranked top_evidences for the frontend
        sources = []
        top_evidences = final_state.get("top_evidences")
        if not top_evidences and final_state.get("evidence_packs"):
            from app.generation.evidence_pack import merge
            _, top_evidences = merge(final_state["evidence_packs"], top_n_total=top_k)

        if top_evidences:
            from app.generation.evidence_pack import format_sources
            sources = format_sources(top_evidences, max_sources=top_k)
        
        # Save to memory service for history tracking
        turn_data = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "user_query": query,
            "assistant_response": answer,
            "sources": sources,
        }
        turn_index = memory_service.append_turn(session_id, turn_data)

        # Persist accumulated known_facts for the session
        updated_facts = final_state.get("known_facts") or merged_facts
        if updated_facts:
            memory_service.save_known_facts(session_id, updated_facts)

        response = {
            "session_id": session_id,
            "answer": answer,
            "sources": sources,
            "turn_index": turn_index,
            "timestamp": turn_data["timestamp"],
            "status": status,
        }
        if status == "needs_clarification" and pending_questions:
            response["questions"] = pending_questions
            
        return response

    async def process_chat_stream(
        self,
        session_id: str,
        query: str,
        top_k: int = 8,
        known_facts: Optional[Dict[str, Any]] = None,
        jurisdiction: str = "national",
    ):
        """
        Processes a chat turn yielding Server-Sent Events (SSE) in real time:
        - status: Pipeline progress (retrieval, reranking, synthesis)
        - sources: Grounded statutory citations as soon as reranked
        - token: AI answer tokens streamed word-by-word
        - clarification: Slot-filling questions if missing facts
        - done: Final turn completion payload with session_id & turn_index
        """
        import json
        import asyncio
        from loguru import logger
        from app.services.streaming_context import streaming_queue_var

        queue = asyncio.Queue()
        token = streaming_queue_var.set(queue)

        async def _run_graph():
            try:
                prior_facts = memory_service.get_known_facts(session_id) or {}
                merged_facts = {**prior_facts, **(known_facts or {})}

                if jurisdiction:
                    merged_facts["jurisdiction"] = jurisdiction

                chat_history = self._get_formatted_history(session_id)

                initial_state = {
                    "query": query,
                    "session_id": session_id,
                    "evidence_packs": [],
                    "retry_count": 0,
                    "known_facts": merged_facts,
                    "chat_history": chat_history,
                }

                config = {"configurable": {"thread_id": session_id}}
                app_instance = get_rag_app()
                final_state = await app_instance.ainvoke(initial_state, config=config)

                status = final_state.get("status", "answered")
                answer = final_state.get("final_answer", "")
                pending_questions = final_state.get("pending_questions", [])

                sources = []
                top_evidences = final_state.get("top_evidences")
                if not top_evidences and final_state.get("evidence_packs"):
                    from app.generation.evidence_pack import merge
                    _, top_evidences = merge(final_state["evidence_packs"], top_n_total=top_k)

                if top_evidences:
                    from app.generation.evidence_pack import format_sources
                    sources = format_sources(top_evidences, max_sources=top_k)

                turn_data = {
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "user_query": query,
                    "assistant_response": answer,
                    "sources": sources,
                }
                turn_index = memory_service.append_turn(session_id, turn_data)

                updated_facts = final_state.get("known_facts") or merged_facts
                if updated_facts:
                    memory_service.save_known_facts(session_id, updated_facts)

                done_event = {
                    "type": "done",
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "status": status,
                    "timestamp": turn_data["timestamp"],
                    "sources": sources,
                    "answer": answer,
                }
                if status == "needs_clarification" and pending_questions:
                    done_event["questions"] = pending_questions

                await queue.put(done_event)

            except Exception as e:
                logger.error(f"Error in chat stream execution: {type(e).__name__} - {e}")
                import traceback
                traceback.print_exc()
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(None)

        task = asyncio.create_task(_run_graph())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            streaming_queue_var.reset(token)
            if not task.done():
                task.cancel()

    def process_chat(self, session_id: str, query: str, top_k: int = 8) -> Dict[str, Any]:
        """Synchronous wrapper for FastAPI router backward compatibility."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            import threading
            result = None
            def run_in_new_loop():
                nonlocal result
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(self.process_chat_async(session_id, query, top_k))
                new_loop.close()
            thread = threading.Thread(target=run_in_new_loop)
            thread.start()
            thread.join()
            return result
        else:
            return asyncio.run(self.process_chat_async(session_id, query, top_k))

chatbot_service = ChatbotService()
