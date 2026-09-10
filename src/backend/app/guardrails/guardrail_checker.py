from typing import List, Any
from app.schemas.pipeline import GuardrailResult, RankedEvidence
from app.schemas.enums import Jurisdiction

def check(draft_answer: str, top_evidences: List[Any], jurisdiction: Jurisdiction) -> GuardrailResult:
    """
    Checks the generated draft to ensure it meets guardrails.
    Returns GuardrailResult gating whether to output the answer or abstain.
    """
    # 1. Simple heuristic check: evidence presence
    if not top_evidences:
        return GuardrailResult(
            passed=False,
            enough_evidence=False,
            current_law=True,
            correct_jurisdiction=True,
            reason="No relevant legal provisions retrieved."
        )

    # 2. Evidence quality check: if ALL top chunks have very low composite score
    # or very low applicability, the retrieval was poor (likely area mismatch).
    # This catches cases where the reranker penalized everything but the LLM
    # still received the penalized garbage as context.
    scored_evidences = [e for e in top_evidences if hasattr(e, "final_score")]
    if scored_evidences:
        avg_score = sum(e.final_score for e in scored_evidences) / len(scored_evidences)
        avg_applicability = sum(
            getattr(e, "applicability_score", 0.5) for e in scored_evidences
        ) / len(scored_evidences)
        if avg_score < 0.25:
            return GuardrailResult(
                passed=False,
                enough_evidence=False,
                current_law=True,
                correct_jurisdiction=True,
                reason=f"Retrieved evidence quality too low (avg score: {avg_score:.2f}). Likely area mismatch — will retry."
            )
        if avg_applicability < 0.3:
            return GuardrailResult(
                passed=False,
                enough_evidence=False,
                current_law=True,
                correct_jurisdiction=True,
                reason=f"Retrieved evidence applicability too low (avg: {avg_applicability:.2f}). Wrong legal area retrieved — will retry."
            )

    # 3. Check if LLM output indicates insufficiency
    lower_draft = draft_answer.lower()
    if ("insufficient" in lower_draft and "material" in lower_draft) or "cannot answer" in lower_draft:
        return GuardrailResult(
            passed=False,
            enough_evidence=False,
            current_law=True,
            correct_jurisdiction=True,
            reason="LLM determined that the retrieved context was insufficient."
        )

    return GuardrailResult(
        passed=True,
        enough_evidence=True,
        current_law=True,
        correct_jurisdiction=True,
        reason=None
    )


class GuardrailChecker:
    """Wrapper class providing object-oriented access to guardrail validation."""
    @staticmethod
    def check(draft_answer: str, top_evidences: List[Any], jurisdiction: Jurisdiction) -> GuardrailResult:
        return check(draft_answer, top_evidences, jurisdiction)

