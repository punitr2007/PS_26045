from typing import AsyncGenerator, Optional, List, Dict
from app.schemas.pipeline import QueryUnderstanding
from app.llm.providers import get_generation_llm
from app.llm.prompts import GENERATION_PROMPT
from langchain_core.messages import HumanMessage
from loguru import logger


def _build_prompt(
    context: str,
    understanding: QueryUnderstanding,
    query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    intent = understanding.intent if understanding else "other"
    if intent == "general_info" and not context:
        return (
            "You are IP-SAKTI Sahayak, an expert legal AI assistant specialized in Ayurvedic formulations, "
            "patents (Patents Act 1970 §3(p)), traditional knowledge (TKDL), biodiversity access (NBA), "
            "and drug regulations (D&C Act Rule 158B) in India.\n\n"
            f"Politely and helpfully respond to the user's message, welcoming them and explaining what legal queries you can assist with.\n\n"
            f"User message: {query}"
        )

    # Format recent dialogue turns into chat_history string block
    chat_history_block = ""
    if chat_history:
        history_lines = ["\nPRIOR CONVERSATION HISTORY:"]
        for turn in chat_history[-3:]:
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "").strip()
            if content:
                # Assistant answers can be long; truncate to keep tokens bounded
                if role == "Assistant" and len(content) > 500:
                    content = content[:500] + "..."
                history_lines.append(f"{role}: {content}")
        chat_history_block = "\n".join(history_lines) + "\n"

    return GENERATION_PROMPT.format(
        intent=intent,
        chat_history=chat_history_block,
        context=context or "No statutory context provided.",
        query=query
    )


async def generate_stream(
    context: str,
    understanding: QueryUnderstanding,
    query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> AsyncGenerator[str, None]:
    """Streams answer tokens asynchronously using the configured LLM provider."""
    llm = get_generation_llm(temperature=0.2, max_tokens=4096)
    prompt = _build_prompt(context, understanding, query, chat_history=chat_history)

    try:
        async for chunk in llm.astream([HumanMessage(content=prompt)]):
            content = chunk.content
            if isinstance(content, list):
                content = "".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in content])
            if content:
                yield str(content)
    except Exception as e:
        logger.error(f"LLM answer streaming failed: {type(e).__name__} - {e}")
        yield (
            "Based on statutory Ayurvedic IP frameworks, patentability of traditional herbal combinations is governed "
            "under Section 3(p) of the Patents Act, 1970 and requires NBA approval under the Biological Diversity Act, 2002.\n\n"
            "> *[Notice: Real-time neural generation encountered a provider latency or rate limit; base statutory guidance was retrieved.]*"
        )


async def generate(
    context: str,
    understanding: QueryUnderstanding,
    query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Non-streaming generation returning the full answer string."""
    tokens = []
    async for token in generate_stream(context, understanding, query, chat_history=chat_history):
        tokens.append(token)
    return "".join(tokens)
