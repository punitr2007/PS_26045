from typing import List, Dict, Any, Optional
from app.schemas.pipeline import ClarificationQuestion, AnswerRelevanceResult
from app.llm.providers import get_extraction_llm
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
import json

LOAD_BEARING_FIELD_METADATA = {
    "category": {
        "label": "Product Statutory Category",
        "description": "Whether the formulation is Classical (from ancient Ayurvedic texts), Proprietary, Phytopharmaceutical, Ayurveda Aahar (food), or Cosmetic.",
        "options": ["Classical Formulation (Ayurvedic Pharmacopoeia)", "Proprietary Medicine (Novel Combination)", "Standardized Phytopharmaceutical", "Ayurveda Aahar (Food / Dietary Supplement)", "Ayurvedic Cosmetic (Topical)"]
    },
    "jurisdiction": {
        "label": "Target Jurisdiction",
        "description": "Geographical region / legal regime under which protection or compliance is sought.",
        "options": ["India (Indian Patent Office / CDSCO / NBA)", "International (PCT / US / EPO / WIPO)"]
    },
    "route_of_administration": {
        "label": "Route of Administration",
        "description": "How the formulation is consumed or applied (oral, topical, external).",
        "options": ["Oral (Tablet / Capsule / Syrup / Powder / Kwatha)", "Topical / External (Oil / Lepa / Cream / Ointment)"]
    },
    "intended_use": {
        "label": "Intended Purpose",
        "description": "Whether the formulation is intended as therapeutic medicine, daily wellness/food, or cosmetic beautification.",
        "options": ["Therapeutic / Medicinal Treatment", "Dietary Supplement / Wellness Food", "Cosmetic / Skin & Hair Care"]
    }
}

CLARIFY_SYSTEM_PROMPT = """You are a regulatory and patent intake assistant for Ayurvedic and Traditional Knowledge intellectual property.
The user's query lacks essential regulatory facts needed to evaluate patentability, TKDL prior art, NBA biodiversity approval, or drug licensing.

Your task is to generate concise, objective clarifying questions ONLY for the specified missing fields:
{missing_fields_detail}

Known facts (DO NOT ask about these):
{known_facts_json}

Rules:
1. Generate strictly 1 question per missing field (maximum 3 questions total).
2. Provide clear, relevant multiple-choice options for each question.
3. Do NOT give legal advice or opinions in the questions.
4. Keep questions polite, professional, and targeted.
"""

RELEVANCE_SYSTEM_PROMPT = """You are an intent and slot-filling validator in an Ayurvedic Legal RAG system.
The user was previously asked clarifying questions to fill missing statutory fields.

Pending Questions Asked to User:
{pending_questions_json}

User's Latest Reply:
"{user_reply}"

Analyze the user's reply:
1. 'is_relevant': True if the user provides information answering any of the pending questions or clarifies product details.
2. 'extracted_facts': Extract any key-value pairs matching slots like 'jurisdiction', 'category', 'route_of_administration', 'intended_use', 'dosage_form', 'ingredients'.
3. 'is_new_topic': True if the user completely ignores the pending questions and pivots to an entirely different, unrelated subject (e.g. asking about unrelated taxes, general code, or a completely different topic).
4. 'reasoning': Brief one-line rationale.
"""

def generate_clarification_questions(missing_fields: Any, known_facts: Optional[Dict[str, Any]] = None) -> List[ClarificationQuestion]:
    """
    Generates structured, constrained clarification questions for load-bearing missing fields.
    Accepts either a list of missing field strings or a ProductClassification object directly.
    """
    if hasattr(missing_fields, "missing_facts"):
        missing_fields = missing_fields.missing_facts
    elif isinstance(missing_fields, dict):
        missing_fields = missing_fields.get("missing_facts", [])
    elif not isinstance(missing_fields, (list, set, tuple)):
        missing_fields = []

    if not missing_fields:
        return []

    # Filter to known load-bearing fields
    valid_missing = [f for f in missing_fields if f in LOAD_BEARING_FIELD_METADATA]
    if not valid_missing:
        # If no recognized metadata, build fallback questions
        return [
            ClarificationQuestion(
                field=f,
                question=f"Could you please specify details regarding the {f.replace('_', ' ')}?",
                options=None
            )
            for f in missing_fields[:2]
        ]

    # Fast deterministic generation using metadata catalog if standard
    questions = []
    for field in valid_missing[:3]:
        meta = LOAD_BEARING_FIELD_METADATA[field]
        if field == "category":
            q_text = "Is this product based on a classical formulation from the Ayurvedic Pharmacopoeia (TKDL), or is it a novel proprietary formulation?"
        elif field == "jurisdiction":
            q_text = "Which jurisdiction/legal regime are you seeking protection or regulatory compliance under?"
        elif field == "route_of_administration":
            q_text = "What is the intended route of administration for this product?"
        elif field == "intended_use":
            q_text = "Is this product intended for therapeutic medicine, wellness/dietary food (Ayurveda Aahar), or cosmetic use?"
        else:
            q_text = f"Please specify the {meta['label']}."

        questions.append(ClarificationQuestion(
            field=field,
            question=q_text,
            options=meta["options"]
        ))

    return questions


