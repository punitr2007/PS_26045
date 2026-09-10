"""
Formulation Audit endpoint.

Accepts formulation abstract, classification, synergy evidence description,
and ingredient list. Returns banded, statutorily-grounded verdicts for:

  1. Section 3(p) / TKDL bar  — classical knowledge exclusion
  2. Section 3(e) / synergy   — mere admixture bar
  3. NBA Form III / Section 6  — prior approval before patent sealing

Verdict bands are qualitative, NOT numeric percentages — percentages without a
documented calculation methodology undermine the source-cited credibility.

Key statutory fact hardcoded in the prompt (India domestic only):
NBA Form III approval must be obtained before the patent is SEALED (not before
filing). It is declared in Form 1 column 9(iii) of the patent application.
"""

import json
import re
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.models.schemas import AuditRequest, AuditResponse, SourceCitation

router = APIRouter()

AUDIT_PROMPT = """You are IP-SAKTI Sahayak — India's statutory legal advisor for Ayurvedic IP and ABS compliance.

Analyse the following Ayurvedic formulation for patent eligibility and biodiversity compliance under Indian law.
🇮🇳 INDIA DOMESTIC ANALYSIS ONLY — do not apply US FDA, EPO, or other international frameworks.

FORMULATION DETAILS:
- Abstract / Claim: {abstract}
- Legal Classification: {classification}
- Synergy / Comparative Evidence: {synergy}
- Botanical Ingredients: {ingredients}

Respond with ONLY this JSON (no prose outside the JSON braces):
{{
  "verdict": "<exactly one of: Likely Blocked | Borderline — Needs Evidence | Reasonably Viable>",
  "tkdl_band": "<one of: Likely Blocked | Borderline | Clear> — <reason citing Section 3(p) Patents Act 1970 and TKDL>",
  "s3e_band": "<one of: Likely Blocked | Borderline | Clear> — <reason citing Section 3(e) Patents Act 1970>",
  "nba_band": "<one of: Required | Conditional | Not Required> — <reason citing Section 6(1) Biological Diversity Act 2002; include: approval needed before patent SEALING not before filing; declare NBA approval application number in Form 1 column 9(iii) of the patent application>",
  "analysis": "<200-350 word markdown analysis with exact Acts, Sections, procedural rules>"
}}

Rules:
- Cite exact Acts, Sections, Rules for every finding.
- Do NOT fabricate section numbers or approval bodies.
- If information is insufficient to assess a dimension, say so explicitly.
- For classical formulations: check if TKDL records are likely and cite specific risk.
- For NBA: The correct sequence is — (1) file patent application; (2) obtain NBA Form III approval before sealing; (3) declare approval in Form 1 col 9(iii).
- ABS authority is the NATIONAL Biodiversity Authority (NBA) for IPR, NOT State Biodiversity Boards.

LEGAL CONTEXT FROM RETRIEVED SOURCES:
{context}
"""


async def _build_audit_context(abstract: str, ingredients: str, classification: str, synergy: str) -> tuple[str, list]:
    """
    Retrieves and reranks legal context across Patent, ABS, and Drug Regulation domains
    reusing the main Chat pipeline's RAG and reranker modules.
    Returns (context_string, raw_source_dicts).
    """
    sources = []
    context_blocks = []

    try:
        from app.schemas.pipeline import SubQuery, ProductClassification
        from app.schemas.enums import Jurisdiction, LegalArea, ProductCategory
        from app.retrieval.patent_rag import PatentRAG
        from app.retrieval.abs_rag import AbsRAG
        from app.retrieval.regulation_rag import RegulationRAG
        from app.retrieval.reranker import rerank_async

        # Determine parsed category for reranker applicability context
        cat_enum = ProductCategory.PROPRIETARY
        if "classical" in classification.lower() or "asu" in classification.lower():
            cat_enum = ProductCategory.CLASSICAL
        elif "ayurveda aahar" in classification.lower() or "food" in classification.lower():
            cat_enum = ProductCategory.AYURVEDA_AAHAR

        prod_class = ProductClassification(
            category=cat_enum,
            ingredients=[i.strip() for i in (ingredients or "").split(",") if i.strip()],
        )

        patent_query = f"Section 3(p) Section 3(e) traditional knowledge synergy comparative data {abstract[:150]}"
        abs_query = f"Section 6 Biological Diversity Act NBA Form III prior approval before patent sealing {ingredients}"
        reg_query = f"Drugs and Cosmetics Act Rule 158B Ayurvedic manufacturing license {classification}"

        sq_patent = SubQuery(legal_area=LegalArea.PATENT, query_text=patent_query, jurisdiction=Jurisdiction.INDIA)
        sq_abs = SubQuery(legal_area=LegalArea.ABS, query_text=abs_query, jurisdiction=Jurisdiction.INDIA)
        sq_reg = SubQuery(legal_area=LegalArea.DRUG_REGULATION, query_text=reg_query, jurisdiction=Jurisdiction.INDIA)

        # Batch retrieval across the 3 specialized domain stores
        patent_packs = await PatentRAG.retrieve_batch([sq_patent])
        abs_packs = await AbsRAG.retrieve_batch([sq_abs])
        reg_packs = await RegulationRAG.retrieve_batch([sq_reg])

        all_packs = patent_packs + abs_packs + reg_packs

        # Re-rank with the main LegalReranker engine
        state_ctx = {
            "query": f"{abstract} {ingredients} {synergy}",
            "classification": prod_class,
            "jurisdiction": Jurisdiction.INDIA
        }
        reranked_packs = await rerank_async(all_packs, state_ctx)

        seen_chunks = set()
        for pack in reranked_packs:
            for ev in pack.evidences:
                chunk = ev.chunk
                if chunk.chunk_id in seen_chunks:
                    continue
                seen_chunks.add(chunk.chunk_id)
                text_preview = chunk.text[:400] + ("..." if len(chunk.text) > 400 else "")
                context_blocks.append(f"[{chunk.provision} - {chunk.title}]\n{text_preview}")
                sources.append({
                    "id": chunk.chunk_id,
                    "provision": chunk.provision,
                    "title": chunk.title,
                    "chapter": chunk.chapter,
                    "pages": chunk.pages,
                })
                if len(sources) >= 6:
                    break
            if len(sources) >= 6:
                break
    except Exception as e:
        logger.warning(f"Audit multi-domain retrieval failed ({e}); proceeding with empty context.")

    return "\n\n---\n\n".join(context_blocks), sources


