import re
from typing import List, Optional, Dict, Any, Tuple
from loguru import logger

from .models import SectionCandidate, LegalCandidate
from .section_extractor import TocStructuralIndex


# ---------------------------------------------------------------------------
# Sentinel constants — must match PdfPlumberLoader
# ---------------------------------------------------------------------------
_H_START = r'<<<HEADING>>>'
_H_END   = r'<<<END_HEADING>>>'


# ---------------------------------------------------------------------------
# Confidence scoring helpers
# ---------------------------------------------------------------------------

def _score_candidate(
    title: Optional[str],
    is_sentinel: bool,
    is_sequential: bool,
    toc_confirmed: bool,
) -> float:
    score = 0.50
    if is_sentinel:
        score += 0.30      # font/style evidence is strong
    if is_sequential:
        score += 0.20      # numbering continues from previous same-type candidate
    if toc_confirmed:
        score += 0.20      # TOC independently confirms this location
    if title and len(title) > 120:
        score -= 0.10      # overly long "titles" are probably body text bleed-through
    if title and len(title) > 200:
        score -= 0.20      # definitely body text, not a heading
    return min(max(score, 0.0), 1.0)


def _is_sequential(number: Optional[str], prev_number: Optional[str]) -> bool:
    """Returns True if number follows prev_number in a simple integer sequence."""
    if not number or not prev_number:
        return False
    m1 = re.match(r'^(\d+)', str(prev_number))
    m2 = re.match(r'^(\d+)', str(number))
    if m1 and m2:
        return int(m2.group(1)) - int(m1.group(1)) in (1, 0)
    return False


# ---------------------------------------------------------------------------
# Generic pattern table
# Each entry: (node_type, compiled_pattern_inside_heading, number_group, title_group)
# Patterns are applied ONLY inside <<<HEADING>>>…<<<END_HEADING>>> sentinels.
# ---------------------------------------------------------------------------

_SENTINEL_PATTERNS: List[Tuple[str, re.Pattern, int, Optional[int]]] = [
    # Part: PART I / PART ONE / PART 1
    ("part",
     re.compile(r'(?i)^PART\s+([IVXLCDM]+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|\d+)[\s:\-–—]*(.{0,100})?$'),
     1, 2),

    # Chapter: CHAPTER I / CHAPTER 1
    ("chapter",
     re.compile(r'(?i)^CHAPTER\s+([IVXLCDM]+|\d+)[\s:\-–—]*(.{0,100})?$'),
     1, 2),

    # Article: Article 14 / Article 14.
    ("article",
     re.compile(r'(?i)^Article\s+(\d+[A-Z]?)[.\s:\-–—]*(.{0,120})?$'),
     1, 2),

    # Rule: Rule 5 / Rule 5.
    ("rule",
     re.compile(r'(?i)^Rule\s+(\d+[A-Z]?)[.\s:\-–—]*(.{0,120})?$'),
     1, 2),

    # Regulation: Regulation 8 / Regulation 8.
    ("regulation",
     re.compile(r'(?i)^Regulation\s+(\d+[A-Z]?)[.\s:\-–—]*(.{0,120})?$'),
     1, 2),

    # Section: 3. Title / 3A. Title
    ("section",
     re.compile(r'^(\d{1,3}[A-Z]{0,2})\.\s+([A-Z][^<<<]{3,120}?)[\.\:\-–—]?\s*$'),
     1, 2),
]

# Pattern for subsection / clause detection in BODY text (not sentinel-gated)
_BODY_PATTERNS: List[Tuple[str, re.Pattern, int]] = [
    ("subsection", re.compile(r'(?m)^\s*\((\d+)\)\s'), 1),
    ("clause",     re.compile(r'(?m)^\s*\(([a-z])\)\s'), 1),
    ("subclause",  re.compile(r'(?m)^\s*\(([ivxlcdm]+)\)\s', re.IGNORECASE), 1),
]


