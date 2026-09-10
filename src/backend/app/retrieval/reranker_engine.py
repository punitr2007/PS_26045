import math
import re
import asyncio
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Optional, Any
from langchain_core.documents import Document
from loguru import logger
from app.config import settings
from app.llm.providers import get_cross_encoder



_AUTHORITY_MAX = 7

_JURISDICTION_KEYWORDS: Dict[str, List[str]] = {
    "india": ["india", "indian", "bharat", "central", "union of india"],
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
    def __init__(
        self,
        weight_relevance: float = 0.60,
        weight_freshness: float = 0.05,
        weight_authority: float = 0.15,
        weight_jurisdiction: float = 0.05,
        weight_applicability: float = 0.10,
        weight_citation_match: float = 0.05,
        freshness_half_life_years: float = 5.0,
        citation_hard_boost: float = 0.25,
        named_instrument_boost: float = 0.10,
        enable_mmr_dedup: bool = False,
        mmr_similarity_threshold: float = 0.92,
        # When a chunk's legal_area is a confirmed mismatch with the query context
        # (applicability_score == 0.2), multiply the composite by this factor.
        # 0.35 means the chunk is cut to 35% of its score — well below any
        # correctly-matched chunk, regardless of how high its vector similarity was.
        applicability_mismatch_penalty: float = 0.35,
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
        self.applicability_mismatch_penalty = applicability_mismatch_penalty
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

            # Hard PENALTY: confirmed legal-area mismatch.
            # applicability_score == 0.2 means the chunk's legal_area is neither
            # the queried area nor a substring match. With w_applicability=0.10,
            # the weighted signal only costs ~0.08 — not enough to suppress a
            # high-cosine wrong-area chunk. Multiply the whole score down instead.
            if s_applicability <= 0.2 and query_context and query_context.get("legal_area"):
                composite = composite * self.applicability_mismatch_penalty
                logger.debug(f"Chunk [{meta.get('chunk_id', '?')}] PENALIZED (area mismatch): composite→{composite:.4f}")

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

    def rerank_pack(
        self,
        query: str,
        chunks: List[Any],
        target_jurisdiction: Optional[Any] = None,
        legal_area: Optional[Any] = None
    ) -> List[Any]:
        """
        Convenience helper to directly rerank a list of RetrievedChunk or RankedEvidence objects.
        Returns a list of RankedEvidence objects sorted by descending final_score.
        """
        from app.schemas.pipeline import RankedEvidence, RetrievedChunk
        
        documents = []
        chunk_map = {}
        for c in chunks:
            actual_chunk = c.chunk if hasattr(c, "chunk") else c
            chunk_id = getattr(actual_chunk, "chunk_id", str(id(actual_chunk)))
            chunk_map[chunk_id] = actual_chunk
            
            jur_val = actual_chunk.jurisdiction.value if hasattr(getattr(actual_chunk, "jurisdiction", None), "value") else str(getattr(actual_chunk, "jurisdiction", "india"))
            meta = {
                "chunk_id": chunk_id,
                "section": getattr(actual_chunk, "provision", ""),
                "article": getattr(actual_chunk, "provision", ""),
                "source_title": getattr(actual_chunk, "title", ""),
                "document_id": getattr(actual_chunk, "title", ""),
                "jurisdiction": jur_val,
                "authority_level": getattr(actual_chunk, "authority_level", None) if getattr(actual_chunk, "authority_level", None) is not None else getattr(actual_chunk, "source_authority", "Act"),
                "document_type": getattr(actual_chunk, "document_type", None),
                "status": "active"
            }
            if legal_area:
                meta["legal_area"] = legal_area.value if hasattr(legal_area, "value") else str(legal_area)
                
            doc = Document(page_content=getattr(actual_chunk, "text", ""), metadata=meta)
            raw_score = getattr(actual_chunk, "vector_score", 0.5) or 0.5
            documents.append((doc, raw_score))

        q_context = {}
        if target_jurisdiction:
            q_context["jurisdiction"] = target_jurisdiction.value if hasattr(target_jurisdiction, "value") else str(target_jurisdiction)
        if legal_area:
            q_context["legal_area"] = [legal_area.value if hasattr(legal_area, "value") else str(legal_area)]
            
        scored = self.rerank(query, documents, q_context)
        
        ranked_evidences = []
        for doc, final_score, signals in scored:
            cid = doc.metadata.get("chunk_id")
            orig_chunk = chunk_map.get(cid)
            ranked_evidences.append(RankedEvidence(
                chunk=orig_chunk,
                relevance_score=signals.get("relevance", 0.5),
                authority_score=signals.get("authority", 0.5),
                jurisdiction_score=signals.get("jurisdiction", 0.5),
                freshness_score=signals.get("freshness", 0.5),
                applicability_score=signals.get("applicability", 0.5),
                final_score=final_score
            ))
        return ranked_evidences

    async def rerank_async(
        self,
        query: str,
        results: List[Tuple[Document, float]],
        query_context: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float, Dict[str, float]]]:
        """
        Asynchronous reranking with optional Neural Cross-Encoder support.
        Runs rule-based scoring first, then asynchronously blends neural cross-encoder
        relevance scores on the pruned candidate set using asyncio.to_thread.
        """
        # Step 1: Run fast rule-based baseline scoring
        initial_scored = self.rerank(query, results, query_context)
        
        if not settings.use_neural_reranker or not initial_scored:
            return initial_scored

        cross_encoder = get_cross_encoder()
        if not cross_encoder:
            return initial_scored

        # Step 2: Prune to top 15 candidates for neural inference
        top_candidates = initial_scored[:15]
        remaining_candidates = initial_scored[15:]
        
        pairs = [[query, doc.page_content] for doc, _, _ in top_candidates]
        
        try:
            # Step 3: Run cross-encoder inference non-blockingly
            logits = await asyncio.to_thread(cross_encoder.predict, pairs)
            
            re_scored = []
            for (doc, _, signals), logit in zip(top_candidates, logits):
                # Sigmoid normalization for raw logit
                s_neural = 1.0 / (1.0 + math.exp(-float(logit)))
                
                # Blend with vector score (60% neural cross-encoder, 40% calibrated vector score)
                s_vec = signals.get("relevance", 0.5)
                s_blended_relevance = 0.60 * s_neural + 0.40 * s_vec
                
                s_freshness = signals.get("freshness", 0.5)
                s_authority = signals.get("authority", 0.5)
                s_jurisdiction = signals.get("jurisdiction", 0.5)
                s_applicability = signals.get("applicability", 0.5)
                s_citation = signals.get("citation_match", 0.0)
                s_named_instrument = signals.get("named_instrument_match", 0.0)

                composite = (
                    self.w_relevance * s_blended_relevance
                    + self.w_freshness * s_freshness
                    + self.w_authority * s_authority
                    + self.w_jurisdiction * s_jurisdiction
                    + self.w_applicability * s_applicability
                    + self.w_citation_match * s_citation
                )

                # Hard boosts & overrides
                if s_citation >= 0.99:
                    composite = min(1.0, composite + self.citation_hard_boost)
                elif s_named_instrument >= 0.99:
                    composite = min(1.0, composite + self.named_instrument_boost)

                # Hard PENALTY: confirmed legal-area mismatch (same as sync path)
                if s_applicability <= 0.2 and query_context and query_context.get("legal_area"):
                    composite = composite * self.applicability_mismatch_penalty
                    logger.debug(f"Neural path: chunk PENALIZED (area mismatch): composite→{composite:.4f}")

                signals["relevance"] = round(s_blended_relevance, 4)
                signals["neural_score"] = round(s_neural, 4)
                signals["composite"] = round(composite, 4)
                signals["explanation"] = self._explain(signals, doc.metadata)

                re_scored.append((doc, composite, signals))

            all_scored = re_scored + remaining_candidates
            all_scored.sort(key=lambda x: x[1], reverse=True)

            if self.enable_mmr_dedup:
                all_scored = self._dedup_near_duplicates(all_scored)

            return all_scored

        except Exception as e:
            logger.warning(f"Neural reranker inference failed: {e}. Using rule-based ranking.")
            return initial_scored

    # ------------------------------------------------------------------
    # Signal Scorers
    # ------------------------------------------------------------------

    def _score_relevance(self, raw_score: float) -> float:
    
        center = 0.55
        steepness = 16.0
        stretched = 1.0 / (1.0 + math.exp(-steepness * (float(raw_score) - center)))
        return round(max(0.0, min(1.0, stretched)), 4)


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
        logger.info(f" Authority Level: {level} : {meta}")
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
                base = 1.0
            elif any(a in legal_area or legal_area in a for a in ctx_areas):
                base = 0.8
            else:
                base = 0.2
        else:
            # Fallback: keyword inference, now scanning ALL areas instead of the
            # first dict match, so multi-topic queries don't lose a signal.
            matched_areas = [
                area for area, keywords in _LEGAL_AREA_KEYWORDS.items()
                if any(kw in query_lower for kw in keywords)
            ]
            if not matched_areas:
                base = 0.5
            elif legal_area in matched_areas:
                base = 1.0
            elif any(a in legal_area or legal_area in a for a in matched_areas):
                base = 0.8
            else:
                base = 0.2

        # ---------------------------------------------------------------
        # Soft bonus/penalty from applicable_product metadata field.
        # The field may be "all", "classical", or "classical;proprietary".
        # This is a small nudge — it must not override the legal_area signal.
        # ---------------------------------------------------------------
        product_category = (query_context or {}).get("product_category")
        if product_category:
            applicable = str(meta.get("applicable_product", "all")).lower().strip()
            # Split on common delimiters used in the CSV / Qdrant payload
            tokens = {t.strip().replace("-", "_") for t in applicable.replace(";", ",").split(",")}
            norm_cat = str(product_category).lower().replace("-", "_").replace(" ", "_")

            if "all" in tokens:
                pass  # neutral — no adjustment
            elif norm_cat in tokens:
                base = min(1.0, base + 0.10)  # soft boost: chunk explicitly covers this category
            elif tokens and "all" not in tokens:
                base = max(0.0, base - 0.10)  # soft penalty: chunk is for specific other categories

        return round(base, 4)

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
        seen_chunk_ids = set()
        seen_texts = []
        deduped = []
        for doc, score, signals in scored:
            cid = doc.metadata.get("chunk_id")
            if cid and cid in seen_chunk_ids:
                continue

            doc_text = doc.page_content.strip().lower()
            if not doc_text:
                continue

            # Check if this exact text has already been seen (copy-paste duplicate)
            is_dup = False
            for seen_text in seen_texts:
                if doc_text == seen_text or (len(doc_text) > 80 and (doc_text in seen_text or seen_text in doc_text)):
                    is_dup = True
                    break
            if is_dup:
                continue

            if cid:
                seen_chunk_ids.add(cid)
            seen_texts.append(doc_text)
            deduped.append((doc, score, signals))

        logger.debug(f"Deduped near duplicates: {len(scored)} -> {len(deduped)} candidates")
        return deduped