@router.post("", response_model=AuditResponse)
async def formulation_audit(request: AuditRequest):
    """
    Formulation Audit — banded, statute-grounded patent/ABS feasibility analysis.
    Returns qualitative verdicts (not numeric percentages) for Section 3(p)/TKDL,
    Section 3(e)/synergy, and NBA Form III/Section 6.
    India domestic analysis only.
    """
    try:
        context, raw_sources = await _build_audit_context(
            abstract=request.abstract,
            ingredients=request.ingredients or "",
            classification=request.classification,
            synergy=request.synergy_description or "",
        )

        prompt = AUDIT_PROMPT.format(
            abstract=request.abstract or "(not provided)",
            classification=request.classification,
            synergy=request.synergy_description or "No comparative synergy data described.",
            ingredients=request.ingredients or "(not specified)",
            context=context or "No retrieved context — analysis based on general statutory knowledge only.",
        )

        from app.llm.providers import get_llm
        from langchain_core.messages import HumanMessage
        llm = get_llm()
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw_text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON from LLM response (strip markdown fences if present)
        parsed = None
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except Exception as e:
                logger.warning(f"Audit JSON parse exception: {e}")

        source_citations = [SourceCitation(**s) for s in raw_sources]

        if parsed and isinstance(parsed, dict) and "verdict" in parsed:
            return AuditResponse(
                verdict=str(parsed.get("verdict", "Borderline — Needs Evidence")),
                tkdl_band=str(parsed.get("tkdl_band", "Assessment unavailable — see analysis below")),
                s3e_band=str(parsed.get("s3e_band", "Assessment unavailable — see analysis below")),
                nba_band=str(parsed.get("nba_band", "Assessment unavailable — see analysis below")),
                analysis=str(parsed.get("analysis", raw_text)),
                sources=source_citations,
            )
        else:
            # Defensive floor when LLM output is malformed or unparseable:
            # Never fabricate misleading precision bands like 'Borderline' or 'Likely Blocked'.
            logger.warning("Audit LLM returned non-JSON/malformed response. Using defensive floor.")
            return AuditResponse(
                verdict="Assessment Unavailable",
                tkdl_band="Assessment unavailable — see raw analysis below",
                s3e_band="Assessment unavailable — see raw analysis below",
                nba_band="Assessment unavailable — see raw analysis below",
                analysis=raw_text or "Formulation audit analysis could not be generated cleanly. Please verify inputs and retry.",
                sources=source_citations,
            )

    except Exception as e:
        logger.error(f"Formulation audit unexpected exception: {e}")
        source_citations = [SourceCitation(**s) for s in (raw_sources if 'raw_sources' in locals() else [])]
        return AuditResponse(
            verdict="Assessment Unavailable",
            tkdl_band="Assessment unavailable — see raw analysis below",
            s3e_band="Assessment unavailable — see raw analysis below",
            nba_band="Assessment unavailable — see raw analysis below",
            analysis=f"Audit analysis encountered a system error: {str(e)}",
            sources=source_citations,
        )


@router.get("/statute/{statute_id}")
async def get_statute(statute_id: str):
    """
    Live statute text endpoint (progressive enhancement).
    Frontend StatuteReader falls back to embedded static text when this returns 404.
    Stub until full bare-act text is ingested into Qdrant with statute_id metadata.
    """
    raise HTTPException(
        status_code=404,
        detail=f"Statute '{statute_id}' not yet served from backend. Frontend uses static fallback.",
    )
