from app.schemas.pipeline import (
    QueryUnderstanding, ProductClassification, QueryDecomposition, SubQuery,
)
from app.schemas.enums import LegalArea, Jurisdiction

def decompose(
    understanding: QueryUnderstanding,
    classification: ProductClassification,
    jurisdiction: Jurisdiction,
    query: str,
) -> QueryDecomposition:
    """
    Given the normalized query + product category, figure out which
    legal areas are actually relevant and generate a focused sub-query
    for each.

    Uses classification.hyde_context (a declarative regulatory product description)
    as the retrieval base text instead of the raw user query — this closes the
    semantic gap between colloquial user questions and formal statute chunk text.
    Falls back to raw query if hyde_context is absent.
    """
    # Area selection always uses raw query — preserves keyword heuristics
    # (e.g. detecting "patent", "section 3", "trademark" in user's own words)
    relevant_areas = _select_relevant_areas(classification, understanding, query)

    # Retrieval text: prefer declarative HyDE context, fall back to raw query
    retrieval_text = classification.hyde_context or query

    sub_queries = [
        SubQuery(
            legal_area=area,
            query_text=_reframe_for_area(retrieval_text, area),
            jurisdiction=jurisdiction,
            # Carry product_category so RAG pipelines can apply
            # applicable_product payload filter in Qdrant.
            product_category=classification.category.value if classification else None,
        )
        for area in relevant_areas
    ]

    return QueryDecomposition(
        sub_queries=sub_queries,
        product_classification=classification,
        jurisdiction=jurisdiction,
    )


_TRADITIONAL_HERB_KEYWORDS = {
    "turmeric", "haldi", "ginger", "adrak", "ashwagandha", "neem", "tulsi",
    "triphala", "brahmi", "amla", "shatavari", "giloy", "guduchi", "manjistha",
    "haritaki", "bibhitaki", "amalaki", "pippali", "chitrak", "vidanga",
    "ayurvedic", "ayurveda", "herbal", "traditional", "classical", "formulation"
}

def _select_relevant_areas(
    classification: ProductClassification, understanding: QueryUnderstanding, query: str
) -> list[LegalArea]:
    # Rule-based gating
    # Keys MUST match ProductCategory enum .value strings exactly (from pipeline.py):
    #   NON_CLASSICAL = "non-classical", AYURVEDA_AAHAR = "ayurveda-aahar"
    mapping = {
        "proprietary": [LegalArea.PATENT, LegalArea.TRADEMARK, LegalArea.DRUG_REGULATION, LegalArea.TK_PRIOR_ART],
        "classical": [LegalArea.TK_PRIOR_ART, LegalArea.ABS, LegalArea.GI, LegalArea.DRUG_REGULATION],
        "cosmetic": [LegalArea.TRADEMARK, LegalArea.DRUG_REGULATION],
        "non-classical": [LegalArea.PATENT, LegalArea.TRADEMARK, LegalArea.DRUG_REGULATION, LegalArea.ABS],
        "phytopharmaceutical": [LegalArea.PATENT, LegalArea.ABS, LegalArea.DRUG_REGULATION],
        "ayurveda-aahar": [LegalArea.TRADEMARK, LegalArea.DRUG_REGULATION, LegalArea.TK_PRIOR_ART, LegalArea.GI],
        "unclassified": list(LegalArea),  # broad search when category unknown
    }
    # Get the default based on category, fallback to all
    areas = list(mapping.get(classification.category.value, list(LegalArea)))

    # Simple heuristics to refine based on the query text (if the query specifically asks about something)
    q = query.lower()
    additional_areas = set()
    if "patent" in q or "invent" in q:
        additional_areas.add(LegalArea.PATENT)
    if "trademark" in q or "brand" in q or "logo" in q:
        additional_areas.add(LegalArea.TRADEMARK)
    if "biodiversity" in q or "nba" in q or "access" in q or "benefit" in q:
        additional_areas.add(LegalArea.ABS)
    if "prior art" in q or "traditional knowledge" in q or "tkdl" in q:
        additional_areas.add(LegalArea.TK_PRIOR_ART)

    # Ingredient-based heuristic: traditional Ayurvedic herbs always warrant TK/GI check
    # because Section 3(p) and GI protection are directly relevant to such formulations
    q_tokens = set(q.replace(",", " ").replace(".", " ").split())
    ingredients = [str(i).lower() for i in getattr(classification, "ingredients", []) or []]
    ingredient_str = " ".join(ingredients)
    all_text = q + " " + ingredient_str

    has_traditional_ingredient = any(herb in all_text for herb in _TRADITIONAL_HERB_KEYWORDS)
    if has_traditional_ingredient:
        additional_areas.add(LegalArea.TK_PRIOR_ART)
        additional_areas.add(LegalArea.GI)

    # Keyword heuristic: explicit Section 3 or 3(p) mention
    if "section 3" in q or "3(p)" in q or "3p" in q:
        additional_areas.add(LegalArea.TK_PRIOR_ART)
        additional_areas.add(LegalArea.PATENT)

    for area in additional_areas:
        if area not in areas:
            areas.append(area)

    # Always include the core regulatory aspect for any query just to be safe in this mock
    if LegalArea.DRUG_REGULATION not in areas and ("legal" in q or "law" in q or "rule" in q or "regulate" in q):
        areas.append(LegalArea.DRUG_REGULATION)

    return areas



def _reframe_for_area(query: str, area: LegalArea) -> str:
    # Heuristic query reframing based on the target legal area
    if area == LegalArea.PATENT:
        return f"{query} (focus on novelty, inventive step, non-patentability, what are not inventions, section 3 Patents Act)"
    elif area == LegalArea.ABS:
        return f"{query} (focus on access to biological resources, benefit sharing, National Biodiversity Authority)"
    elif area == LegalArea.TK_PRIOR_ART:
        return f"{query} (focus on traditional knowledge prior art, section 3(p) Patents Act, what are not inventions, not an invention within the meaning of this Act, traditional Ayurvedic knowledge, TKDL)"
    elif area == LegalArea.DRUG_REGULATION:
        return f"{query} (focus on Drugs and Cosmetics Act, licensing, labeling, clinical trials)"
    elif area == LegalArea.TRADEMARK:
        return f"{query} (focus on trademark registration, distinctiveness, deceptive similarity)"
    elif area == LegalArea.GI:
        return f"{query} (focus on Geographical Indications, origin, traditional practice)"
    return query
