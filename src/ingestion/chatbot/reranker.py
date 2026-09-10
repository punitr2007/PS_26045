"""
Legal RAG Re-ranking Module v2
================================
Improvements over v1:

1. Accepts an optional structured `query_context` dict (jurisdiction, legal_area,
   product_category) produced by the upstream jurisdiction router / classifier.
   This REPLACES keyword-regex inference whenever available — regex on raw user
   text is inherently lossy ("my product" tells you nothing; the classifier's
   output does). Falls back to keyword inference only when context is absent
   (e.g. ad-hoc queries, eval harness).
2. New exact-citation-match signal: if the query names a specific Act/Section/
   Rule (e.g. "Section 3(p)", "Rule 158B"), a chunk whose metadata matches that
   exact locator gets a hard boost. This is the single highest-precision signal
   available in a legal RAG and was previously not modeled at all.
3. Applicability now scores ALL matched legal areas, not just the first dict
   hit — a query mentioning both "patent" and "biological resource" no longer
   silently drops one area.
4. Fixed the "international" jurisdiction keyword bug (was ["germany","uk"],
   which is wrong and would never match an india/international split query).
5. Freshness recency nudge is now timezone-safe and won't throw on tz-aware
   effective_from values.
6. Authority parsing is defensive against malformed authority_level strings.
7. Optional lightweight MMR-style de-duplication pass so top-k isn't dominated
   by 5 near-identical chunks of the same section.
"""

import math
import re
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Optional, Any
from langchain_core.documents import Document
from loguru import logger


_AUTHORITY_MAX = 7

_JURISDICTION_KEYWORDS: Dict[str, List[str]] = {
    "india": ["india", "indian", "bharat", "central", "union of india"],
    "maharashtra": ["maharashtra", "mumbai", "bombay"],
    "delhi": ["delhi", "new delhi", "ncr"],
    "karnataka": ["karnataka", "bangalore", "bengaluru"],
    "international": [
        "international", "trips", "wipo", "pct", "madrid", "hague",
        "budapest", "nagoya", "cbd", "convention on biological diversity",
        "treaty", "export", "foreign jurisdiction",
    ],
}

_LEGAL_AREA_KEYWORDS: Dict[str, List[str]] = {
    "patent": ["patent", "invention", "patentable", "patentability", "novelty", "prior art", "claim"],
    "gi": ["geographical indication", "gi tag", "gi registry", "region-specific", "gi act"],
    "trademark": ["trademark", "trade mark", "brand", "mark", "logo", "passing off"],
    "copyright": ["copyright", "author", "artistic work", "literary work", "film", "music"],
    "design": ["industrial design", "design act", "aesthetic", "shape", "ornamentation"],
    "plant_variety": ["plant variety", "ppv&fr", "farmers rights", "breeder", "propagating material"],
    "abs_biodiversity": ["biological diversity", "abs", "benefit sharing", "biological resource", "nbca", "sbb"],
    "tk_prior_art": ["traditional knowledge", "tkdl", "prior art", "codified knowledge", "misappropriation"],
    "drug_regulatory": ["drug", "cosmetic act", "ayush", "pharmacopoeia", "phytopharmaceutical", "drug license"],
    "food_regulatory": ["fssai", "ayurveda-aahar", "food safety", "food standard"],
    "cosmetic_regulatory": ["cosmetic", "cosmetic rules", "cosmetic standard"],
    "advertising": ["advertisement", "drugs and magic remedies", "misleading claim", "advertising code"],
    "international_treaty": ["trips", "cbd", "nagoya", "wipo", "pct", "madrid protocol", "hague system", "budapest treaty"],
}

_CITATION_PATTERN = re.compile(
    r"\b(?:section|sec\.?|s\.|rule|article|art\.?)\s*(\d+[a-zA-Z]?(?:\([\w]+\))*)",
    re.IGNORECASE,
)