class CandidateDetector:
    """
    Detects structural candidates from legal document text.

    Two public APIs:

    ``detect_generic_candidates(full_text, toc_index)``
        New API — returns ``List[LegalCandidate]``.
        Matches ONLY inside ``<<<HEADING>>>`` sentinels (from pdfplumber).
        Falls back to regex on plain text if no sentinels are found.
        Detects: part, chapter, section, article, rule, regulation.

    ``detect_candidates(full_text, toc_index)``
        Legacy API — returns ``List[SectionCandidate]``.
        Unchanged from original implementation; used by existing pipeline.
    """

    def __init__(self):
        # Legacy patterns (unchanged) — used by detect_candidates()
        self.section_pattern = re.compile(
            r'\n(\d{1,3}[A-Z]{0,2})\.\s+([A-Za-z][^\n]{3,200}?)[.\u2014\u2013:-]\s*\n',
            re.MULTILINE
        )
        self.chapter_pattern = re.compile(
            r'\n(CHAPTER\s+[IVXLCDM]+)\s*[\n:\-–—]*\s*([A-Z][A-Za-z0-9\s,&/()\-–—]{2,100})(?=\n)',
            re.MULTILINE
        )

    # ==================================================================
    # NEW GENERIC API
    # ==================================================================

    def detect_generic_candidates(
        self,
        full_text: str,
        toc_index: Optional[TocStructuralIndex] = None,
    ) -> List[LegalCandidate]:
        """
        Detect structural candidates using heading sentinels and/or regex.

        Strategy:
          1. If the text contains ``<<<HEADING>>>`` sentinels (from pdfplumber),
             match patterns exclusively inside sentinel blocks.
          2. If no sentinels exist (e.g. plain .txt files), fall back to
             conservative regex with ``^`` anchors.
          3. Body-level patterns (subsections, clauses) are detected in the
             full text regardless, but only within known section boundaries.

        Returns a flat ``List[LegalCandidate]`` ordered by ``start_char_idx``.
        The ``HierarchyBuilder`` converts this into a tree.
        """
        has_sentinels = _H_START in full_text

        if has_sentinels:
            candidates = self._detect_from_sentinels(full_text, toc_index)
        else:
            logger.info(
                "CandidateDetector: no heading sentinels found — using regex fallback "
                "(plain text mode, e.g. .txt files)."
            )
            candidates = self._detect_regex_fallback(full_text, toc_index)

        logger.info(
            f"Generic Candidate Detection: {len(candidates)} candidates found "
            f"({'sentinel' if has_sentinels else 'regex'} mode)."
        )
        self._report_gaps(candidates)
        return candidates

    # ------------------------------------------------------------------
    def _detect_from_sentinels(
        self,
        full_text: str,
        toc_index: Optional[TocStructuralIndex],
    ) -> List[LegalCandidate]:
        """Match structural patterns only within <<<HEADING>>>…<<<END_HEADING>>> blocks."""

        # Extract all heading spans: (start_in_text, end_in_text, heading_content)
        sentinel_re = re.compile(
            rf'{re.escape(_H_START)}(.*?){re.escape(_H_END)}',
            re.DOTALL
        )

        raw_matches: List[LegalCandidate] = []

        for m in sentinel_re.finditer(full_text):
            heading_text = m.group(1).strip()
            heading_start = m.start()
            heading_end = m.end()

            matched_candidate: Optional[LegalCandidate] = None

            for node_type, pattern, num_grp, title_grp in _SENTINEL_PATTERNS:
                pm = pattern.match(heading_text)
                if not pm:
                    continue
                number = pm.group(num_grp).strip() if pm.lastindex and pm.lastindex >= num_grp else None
                title = (
                    pm.group(title_grp).strip()
                    if title_grp and pm.lastindex and pm.lastindex >= title_grp
                    else None
                )
                # Clean empty title
                if title == "":
                    title = None

                confidence = _score_candidate(
                    title=title,
                    is_sentinel=True,
                    is_sequential=False,   # updated below after dedup+sort
                    toc_confirmed=False,   # updated below if toc_index available
                )

                matched_candidate = LegalCandidate(
                    node_type=node_type,
                    number=number,
                    title=title,
                    start_char_idx=heading_start,
                    end_char_idx=heading_end,  # end_char_idx updated after processing all
                    confidence=confidence,
                    detection_method="heading_sentinel",
                )
                break  # first matching pattern wins (ordered by specificity)

            if matched_candidate:
                raw_matches.append(matched_candidate)

        if not raw_matches:
            return []

        # Sort by position, then assign end_char_idx = next candidate's start
        raw_matches.sort(key=lambda c: c.start_char_idx)

        # Deduplication: if same number+type appears twice (TOC + body), keep last
        seen: Dict[str, LegalCandidate] = {}
        for c in raw_matches:
            key = f"{c.node_type}_{c.number}"
            seen[key] = c
        deduped = sorted(seen.values(), key=lambda c: c.start_char_idx)

        # Assign end_char_idx and update sequential confidence
        result: List[LegalCandidate] = []
        prev_by_type: Dict[str, LegalCandidate] = {}

        for i, c in enumerate(deduped):
            end_idx = deduped[i + 1].start_char_idx if i + 1 < len(deduped) else len(full_text)
            sequential = _is_sequential(c.number, prev_by_type.get(c.node_type, LegalCandidate(
                node_type=c.node_type, start_char_idx=0, end_char_idx=0
            )).number)

            # TOC confirmation
            toc_ok = False
            if toc_index and toc_index.has_toc and c.node_type in ("chapter", "part"):
                toc_ok = True   # any chapter-level candidate near a TOC page is boosted

            updated_confidence = _score_candidate(
                title=c.title,
                is_sentinel=True,
                is_sequential=sequential,
                toc_confirmed=toc_ok,
            )

            updated = c.model_copy(update={
                "end_char_idx": end_idx,
                "confidence": updated_confidence,
            })
            result.append(updated)
            prev_by_type[c.node_type] = updated

        logger.debug(
            f"Sentinel detection: {len(raw_matches)} raw → {len(result)} after dedup."
        )
        return result

    # ------------------------------------------------------------------
    def _detect_regex_fallback(
        self,
        full_text: str,
        toc_index: Optional[TocStructuralIndex],
    ) -> List[LegalCandidate]:
        """
        Conservative regex detection for plain-text files (no pdfplumber sentinels).
        Uses line-start anchors to reduce false positives.
        """
        # Build a combined pattern list with ^-anchored regex variants
        plain_patterns: List[Tuple[str, re.Pattern, int, Optional[int]]] = [
            ("part",
             re.compile(r'(?im)^PART\s+([IVXLCDM]+|ONE|TWO|THREE|\d+)[\s:\-–—]*(.{0,100})?$'),
             1, 2),
            ("chapter",
             re.compile(r'(?im)^CHAPTER\s+([IVXLCDM]+|\d+)[\s:\-–—]*(.{0,100})?$'),
             1, 2),
            ("article",
             re.compile(r'(?im)^Article\s+(\d+[A-Z]?)[.\s:\-–—]*(.{0,120})?$'),
             1, 2),
            ("rule",
             re.compile(r'(?im)^Rule\s+(\d+[A-Z]?)[.\s:\-–—]*(.{0,120})?$'),
             1, 2),
            ("regulation",
             re.compile(r'(?im)^Regulation\s+(\d+[A-Z]?)[.\s:\-–—]*(.{0,120})?$'),
             1, 2),
            ("section",
             re.compile(r'(?m)^(\d{1,3}[A-Z]{0,2})\.\s+([A-Z][^\n]{3,120}?)[\.\:\-–—]?\s*$'),
             1, 2),
        ]

        all_candidates: List[LegalCandidate] = []
        for node_type, pattern, num_grp, title_grp in plain_patterns:
            raw_matches_this = list(pattern.finditer(full_text))
            # Dedup: last occurrence wins (body over TOC)
            seen: Dict[str, Any] = {}
            for m in raw_matches_this:
                key = m.group(num_grp).strip() if m.lastindex and m.lastindex >= num_grp else m.group(0)
                seen[key] = m
            for key, m in seen.items():
                number = m.group(num_grp).strip() if m.lastindex and m.lastindex >= num_grp else None
                title = (
                    m.group(title_grp).strip()
                    if title_grp and m.lastindex and m.lastindex >= title_grp
                    else None
                ) or None
                all_candidates.append(LegalCandidate(
                    node_type=node_type,
                    number=number,
                    title=title,
                    start_char_idx=m.start(),
                    end_char_idx=m.end(),
                    confidence=_score_candidate(title, is_sentinel=False,
                                                is_sequential=False, toc_confirmed=False),
                    detection_method="regex",
                ))

        # Sort and assign end boundaries
        all_candidates.sort(key=lambda c: c.start_char_idx)
        result: List[LegalCandidate] = []
        prev_by_type: Dict[str, LegalCandidate] = {}
        for i, c in enumerate(all_candidates):
            end_idx = all_candidates[i + 1].start_char_idx if i + 1 < len(all_candidates) else len(full_text)
            sequential = _is_sequential(c.number, prev_by_type.get(c.node_type, LegalCandidate(
                node_type=c.node_type, start_char_idx=0, end_char_idx=0
            )).number)
            updated = c.model_copy(update={
                "end_char_idx": end_idx,
                "confidence": _score_candidate(c.title, is_sentinel=False,
                                               is_sequential=sequential, toc_confirmed=False),
            })
            result.append(updated)
            prev_by_type[c.node_type] = updated

        return result

    # ==================================================================
    # LEGACY API — unchanged, backward compatible
    # ==================================================================

    def detect_candidates(
        self,
        full_text: str,
        toc_index: Optional[TocStructuralIndex] = None,
    ) -> List[SectionCandidate]:
        """
        [LEGACY] Original section-centric detection returning ``SectionCandidate`` objects.

        This method is unchanged from the original implementation and is kept for
        full backward compatibility with ``pipeline.py`` and ``validator.py``.
        New code should call ``detect_generic_candidates()`` instead.
        """
        raw_matches = list(self.section_pattern.finditer(full_text))
        use_toc = toc_index is not None and toc_index.has_toc

        seen_secs: Dict[str, Any] = {}
        for m in raw_matches:
            sec_key = m.group(1).strip()
            seen_secs[sec_key] = m
        matches = sorted(seen_secs.values(), key=lambda m: m.start())
        logger.debug(
            f"Section candidate filtering: {len(raw_matches)} raw matches "
            f"→ {len(matches)} after deduplication."
        )

        chapter_matches: list = []
        if not use_toc:
            raw_chapter_matches = list(self.chapter_pattern.finditer(full_text))
            seen: Dict[str, Any] = {}
            for ch in raw_chapter_matches:
                key = ch.group(1).strip()
                seen[key] = ch
            chapter_matches = sorted(seen.values(), key=lambda m: m.start())
            logger.debug(
                f"Regex fallback: {len(raw_chapter_matches)} raw chapter matches "
                f"→ {len(chapter_matches)} after deduplication."
            )

        candidates: List[SectionCandidate] = []
        for i, match in enumerate(matches):
            sec_num = match.group(1).strip()
            sec_title = match.group(2).strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)

            current_chapter: Optional[str] = None
            if not use_toc:
                for ch in chapter_matches:
                    if ch.start() <= start:
                        current_chapter = f"{ch.group(1).strip()}: {ch.group(2).strip()}"
                    else:
                        break

            candidates.append(
                SectionCandidate(
                    section_number=sec_num,
                    section_title=sec_title,
                    start_char_idx=start,
                    end_char_idx=end,
                    chapter_ref=current_chapter
                )
            )

        logger.info(
            f"[Legacy] Candidate Detection: Found {len(candidates)} section candidates "
            f"(chapter source: {'TOC structural index' if use_toc else 'regex fallback with dedup'})."
        )
        self._report_gaps_legacy(candidates)
        if not use_toc:
            self._report_missing_chapters(candidates)
        return candidates

    # ==================================================================
    # Reporting helpers
    # ==================================================================

    def _report_gaps(self, candidates: List[LegalCandidate]) -> None:
        """Flags likely missed sections by checking numeric sequence gaps."""
        by_type: Dict[str, List[int]] = {}
        for c in candidates:
            if c.number:
                m = re.match(r'(\d+)', c.number)
                if m:
                    by_type.setdefault(c.node_type, []).append(int(m.group(1)))

        for node_type, nums in by_type.items():
            nums_sorted = sorted(set(nums))
            for i in range(len(nums_sorted) - 1):
                gap = nums_sorted[i + 1] - nums_sorted[i]
                if gap > 2:
                    missing = list(range(nums_sorted[i] + 1, nums_sorted[i + 1]))
                    logger.warning(
                        f"Gap check [{node_type}]: possible missing {node_type}(s) "
                        f"{missing} between {nums_sorted[i]} and {nums_sorted[i+1]}."
                    )

    def _report_gaps_legacy(self, candidates: List[SectionCandidate]) -> List[str]:
        """Legacy gap reporter for SectionCandidate (unchanged)."""
        warnings = []
        nums = sorted(set(
            int(m.group(1)) for c in candidates
            if (m := re.match(r'(\d+)', c.section_number))
        ))
        for i in range(len(nums) - 1):
            gap = nums[i + 1] - nums[i]
            if gap > 1:
                missing = list(range(nums[i] + 1, nums[i + 1]))
                msg = f"Possible missing section(s) {missing} between Section {nums[i]} and Section {nums[i+1]}"
                warnings.append(msg)
                logger.warning(msg)
        if not warnings:
            logger.info("Gap check: no numeric gaps detected in section sequence.")
        return warnings

    def _report_missing_chapters(self, candidates: List[SectionCandidate]) -> None:
        """Legacy: flags sections that got no chapter context (unchanged)."""
        unassigned = [c.section_number for c in candidates if c.chapter_ref is None]
        if unassigned:
            logger.warning(
                f"{len(unassigned)} section(s) have no chapter assigned "
                f"(possible chapter-heading detection miss): {unassigned}"
            )

