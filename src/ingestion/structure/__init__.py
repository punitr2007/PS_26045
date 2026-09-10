from .models import (
    LegalDocumentConfig,
    SectionCandidate,
    LegalCandidate,
    LegalNode,
    section_candidate_to_legal_candidate,
)
from .candidate_detector import CandidateDetector
from .validator import ContextValidator
from .section_extractor import TocStructuralIndex, LegalSectionExtractor, TocEntry
from .hierarchy_builder import HierarchyBuilder, flatten_tree, find_ancestors

__all__ = [
    # Existing exports (unchanged)
    "LegalDocumentConfig",
    "SectionCandidate",
    "CandidateDetector",
    "ContextValidator",
    "TocStructuralIndex",
    "LegalSectionExtractor",
    # New exports
    "LegalCandidate",
    "LegalNode",
    "TocEntry",
    "section_candidate_to_legal_candidate",
    "HierarchyBuilder",
    "flatten_tree",
    "find_ancestors",
]