_PRODUCT_CATEGORY_LEGAL_AREAS: Dict[str, List[str]] = {
    "classical": ["tk_prior_art", "drug_regulatory"],
    "proprietary": ["drug_regulatory", "trademark"],
    "phytopharmaceutical": ["drug_regulatory", "patent"],
    "non_classical": ["drug_regulatory", "patent"],
    "ayurveda_aahar": ["food_regulatory"],
    "cosmetic": ["cosmetic_regulatory"],
}

_NAMED_INSTRUMENT_ALIASES: Dict[str, List[str]] = {
    "drugs and cosmetics act": ["drugs and cosmetics act", "d&c act"],
    "drugs and cosmetics rules": ["drugs and cosmetics rules", "d&c rules"],
    "new drugs and clinical trials": ["ndct", "new drugs and clinical trials"],
    "biological diversity act": ["biological diversity act", "bd act"],
    "patents act": ["patents act"],
    "trade marks act": ["trade marks act", "trademarks act"],
    "gi act": ["geographical indications", "gi act"],
    "ayush gcp": ["ayush gcp", "good clinical practice"],
}


class LegalReranker:
    """
    Re-ranks vector search results using a weighted combination of legal-domain
    signals, with an optional exact-citation override boost applied on top.

    Usage (preferred — pass structured context from your jurisdiction router /
    classifier so matching isn't dependent on regex over raw text):

        reranker = LegalReranker()
        reranked = reranker.rerank(
            query="Can I patent this ashwagandha formulation?",
            results=results_with_scores,
            query_context={
                "jurisdiction": "india",
                "legal_area": ["patent", "tk_prior_art"],
                "product_category": "phytopharmaceutical",
            },
        )
        top_chunks = reranked[:top_k]

    Usage (fallback — no upstream classification available):

        reranked = reranker.rerank(query="...", results=results_with_scores)
    """

    def __init__(
        self,
        weight_relevance: float = 0.35,
        weight_freshness: float = 0.15,
        weight_authority: float = 0.20,
        weight_jurisdiction: float = 0.10,
        weight_applicability: float = 0.15,
        weight_citation_match: float = 0.05,
        freshness_half_life_years: float = 5.0,
        citation_hard_boost: float = 0.25,
        named_instrument_boost: float = 0.10,
        enable_mmr_dedup: bool = True,
        mmr_similarity_threshold: float = 0.92,
    ):
        """
        Args:
            weight_*: Signal weights (auto-normalized if they don't sum to 1.0).
            freshness_half_life_years: Decay half-life for the recency nudge.
            citation_hard_boost: Flat additive bonus (post-normalization, before
                clip to 1.0) applied when the query's cited section/rule/article
                exactly matches a chunk's metadata locator. This is intentionally
                a hard boost rather than a weighted signal — an exact statutory
                citation match should be near-decisive, not diluted by averaging.
            named_instrument_boost: Smaller additive bonus when the query names
                a specific Act/Rules/Guideline (e.g. "Drugs and Cosmetics Rules")
                and the chunk comes from that exact instrument. Lower than the
                citation boost because it's instrument-level, not clause-level,
                precision.
            enable_mmr_dedup: If True, penalize chunks that are near-duplicates
                (same document_id + section) of an already-selected higher chunk,
                so top-k results aren't 4 copies of the same paragraph.
            mmr_similarity_threshold: Cosine-sim threshold above which two chunks
                are considered near-duplicates for the dedup pass (approximated
                via matching document_id + section/article metadata, not a second
                embedding comparison, to avoid extra vector math per call).
        """
        weights = dict(
            relevance=weight_relevance,
            freshness=weight_freshness,
            authority=weight_authority,
            jurisdiction=weight_jurisdiction,
            applicability=weight_applicability,
            citation_match=weight_citation_match,
        )
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f"LegalReranker: weights sum to {total:.2f}, normalizing.")
            weights = {k: v / total for k, v in weights.items()}

        self.w_relevance = weights["relevance"]
        self.w_freshness = weights["freshness"]
        self.w_authority = weights["authority"]
        self.w_jurisdiction = weights["jurisdiction"]
        self.w_applicability = weights["applicability"]
        self.w_citation_match = weights["citation_match"]

        self.freshness_half_life_years = freshness_half_life_years
        self.citation_hard_boost = citation_hard_boost
        self.named_instrument_boost = named_instrument_boost
        self.enable_mmr_dedup = enable_mmr_dedup
        self.mmr_similarity_threshold = mmr_similarity_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        results: List[Tuple[Document, float]],
        query_context: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float, Dict[str, float]]]:
        """
        Args:
            query: raw user query (used for keyword fallback + citation extraction).
            results: List of (Document, similarity_score) from vector search.
            query_context: optional structured output from the jurisdiction
                router / classifier, e.g.:
                    {"jurisdiction": "india", "legal_area": ["patent"],
                     "product_category": "phytopharmaceutical"}
                When provided, jurisdiction/applicability scoring uses this
                directly instead of regex-matching the raw query.

        Returns:
            List of (Document, composite_score, signal_scores), sorted descending.
        """
        query_lower = query.lower()
        cited_locators = self._extract_citations(query)
        named_instruments = self._extract_named_instruments(query_lower)

        # Derive extra legal-area candidates from product_category if the
        # caller passed one (from classify_engine.py output) without also
        # passing legal_area directly.
        effective_context = dict(query_context) if query_context else {}
        if not effective_context.get("legal_area") and effective_context.get("product_category"):
            cat = str(effective_context["product_category"]).lower().replace("-", "_").replace(" ", "_")
            inferred_areas = _PRODUCT_CATEGORY_LEGAL_AREAS.get(cat)
            if inferred_areas:
                effective_context["legal_area"] = inferred_areas

        scored = []
        for doc, raw_score in results:
            meta = doc.metadata

            s_relevance = self._score_relevance(raw_score)
            s_freshness = self._score_freshness(meta)
            s_authority = self._score_authority(meta)
            s_jurisdiction = self._score_jurisdiction(query_lower, meta, effective_context)
            s_applicability = self._score_applicability(query_lower, meta, effective_context)
            s_citation = self._score_citation_match(cited_locators, meta)
            s_named_instrument = self._score_named_instrument(named_instruments, meta)

            composite = (
                self.w_relevance * s_relevance
                + self.w_freshness * s_freshness
                + self.w_authority * s_authority
                + self.w_jurisdiction * s_jurisdiction
                + self.w_applicability * s_applicability
                + self.w_citation_match * s_citation
            )

            # Hard boosts, applied after the weighted sum: an exact statutory
            # citation match or a named-instrument match is close to decisive
            # evidence for a legal system and should not be diluted by
            # averaging against unrelated signals like raw cosine relevance.
            if s_citation >= 0.99:
                composite = min(1.0, composite + self.citation_hard_boost)
            elif s_named_instrument >= 0.99:
                composite = min(1.0, composite + self.named_instrument_boost)

            signal_scores = {
                "relevance": round(s_relevance, 4),
                "freshness": round(s_freshness, 4),
                "authority": round(s_authority, 4),
                "jurisdiction": round(s_jurisdiction, 4),
                "applicability": round(s_applicability, 4),
                "citation_match": round(s_citation, 4),
                "named_instrument_match": round(s_named_instrument, 4),
                "composite": round(composite, 4),
            }
            signal_scores["explanation"] = self._explain(signal_scores, meta)

            logger.debug(f"Chunk [{meta.get('chunk_id', '?')}] scores: {signal_scores}")
            scored.append((doc, composite, signal_scores))

        scored.sort(key=lambda x: x[1], reverse=True)

        if self.enable_mmr_dedup:
            scored = self._dedup_near_duplicates(scored)

        return scored

    # ------------------------------------------------------------------
    # Signal Scorers
    # ------------------------------------------------------------------

    def _score_relevance(self, raw_score: float) -> float:
        return max(0.0, min(1.0, float(raw_score)))

    def _score_freshness(self, meta: Dict[str, Any]) -> float:
        status = str(meta.get("status", "")).lower().strip()
        status_map = {
            "active": 1.0,
            "in_force": 1.0,
            "amended": 0.9,
            "not_yet_effective": 0.5,
            "superseded": 0.15,
            "repealed": 0.05,
        }
        base = status_map.get(status, 0.5)

        effective_from = meta.get("effective_from")
        if effective_from and base >= 0.9:
            try:
                eff_dt = datetime.fromisoformat(str(effective_from))
                now = datetime.now(eff_dt.tzinfo) if eff_dt.tzinfo else datetime.now()
                years_old = (now - eff_dt).days / 365.25
                recency_nudge = max(0.0, 1.0 - min(years_old, 30) / 60)
                base = min(1.0, base * 0.85 + recency_nudge * 0.15)
            except (ValueError, TypeError):
                pass

        return round(base, 4)

    def _score_authority(self, meta: Dict[str, Any]) -> float:
        level = meta.get("authority_level")
        if level is not None:
            try:
                level_num = int(re.sub(r"[^\d]", "", str(level)))
                return max(0.0, min(1.0, 1.0 - (level_num / _AUTHORITY_MAX)))
            except (ValueError, TypeError):
                pass

        doc_type = str(meta.get("document_type", "")).lower().strip()
        fallback_map = {
            "act": 1.0, "treaty": 1.0,
            "rule": 0.85, "notifications": 0.85, "amendment": 0.85,
            "official guidelines": 0.70,
            "policy": 0.60, "framework": 0.60,
            "procedure": 0.55,
            "plan": 0.40, "protocol": 0.40,
        }
        return fallback_map.get(doc_type, 0.10)

    def _score_jurisdiction(
        self, query_lower: str, meta: Dict[str, Any], query_context: Optional[Dict[str, Any]]
    ) -> float:
        doc_jurisdiction = str(meta.get("jurisdiction", "")).lower()

        # Prefer structured context over keyword inference.
        target_jurisdiction = None
        if query_context and query_context.get("jurisdiction"):
            target_jurisdiction = str(query_context["jurisdiction"]).lower()

        if not doc_jurisdiction or doc_jurisdiction in ("india", "central", "national"):
            base = 0.8  # central/national laws are broadly applicable
        else:
            base = 0.3  # default: regional/foreign law not matching context

        if target_jurisdiction:
            if doc_jurisdiction == target_jurisdiction:
                return 1.0
            if target_jurisdiction in ("india",) and doc_jurisdiction in ("india", "central", "national"):
                return 1.0
            if target_jurisdiction == "international" and doc_jurisdiction not in ("india", "central", "national"):
                return 1.0
            # Structured context says one jurisdiction, doc is a different one:
            # this is a stronger mismatch signal than the keyword fallback.
            if doc_jurisdiction not in ("india", "central", "national"):
                return 0.15
            return base

        # Fallback: keyword inference on raw query text.
        keywords = _JURISDICTION_KEYWORDS.get(doc_jurisdiction, [doc_jurisdiction])
        if any(kw in query_lower for kw in keywords):
            return 1.0
        return base

    def _score_applicability(
        self, query_lower: str, meta: Dict[str, Any], query_context: Optional[Dict[str, Any]]
    ) -> float:
        legal_area = str(meta.get("legal_area", "")).lower()

        # Prefer structured context (can be a list of areas from query decomposition).
        if query_context and query_context.get("legal_area"):
            ctx_areas = query_context["legal_area"]
            if isinstance(ctx_areas, str):
                ctx_areas = [ctx_areas]
            ctx_areas = [a.lower() for a in ctx_areas]

            if legal_area in ctx_areas:
                return 1.0
            if any(a in legal_area or legal_area in a for a in ctx_areas):
                return 0.8
            return 0.2

        # Fallback: keyword inference, now scanning ALL areas instead of the
        # first dict match, so multi-topic queries don't lose a signal.
        matched_areas = [
            area for area, keywords in _LEGAL_AREA_KEYWORDS.items()
            if any(kw in query_lower for kw in keywords)
        ]
        if not matched_areas:
            return 0.5

        if legal_area in matched_areas:
            return 1.0
        if any(a in legal_area or legal_area in a for a in matched_areas):
            return 0.8
        return 0.2

    def _score_citation_match(self, cited_locators: List[str], meta: Dict[str, Any]) -> float:
        """
        Returns 1.0 if the query explicitly cites a section/rule/article number
        that matches this chunk's section/article metadata field.
        """
        if not cited_locators:
            return 0.0

        doc_locator = str(meta.get("section") or meta.get("article") or "").lower()
        doc_locator = re.sub(r"[^\w()]", "", doc_locator)  # normalize "3 (p)" -> "3(p)"
        if not doc_locator:
            return 0.0

        for loc in cited_locators:
            norm = re.sub(r"[^\w()]", "", loc.lower())
            if norm and (norm == doc_locator or norm in doc_locator or doc_locator in norm):
                return 1.0
        return 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_citations(self, query: str) -> List[str]:
        return [m.group(1) for m in _CITATION_PATTERN.finditer(query)]

    def _extract_named_instruments(self, query_lower: str) -> List[str]:
        """Returns the alias-list keys whose trigger phrase appears in the query."""
        return [name for name in _NAMED_INSTRUMENT_ALIASES if name in query_lower]

    def _score_named_instrument(self, named_instruments: List[str], meta: Dict[str, Any]) -> float:
        if not named_instruments:
            return 0.0
        haystack = f"{meta.get('source_title', '')} {meta.get('document_id', '')}".lower()
        if not haystack.strip():
            return 0.0
        for name in named_instruments:
            if any(alias in haystack for alias in _NAMED_INSTRUMENT_ALIASES[name]):
                return 1.0
        return 0.0

    def _explain(self, signals: Dict[str, float], meta: Dict[str, Any]) -> str:
        """
        One-line, human-readable justification for why this chunk ranked where
        it did. Feeds the PRD's confidence/audit requirement (Section 24/30) —
        cheap to generate here, expensive to reconstruct later from raw scores.
        """
        reasons = []
        if signals["citation_match"] >= 0.99:
            reasons.append("exact section/rule citation match")
        if signals["named_instrument_match"] >= 0.99:
            reasons.append("named instrument match")
        if signals["authority"] >= 0.9:
            reasons.append("primary legislation/treaty authority")
        elif signals["authority"] <= 0.3:
            reasons.append("low source authority")
        if signals["freshness"] <= 0.2:
            reasons.append("superseded/repealed — historical context only")
        if signals["jurisdiction"] <= 0.2:
            reasons.append("jurisdiction mismatch")
        if signals["applicability"] <= 0.3:
            reasons.append("legal area likely mismatched")
        if not reasons:
            reasons.append("moderate relevance across all signals")
        return "; ".join(reasons)

    def _dedup_near_duplicates(
        self, scored: List[Tuple[Document, float, Dict[str, float]]]
    ) -> List[Tuple[Document, float, Dict[str, float]]]:
        """
        Cheap de-dup: if two chunks share the same (document_id, section/article),
        keep only the higher-scored one. Prevents top-k being flooded with
        near-identical chunks of the same provision at the cost of diversity.
        """
        seen = set()
        deduped = []
        for doc, score, signals in scored:
            key = (doc.metadata.get("document_id"), doc.metadata.get("section") or doc.metadata.get("article"))
            if key in seen and key[0] is not None:
                continue
            seen.add(key)
            deduped.append((doc, score, signals))
        logger.info(deduped)
        return deduped