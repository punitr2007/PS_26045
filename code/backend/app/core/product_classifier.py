from typing import Optional, Dict, Any, List
from app.schemas.pipeline import QueryUnderstanding, ProductClassification
from app.schemas.enums import Jurisdiction, ProductCategory
from app.llm.providers import get_extraction_llm
from app.llm.prompts import CLASSIFICATION_EXTRACTION_PROMPT, HYDE_CONTEXT_PROMPT
from loguru import logger

def _parse_category(cat_val: Any) -> ProductCategory:
    if isinstance(cat_val, ProductCategory):
        return cat_val
    if not cat_val:
        return ProductCategory.UNCLASSIFIED
    val_str = str(cat_val).lower().replace("_", "-").strip()
    for cat in ProductCategory:
        if cat.value == val_str:
            return cat
    return ProductCategory.UNCLASSIFIED

BOTANICAL_LEXICON = {
    "ashwagandha": "Ashwagandha (Withania somnifera)",
    "withania": "Ashwagandha (Withania somnifera)",
    "shallaki": "Shallaki (Boswellia serrata)",
    "boswellia": "Shallaki (Boswellia serrata)",
    "curcumin": "Curcumin / Haridra (Curcuma longa)",
    "turmeric": "Curcumin / Haridra (Curcuma longa)",
    "haridra": "Curcumin / Haridra (Curcuma longa)",
    "neem": "Neem (Azadirachta indica)",
    "tulsi": "Tulsi (Ocimum sanctum)",
    "triphala": "Triphala",
    "brahmi": "Brahmi (Bacopa monnieri)",
    "guggulu": "Guggulu (Commiphora mukul)",
    "guggul": "Guggulu (Commiphora mukul)",
    "shatavari": "Shatavari (Asparagus racemosus)",
    "amla": "Amla (Phyllanthus emblica)",
    "pippali": "Pippali (Piper longum)",
    "haritaki": "Haritaki (Terminalia chebula)",
    "yashtimadhu": "Yashtimadhu (Glycyrrhiza glabra)",
    "licorice": "Yashtimadhu (Glycyrrhiza glabra)",
    "panchagavya": "Panchagavya",
    "shunthi": "Shunthi (Zingiber officinale)",
    "ginger": "Shunthi (Zingiber officinale)",
}

