import re
import unicodedata
from typing import Optional, Tuple, List
from loguru import logger

from .models import SectionCandidate, LegalCandidate


# Confidence thresholds
_ACCEPT_THRESHOLD = 0.90   # auto-accepted
_REVIEW_THRESHOLD = 0.70   # secondary validation; accepted unless other flags fail
# < 0.70 → rejected (unless REPEALED/OMITTED)


def _normalize_for_integrity(text: str) -> str:
    """
    Whitespace-only normalization for source integrity checks.
    Must NEVER remove legally meaningful content.
    """
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r'\s+', ' ', text).strip()


class ContextValidator:
    """
    Validates structural candidates.

    Two public APIs:

    ``validate_candidate(candidate: LegalCandidate, raw_text: str)``
        New generic API for LegalCandidate objects.
        Enforces confidence thresholds and source integrity checks.

    ``validate_and_clean(candidate: SectionCandidate, raw_text: str)``
        Legacy API — unchanged from original implementation.
        Used by existing pipeline.py code path.
    """

    REPEALED_PATTERN = re.compile(r'\b(omit|omitted|repeal|repealed|deleted)\b', re.IGNORECASE)

    # ==================================================================
    # NEW GENERIC API
    # ==================================================================

    def validate_candidate(
        self,
        candidate: LegalCandidate,
        raw_text: str,
        source_id: str = "UNKNOWN",
    ) -> Optional[LegalCandidate]:
        """
        Validates a ``LegalCandidate`` against the source text.

        Checks:
          1. Confidence threshold:
             >= 0.90 → accepted
             0.70–0.90 → secondary validation (check content length)
             <  0.70 → rejected (unless REPEALED pattern present)
          2. Source integrity: normalized chunk must appear in normalized source.
          3. Minimum content length.

        Returns the candidate unchanged if valid, or ``None`` if rejected.
        Logs failures with source_id, node_type, number, and char offsets.
        """
        chunk = raw_text[candidate.start_char_idx:candidate.end_char_idx].strip()

        # --- Confidence gate ---
        if candidate.confidence < _REVIEW_THRESHOLD:
            is_repealed = (
                self.REPEALED_PATTERN.search(chunk) or
                (candidate.title and self.REPEALED_PATTERN.search(candidate.title))
            )
            if not is_repealed:
                logger.warning(
                    f"[{source_id}] REJECTED low-confidence candidate: "
                    f"type={candidate.node_type}, number={candidate.number}, "
                    f"confidence={candidate.confidence:.2f}, "
                    f"chars=[{candidate.start_char_idx}:{candidate.end_char_idx}]"
                )
                return None
            logger.info(
                f"[{source_id}] Low-confidence but REPEALED/OMITTED — kept as stub: "
                f"{candidate.node_type} {candidate.number}"
            )

        # --- Minimum content length ---
        if len(chunk) < 10 and not self.REPEALED_PATTERN.search(chunk):
            logger.warning(
                f"[{source_id}] REJECTED candidate with too-short content ({len(chunk)} chars): "
                f"{candidate.node_type} {candidate.number}"
            )
            return None

        # --- Source integrity check ---
        normalized_chunk = _normalize_for_integrity(chunk[:500])  # check first 500 chars
        normalized_source = _normalize_for_integrity(raw_text)
        if normalized_chunk and normalized_chunk not in normalized_source:
            logger.error(
                f"[{source_id}] INTEGRITY FAILURE — chunk text not traceable to source: "
                f"type={candidate.node_type}, number={candidate.number}, "
                f"chars=[{candidate.start_char_idx}:{candidate.end_char_idx}]. "
                f"DO NOT EMBED this chunk."
            )
            return None

        return candidate

    def validate_candidates(
        self,
        candidates: List[LegalCandidate],
        raw_text: str,
        source_id: str = "UNKNOWN",
    ) -> List[LegalCandidate]:
        """
        Batch-validates a list of ``LegalCandidate`` objects.
        Returns only accepted candidates; logs a summary.
        """
        accepted: List[LegalCandidate] = []
        low_conf: List[LegalCandidate] = []
        rejected = 0

        for c in candidates:
            if c.confidence >= _ACCEPT_THRESHOLD:
                # Fast-path: high confidence, still run integrity check
                result = self.validate_candidate(c, raw_text, source_id)
                if result:
                    accepted.append(result)
                else:
                    rejected += 1
            elif c.confidence >= _REVIEW_THRESHOLD:
                low_conf.append(c)
                result = self.validate_candidate(c, raw_text, source_id)
                if result:
                    accepted.append(result)
                else:
                    rejected += 1
            else:
                result = self.validate_candidate(c, raw_text, source_id)
                if result:
                    accepted.append(result)
                else:
                    rejected += 1

        logger.info(
            f"[{source_id}] Validation summary: "
            f"{len(accepted)} accepted, {len(low_conf)} low-confidence reviewed, "
            f"{rejected} rejected from {len(candidates)} candidates."
        )
        return accepted

    # ==================================================================
    # LEGACY API — unchanged
    # ==================================================================

    def validate_and_clean(
        self, candidate: SectionCandidate, raw_text: str
    ) -> Optional[Tuple[SectionCandidate, str]]:
        chunk = raw_text[candidate.start_char_idx:candidate.end_char_idx].strip()

        if len(chunk) < 20:
            if self.REPEALED_PATTERN.search(chunk) or self.REPEALED_PATTERN.search(candidate.section_title):
                logger.info(
                    f"Section {candidate.section_number}: short but marked repealed/omitted — "
                    f"kept as stub so it isn't flagged as a detection gap."
                )
                return candidate, f"[STATUS: REPEALED/OMITTED] {chunk or candidate.section_title}"
            logger.warning(
                f"Discarding candidate Section {candidate.section_number}: content too short "
                f"({len(chunk)} chars) and not marked repealed — likely a detection error, not a real gap."
            )
            return None

        cleaned_text = re.sub(r'\n{3,}', '\n\n', chunk)
        cleaned_text = re.sub(r'\[\d+\]', '', cleaned_text)
        return candidate, cleaned_text