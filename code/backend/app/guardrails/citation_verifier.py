import re
from typing import List, Tuple, Optional, Any, Dict
from loguru import logger

# Matches Indian legal statutory citations such as:
# Section 3, Section 3(p), Section 2(1)(j), Section 107, Rule 169(A), Article 21
_STATUTORY_CITATION_PATTERN = re.compile(
    r"\b(?:Section|Sec\.|Rule|Article)\s*(\d+[A-Za-z]?(?:\s*\([a-z0-9A-Z]+\))*)",
    re.IGNORECASE,
)

# Matches clause citations like "clause (p)", "sub-clause (p)"
_CLAUSE_PATTERN = re.compile(
    r"\b(?:clause|sub-clause|subclause)\s*\(([a-z0-9]+)\)",
    re.IGNORECASE,
)

# Phrases where the LLM explicitly confesses that the text was not in the retrieved context
_ABSENT_EVIDENCE_ADMISSIONS = [
    "not reproduced in the excerpt",
    "not reproduced in the provided",
    "not reproduced in the retrieved",
    "not provided in the excerpt",
    "not provided in the retrieved",
    "not included in the excerpt",
    "not included in the retrieved text",
    "not explicitly detailed in the excerpt",
    "not explicitly reproduced",
    "excerpt does not contain",
    "excerpts do not contain",
    "not found in the excerpt",
    "exact list is not reproduced",
]


def normalize_locator(loc: str) -> str:
    """Normalizes locators for comparison, e.g. '3 (p)' -> '3(p)'."""
    return re.sub(r"[^\w()]", "", loc.lower())


class CitationVerifier:
    """
    Verifies that statutory citations made in an LLM-generated answer
    are strictly grounded in the retrieved legal chunks.
    """

    @staticmethod
    def extract_citations(text: str) -> List[str]:
        """Extracts unique cited statutory sections, rules, and articles from text."""
        citations = []
        for match in _STATUTORY_CITATION_PATTERN.finditer(text):
            citations.append(match.group(0).strip())
            
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for c in citations:
            norm = normalize_locator(c)
            if norm not in seen:
                seen.add(norm)
                unique.append(c)
        return unique

    @staticmethod
    def check_admissions_of_missing_evidence(text: str) -> Optional[str]:
        """
        Checks if the LLM admitted that a cited statutory list or provision was
        missing from the provided excerpts.
        """
        lower_text = text.lower()
        for phrase in _ABSENT_EVIDENCE_ADMISSIONS:
            if phrase in lower_text:
                return f"Model admitted evidence was missing from retrieved context ('{phrase}')."
        return None

    @classmethod
    def verify(
        cls, draft_answer: str, top_evidences: List[Any]
    ) -> Tuple[bool, List[str], List[str], Optional[str]]:
        """
        Validates draft answer against top_evidences.

        Returns:
            (passed, verified_citations, unverified_citations, reason)
        """
        # 1. Check for explicit LLM admission that text was missing from retrieved context
        admission_reason = cls.check_admissions_of_missing_evidence(draft_answer)
        if admission_reason:
            logger.warning(f"Citation verification failed: {admission_reason}")
            # Even if it passes other checks, an answer stating 'text was not reproduced'
            # indicates hallucination from training data.
            return False, [], [], admission_reason

        # 2. Extract citations from answer
        citations = cls.extract_citations(draft_answer)
        if not citations:
            # If no formal statutory citations were made, pass verification
            return True, [], [], None

        # 3. Build lookup corpus from top_evidences
        evidence_locators = set()
        evidence_texts = []
        
        for ev in top_evidences:
            chunk = getattr(ev, "chunk", ev)
            prov = getattr(chunk, "provision", "") or ""
            sec = getattr(chunk, "section", "") or ""
            art = getattr(chunk, "article", "") or ""
            title = getattr(chunk, "title", "") or ""
            text = getattr(chunk, "text", "") or ""

            for raw_loc in [prov, sec, art]:
                if raw_loc:
                    evidence_locators.add(normalize_locator(str(raw_loc)))
            
            # Combine locators and text for fallback keyword searching
            evidence_texts.append(f"{prov} {title} {text}".lower())

        verified = []
        unverified = []

        for citation in citations:
            norm_c = normalize_locator(citation)
            # Extract digits and subclauses, e.g. "section3(p)" -> "3(p)", "3"
            num_match = re.search(r"(\d+[a-z]?(?:\([a-z0-9]+\))*)", norm_c)
            loc_target = num_match.group(1) if num_match else norm_c
            parent_target = re.match(r"(\d+)", loc_target).group(1) if re.match(r"(\d+)", loc_target) else loc_target

            # Direct match against chunk metadata provision
            is_matched = False
            for eloc in evidence_locators:
                if loc_target in eloc or eloc in loc_target:
                    is_matched = True
                    break

            # Fallback: check if the exact provision/clause appears in the text of any chunk
            if not is_matched:
                clause_match = re.search(r"\(([a-z0-9]+)\)", loc_target)
                clause_char = clause_match.group(1) if clause_match else None
                
                for ev_text in evidence_texts:
                    # Look for citation pattern or specific clause indicator inside the chunk
                    if loc_target in ev_text:
                        is_matched = True
                        break
                    # If citation is Section 3(p), check if chunk mentions "section 3" AND "(p)"
                    if parent_target and f"section {parent_target}" in ev_text:
                        if clause_char:
                            if f"({clause_char})" in ev_text or f"clause ({clause_char})" in ev_text:
                                is_matched = True
                                break
                        else:
                            is_matched = True
                            break

            if is_matched:
                verified.append(citation)
            else:
                unverified.append(citation)

        if unverified:
            logger.warning(
                f"Citation verification: {len(verified)} verified, {len(unverified)} unverified: {unverified}"
            )
            # If critical statutory provisions cited in answer were completely missing from evidence
            reason = (
                f"Statutory citations not backed by retrieved evidence text: {', '.join(unverified)}. "
                "Answer relied on background model knowledge rather than retrieved statutory chunks."
            )
            return False, verified, unverified, reason

        logger.info(f"Citation verification passed: all {len(verified)} citations grounded in retrieved evidence.")
        return True, verified, [], None