def classify(
    understanding: QueryUnderstanding, 
    jurisdiction: Optional[Jurisdiction] = None,
    known_facts: Optional[Dict[str, Any]] = None,
    existing_classification: Optional[ProductClassification] = None
) -> ProductClassification:
    """
    Classifies the product, prioritizing known_facts (e.g. from UI panel),
    applying deterministic heuristics, decoupling ingredient extraction,
    and calculating genuinely load-bearing missing facts.
    """
    facts = dict(known_facts or {})
    
    # 1. Base initialization from existing classification or blank
    if existing_classification:
        classification = existing_classification.model_copy(deep=True)
    else:
        classification = ProductClassification(
            ingredients=[],
            category=ProductCategory.UNCLASSIFIED,
            confidence=0.5,
            reasoning="Initial classification.",
            missing_facts=[]
        )

    # 2. Fast deterministic heuristics from raw query / product description
    desc_lower = (understanding.raw_product_description or "").lower() if understanding else ""
    entities_lower = [e.lower() for e in (understanding.entities if understanding else [])]
    combined_text = f"{desc_lower} {' '.join(entities_lower)}"

    if desc_lower or entities_lower:
        # Category classification
        if any(w in desc_lower for w in ["classical", "pharmacopoeia", "samhita", "taila", "ghrita", "asava", "arishta", "churna", "vati", "bhasma", "kwatha", "avaleha", "guggulu", "lepa"]):
            classification.category = ProductCategory.CLASSICAL
            classification.confidence = 0.9
            classification.reasoning = "Formulation identified as Classical Ayurvedic preparation."
        elif any(w in desc_lower for w in ["proprietary", "p&p", "patent or proprietary", "novel formulation", "synergy", "shallaki"]):
            classification.category = ProductCategory.PROPRIETARY
            classification.confidence = 0.85
            classification.reasoning = "Formulation identified as Patent or Proprietary (P&P) Ayurvedic medicine."
        elif any(w in desc_lower for w in ["phytopharmaceutical", "standardized extract", "purified fraction"]):
            classification.category = ProductCategory.PHYTOPHARMACEUTICAL
            classification.confidence = 0.9
            classification.reasoning = "Formulation identified as Standardized Phytopharmaceutical."
        elif any(w in desc_lower for w in ["ayurveda aahar", "aahar", "dietary supplement", "food", "nutraceutical"]):
            classification.category = ProductCategory.AYURVEDA_AAHAR
            classification.confidence = 0.85
            classification.reasoning = "Formulation identified as Ayurveda Aahar / Dietary Supplement."
        elif any(w in desc_lower for w in ["cosmetic", "face wash", "lotion", "soap", "beauty", "skin care", "hair care"]):
            classification.category = ProductCategory.COSMETIC
            classification.confidence = 0.85
            classification.reasoning = "Formulation identified as Ayurvedic Cosmetic."

        # Route of administration
        if any(w in desc_lower for w in ["oral", "tablet", "capsule", "syrup", "powder", "kwatha", "vati", "drink", "ingest"]):
            classification.route_of_administration = "oral"
        elif any(w in desc_lower for w in ["topical", "external", "oil", "taila", "lepa", "cream", "ointment", "gel"]):
            classification.route_of_administration = "external"

        # Intended use
        if any(w in desc_lower for w in ["therapeutic", "medicine", "cure", "treatment", "disease", "pain"]):
            classification.intended_use = "medicine"
        elif any(w in desc_lower for w in ["wellness", "supplement", "food", "nutrition", "diet"]):
            classification.intended_use = "wellness"
        elif any(w in desc_lower for w in ["cosmetic", "beauty", "skin", "hair"]):
            classification.intended_use = "cosmetic"

        # Botanical / Ingredient extraction (runs on combined text)
        matched_ingredients = []
        for key, bot_name in BOTANICAL_LEXICON.items():
            if key in combined_text and bot_name not in matched_ingredients:
                matched_ingredients.append(bot_name)
        if matched_ingredients:
            classification.ingredients = list(set(classification.ingredients + matched_ingredients))

    # 3. Extract from raw description via LLM if category remains unclassified OR ingredients are missing
    if (
        understanding
        and understanding.raw_product_description
        and (classification.category == ProductCategory.UNCLASSIFIED or len(classification.ingredients) == 0)
    ):
        try:
            llm = get_extraction_llm(temperature=0.0, max_tokens=1024)
            structured_llm = llm.with_structured_output(ProductClassification)
            prompt = CLASSIFICATION_EXTRACTION_PROMPT.format(description=understanding.raw_product_description)
            extracted = structured_llm.invoke(prompt)
            
            # Merge extracted values into classification without clobbering heuristic certainty
            if classification.category == ProductCategory.UNCLASSIFIED and extracted.category != ProductCategory.UNCLASSIFIED:
                classification.category = extracted.category
                classification.confidence = extracted.confidence
            if classification.route_of_administration == "unknown" and extracted.route_of_administration != "unknown":
                classification.route_of_administration = extracted.route_of_administration
            if classification.intended_use == "unknown" and extracted.intended_use != "unknown":
                classification.intended_use = extracted.intended_use
            if extracted.ingredients:
                classification.ingredients = list(set(classification.ingredients + extracted.ingredients))
            if not classification.dosage_form and extracted.dosage_form:
                classification.dosage_form = extracted.dosage_form
            if extracted.reasoning and classification.reasoning == "Initial classification.":
                classification.reasoning = extracted.reasoning
        except Exception as e:
            logger.warning(f"LLM classification extraction failed: {e}. Relying on known facts and defaults.")

    # Generate HyDE context: a declarative regulatory-style product description
    # used as the retrieval base text instead of the raw user query.
    # Only fires when:
    #   - A meaningful product description exists (> 20 chars)
    #   - Classification genuinely succeeded (category resolved + confidence >= 0.65)
    # This prevents wasting an LLM call when classification failed (e.g., 503 error)
    # and the classifier fell back to defaults (confidence=0.5, category=UNCLASSIFIED).
    _desc = (understanding.raw_product_description or "").strip() if understanding else ""
    _hyde_eligible = (
        bool(_desc)
        and len(_desc) > 20
        and classification.category != ProductCategory.UNCLASSIFIED
        and classification.confidence >= 0.65
    )
    if _hyde_eligible:
        try:
            hyde_llm = get_extraction_llm(temperature=0.2)
            from app.config import settings
            provider = (settings.extraction_provider or settings.llm_provider or "gemini").lower()
            token_kwarg = "max_output_tokens" if provider == "gemini" else "max_tokens"
            bounded_llm = hyde_llm.bind(**{token_kwarg: 200})
            prompt = HYDE_CONTEXT_PROMPT.format(
                description=understanding.raw_product_description
            )
            result = bounded_llm.invoke(prompt)
            raw_content = result.content

            hyde_text = ""
            if hasattr(result, "text") and isinstance(result.text, str):
                hyde_text = result.text.strip()
            if not hyde_text:
                if isinstance(raw_content, list):
                    hyde_text = " ".join(
                        part.get("text", "")
                        for part in raw_content
                        if isinstance(part, dict) and part.get("type") == "text"
                    ).strip()
                    if not hyde_text:
                        hyde_text = " ".join(
                            part.get("text", "") or part.get("thinking", "")
                            if isinstance(part, dict) else str(part)
                            for part in raw_content
                        ).strip()
                else:
                    hyde_text = str(raw_content).strip()

            if not hyde_text:
                classification.hyde_context = None
            else:
                classification.hyde_context = hyde_text
        except Exception as e:
            logger.warning(f"HyDE context generation failed: {e}. Falling back to raw query for retrieval.")
            classification.hyde_context = None

    # 4. Apply known_facts (Ground Truth from panel or user clarification) - overrides extraction
    if "category" in facts:
        classification.category = _parse_category(facts["category"])
    if "route_of_administration" in facts:
        route_val = str(facts["route_of_administration"]).lower().strip()
        if route_val in ("oral", "external", "parenteral"):
            classification.route_of_administration = route_val
    if "intended_use" in facts:
        use_val = str(facts["intended_use"]).lower().strip()
        if use_val in ("medicine", "food", "cosmetic", "wellness"):
            classification.intended_use = use_val
    if "dosage_form" in facts:
        classification.dosage_form = str(facts["dosage_form"])

    # 5. Compute genuinely load-bearing missing_facts
    missing = []
    has_product = bool(understanding and understanding.raw_product_description)

    # Category is ONLY missing if there was a product description to classify in the first place
    if classification.category == ProductCategory.UNCLASSIFIED and "category" not in facts and has_product:
        missing.append("category")

    # Route of administration is load-bearing for regulatory compliance queries on PROPRIETARY formulations
    # where D&C Act Rule 158B vs FSSAI vs Cosmetics depends on route and purpose
    intent_val = getattr(understanding, "intent", "other") if understanding else "other"
    if (
        classification.category == ProductCategory.PROPRIETARY
        and intent_val == "compliance"
        and classification.route_of_administration == "unknown"
        and "route_of_administration" not in facts
        and has_product
    ):
        missing.append("route_of_administration")

    classification.missing_facts = missing
    return classification
