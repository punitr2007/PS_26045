from typing import Optional, List, Dict
from app.schemas.pipeline import QueryUnderstanding
from app.llm.providers import get_extraction_llm
from app.llm.prompts import EXTRACTION_PROMPT
from loguru import logger

async def process(
    query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> QueryUnderstanding:
    """Extracts intent, entities, jurisdiction, and product description from the query asynchronously,
    resolving follow-up references and pronouns from chat_history if provided."""
    llm = get_extraction_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(QueryUnderstanding)
    
    # Format prior conversation context if present
    history_context = ""
    if chat_history:
        lines = ["\nPrior conversation context:"]
        for turn in chat_history[-3:]:
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "").strip()
            if content:
                truncated_content = content[:300] + "..." if len(content) > 300 else content
                lines.append(f"{role}: {truncated_content}")
        history_context = "\n".join(lines) + "\n"
    
    prompt = EXTRACTION_PROMPT.format(history_context=history_context, user_text=query)
    
    try:
        result = await structured_llm.ainvoke(prompt)
        return result
    except Exception as e:
        logger.warning(f"Async query understanding extraction encountered: {e}. Using heuristic fallback.")
        # Heuristic keyword fallback if LLM extraction encounters rate limits
        q_lower = query.lower()
        intent = "other"
        if "patent" in q_lower or "invent" in q_lower or "3(p)" in q_lower or "3(e)" in q_lower:
            intent = "patentability"
        elif "compliance" in q_lower or "license" in q_lower or "rule 158" in q_lower or "regulation" in q_lower or "export" in q_lower:
            intent = "compliance"
        elif "biodiversity" in q_lower or "nba" in q_lower or "abs" in q_lower:
            intent = "abs_obligation"
        elif "formulation" in q_lower or "extract" in q_lower or "medicine" in q_lower or "herb" in q_lower or "protect" in q_lower:
            intent = "classification"
        elif any(greeting in q_lower for greeting in ["hi", "hello", "hey", "who are you", "what can you do"]):
            intent = "general_info"
            
        formulation_markers = [
            "formulation", "extract", "medicine", "herb", "herbal", "plant", "taila", "churna", "oil",
            "capsule", "tablet", "syrup", "cream", "gel", "lotion", "blend", "mixture", "mix", "recipe",
            "composition", "combo", "preparation", "powder", "shallaki", "ashwagandha",
            "curcumin", "neem", "tulsi", "triphala", "brahmi", "guggulu", "shatavari",
            "amla", "pippali", "haritaki", "panchagavya", "boswellia"
        ]
        has_product = any(marker in q_lower for marker in formulation_markers)
        raw_desc = query if (has_product and intent != "general_info") else None

        extracted_entities = []
        for marker in ["ashwagandha", "shallaki", "curcumin", "neem", "tulsi", "triphala", "brahmi", "guggulu", "panchagavya", "boswellia"]:
            if marker in q_lower:
                extracted_entities.append(marker.capitalize())

        # If current turn is a pronoun/follow-up without explicit formulation or entities, inherit from prior turns
        pronoun_markers = [" it", " this", " that", " these", " same", " the formulation", " the product", " the cream", " the medicine"]
        is_follow_up = any(p in q_lower for p in pronoun_markers)
        if (not extracted_entities or not raw_desc) and is_follow_up and chat_history:
            for turn in reversed(chat_history):
                if turn.get("role") == "user":
                    prev_text = turn.get("content", "").lower()
                    if not raw_desc and any(marker in prev_text for marker in formulation_markers):
                        raw_desc = turn.get("content")
                    if not extracted_entities:
                        for marker in ["ashwagandha", "shallaki", "curcumin", "neem", "tulsi", "triphala", "brahmi", "guggulu", "panchagavya", "boswellia"]:
                            if marker in prev_text and marker.capitalize() not in extracted_entities:
                                extracted_entities.append(marker.capitalize())
                    if raw_desc and extracted_entities:
                        break

        jurisdiction = None
        if "us" in q_lower or "usa" in q_lower or "united states" in q_lower:
            jurisdiction = "United States"
        elif "eu" in q_lower or "europe" in q_lower:
            jurisdiction = "Europe"
        elif "india" in q_lower:
            jurisdiction = "india"

        return QueryUnderstanding(
            intent=intent,
            entities=extracted_entities,
            mentions_jurisdiction=jurisdiction,
            raw_product_description=raw_desc
        )