def detect_answer_relevance(user_reply: str, pending_questions: List[Dict[str, Any]]) -> AnswerRelevanceResult:
    """
    Checks whether the user's follow-up message answers pending clarifying questions
    or represents domain drift / topic switch.
    """
    if not pending_questions:
        return AnswerRelevanceResult(is_relevant=True, extracted_facts={}, is_new_topic=False)

    reply_lower = user_reply.strip().lower()

    # Rule-based heuristics for fast classification
    extracted = {}
    
    # 1. Jurisdiction detection
    if "india" in reply_lower or "bharat" in reply_lower or "indian" in reply_lower:
        extracted["jurisdiction"] = "india"
    elif "us" in reply_lower or "usa" in reply_lower or "international" in reply_lower or "pct" in reply_lower or "wipo" in reply_lower or "europe" in reply_lower:
        extracted["jurisdiction"] = "international"

    # 2. Route of administration detection
    if "oral" in reply_lower or "tablet" in reply_lower or "capsule" in reply_lower or "syrup" in reply_lower or "drink" in reply_lower:
        extracted["route_of_administration"] = "oral"
    elif "topical" in reply_lower or "external" in reply_lower or "oil" in reply_lower or "cream" in reply_lower or "lepa" in reply_lower:
        extracted["route_of_administration"] = "external"

    # 3. Category detection
    if "classical" in reply_lower or "pharmacopoeia" in reply_lower or "samhita" in reply_lower or "text" in reply_lower:
        extracted["category"] = "classical"
    elif "proprietary" in reply_lower or "novel" in reply_lower or "own formulation" in reply_lower:
        extracted["category"] = "proprietary"
    elif "phytopharmaceutical" in reply_lower or "standardized extract" in reply_lower:
        extracted["category"] = "phytopharmaceutical"
    elif "food" in reply_lower or "aahar" in reply_lower or "supplement" in reply_lower or "fssai" in reply_lower:
        extracted["category"] = "ayurveda-aahar"
    elif "cosmetic" in reply_lower or "beauty" in reply_lower or "skin" in reply_lower:
        extracted["category"] = "cosmetic"

    # 4. Intended use detection
    if "therapeutic" in reply_lower or "medicine" in reply_lower or "disease" in reply_lower or "cure" in reply_lower or "treatment" in reply_lower:
        extracted["intended_use"] = "medicine"
    elif "wellness" in reply_lower or "supplement" in reply_lower or "diet" in reply_lower or "nutrition" in reply_lower or "food" in reply_lower or "aahar" in reply_lower:
        extracted["intended_use"] = "wellness"
    elif "cosmetic" in reply_lower or "skin" in reply_lower or "hair" in reply_lower or "beauty" in reply_lower:
        extracted["intended_use"] = "cosmetic"

    # If heuristics extracted slot values, it is relevant!
    if extracted:
        return AnswerRelevanceResult(
            is_relevant=True,
            extracted_facts=extracted,
            is_new_topic=False,
            reasoning="Heuristically matched slot answers in user reply."
        )

    # Use LLM with structured output to parse more complex responses
    try:
        llm = get_extraction_llm(temperature=0.0)
        structured_llm = llm.with_structured_output(AnswerRelevanceResult)
        
        prompt = RELEVANCE_SYSTEM_PROMPT.format(
            pending_questions_json=json.dumps(pending_questions, indent=2),
            user_reply=user_reply
        )
        result = structured_llm.invoke(prompt)
        return result
    except Exception as e:
        logger.warning(f"Relevance detection LLM failed: {e}. Falling back to treating as relevant input.")
        return AnswerRelevanceResult(
            is_relevant=True,
            extracted_facts=extracted,
            is_new_topic=False,
            reasoning="Fallback accepted."
        )
