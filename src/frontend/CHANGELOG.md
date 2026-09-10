# IP-Shakti RAG Pipeline — Changelog
Date: 2026-09-05
Session Summary: Fixed 4 bugs that were causing the chatbot to abstain (say "I don't have enough info") even when the legal data was present in the database.

---

## Fix 1 — Chatbot never searched for traditional knowledge laws like Section 3(p)
File: app/core/query_decomposer.py

What was wrong:
When a user asked "can I patent haldi milk?", the system classified the product as ayurveda-aahar.
But the rule that decides which laws to search only looked at Trademark and Drug Regulation.
It never searched Traditional Knowledge law (Section 3(p) of the Patents Act) or Geographical Indication (GI) law
— which are the most relevant laws for a turmeric-based formulation.

What was fixed:
- ayurveda-aahar products now also search Traditional Knowledge and GI law.
- proprietary products now also search Traditional Knowledge law.
- If the query/ingredients contain words like turmeric, haldi, ginger, ayurvedic, herbal etc.,
  the system automatically adds TK and GI searches.
- If the query mentions "section 3" or "3(p)", Patent + TK searches are forced.

Simple result: Asking "can I patent haldi milk?" will now retrieve Section 3(p) instead of irrelevant Section 84.

---

## Fix 2 — Retrieved evidence was appearing in duplicate in the LLM context
Files: app/graph/state.py, app/graph/nodes/generate.py, app/graph/nodes/guardrail.py, app/generation/evidence_pack.py

What was wrong:
After ranking legal evidence, the system kept TWO copies of every result.
The original unranked copy AND the reranked copy were both stored in state.
So the LLM was seeing the same legal sections repeated twice, wasting the context window.

What was fixed:
- generate.py no longer writes ranked results back into evidence_packs.
  Instead it saves results in two new state fields: top_evidences and context_str.
- guardrail.py now reads from top_evidences directly (already-ranked results).
- evidence_pack.merge() now deduplicates by chunk_id before sorting.
  If the same section appears multiple times, only the highest-scored copy is kept.

Simple result: No more repeated law sections. Each unique provision appears exactly once.

---

## Fix 3 — The ranking system could not tell relevant sections from irrelevant ones
Files: app/schemas/pipeline.py, app/retrieval/hybrid_retriever.py, app/retrieval/reranker.py, app/retrieval/reranker_engine.py

What was wrong (3 sub-problems):

3a — Raw similarity scores were too compressed:
All Qdrant search results came back with scores in a tiny range like 0.06 to 0.08.
Because these numbers are so close together, the ranker could not tell which section was relevant.
Section 84 (compulsory licences — irrelevant to patentability) scored nearly the same as
Section 2 (definitions of inventions — directly relevant).

3b — Legal area label was being faked:
The reranker has an "applicability" score that checks whether a chunk's legal area matches the query.
But the code was tagging EVERY chunk with the sub-query's area before scoring.
So every chunk automatically got a perfect 1.0 applicability score. The signal was useless.

3c — legal_area was not being stored on retrieved chunks:
The RetrievedChunk object had no field for legal_area, so the real area stored in Qdrant was thrown away.

What was fixed:
- Added legal_area field to RetrievedChunk (pipeline.py).
- hybrid_retriever.py now reads the real legal_area from Qdrant metadata and stores it on the chunk.
- reranker.py now uses the chunk's actual stored legal_area instead of stamping all chunks with the sub-query area.
- reranker_engine.py now applies sigmoid stretch to raw Qdrant scores so they spread across 0.1–0.9 range.
  Before: 0.06–0.08 all mapped to near-identical values.
  After:  score 0.05 (irrelevant) -> ~0.18, score 0.14 (relevant) -> ~0.85.

Simple result: The ranker can now tell "this section is relevant" from "this section is noise".

---

## Fix 4 — Same legal section appeared multiple times in search results
File: app/retrieval/reranker.py

What was wrong:
The reranker has a built-in MMR deduplication feature that removes near-identical chunks.
But this feature was turned OFF by default, so the same section could appear 3-4 times in results.

What was fixed:
One-liner change: LegalReranker(enable_mmr_dedup=True)

Simple result: If Section 84 appears 3 times in raw results, only the best-scored version is kept.
The other slots go to different, more diverse legal provisions.

---

## Fix 5 — Reranker scored every law chunk identical 0.8275 (score collapse)
Files: app/retrieval/reranker_engine.py, app/generation/evidence_pack.py

What was wrong:
Even though Section 3(p) (traditional knowledge exclusion) was retrieved with a good score (0.6381),
it got pushed out of the final list.
Why? The scoring formula had center=0.10. Because actual vector scores were 0.45–0.70, the formula
maxed out at 1.0 for EVERY chunk.
Combined with all legal acts having identical 1.0 scores for authority, freshness, and jurisdiction,
every chunk ended up with an identical total score of 0.8275.
Section 107 (infringement defences) and an irrelevant Trademark chunk beat Section 3(p) purely by random chance.

What was fixed:
- Adjusted the formula center to 0.55 and steepness to 16.0 (matching actual database scores).
  Now:
  - Weak match (0.4757) -> scores low (0.23)
  - Strong match (0.6381, Section 3) -> scores high (0.80)
  - Very strong match (0.6768) -> scores 0.88
- Changed score weights so relevance is 60% of the decision (was only 35%).
- Added strict tie-breaking in evidence_pack.merge(): if total scores are close, the chunk with higher vector similarity strictly wins.

Simple result: Section 3(p) decisively beats irrelevant chunks and takes top rank.

---

## Fix 6 — Neural Cross-Encoder given wrong question terms
Files: app/retrieval/reranker.py, app/retrieval/reranker_engine.py

What was wrong:
When using the neural reranker, it was only given the user's raw question ("can I patent haldi milk?").
The legal provisions in the Patent Act don't mention the words "haldi" or "milk".
So the neural reranker thought none of them were relevant and gave neutral logits (~0),
collapsing all scores to ~0.65.

What was fixed:
- The reranker is now given the effective query combining both user question and the legal sub-query:
  e.g., "can I patent haldi milk? - what are not inventions, not an invention within the meaning of this Act, TKDL".
- The neural and vector scores are blended 60% neural and 40% vector score (per user setting).

Simple result: The cross-encoder now sees legal terms like "inventions" and "traditional knowledge", allowing it to recognize Section 3(p).

---

## Fix 7 — Citation Verification Node (Grounding Guardrail)
Files: app/guardrails/citation_verifier.py, app/guardrails/guardrail_checker.py, app/graph/nodes/guardrail.py, app/schemas/pipeline.py

What was wrong:
Sometimes the LLM produced a good-sounding answer citing Section 3(p), but admitted inside the answer:
"the exact list is not reproduced in the excerpt".
The chatbot was answering from training memory instead of real retrieved database text!
There was no check to verify if cited sections actually existed in the retrieved excerpts.

What was fixed:
- Created app/guardrails/citation_verifier.py:
  1. Scans draft answers for all cited sections/rules (Section 3(p), Section 107, Rule 169, etc.).
  2. Checks each citation against the actual text and metadata of retrieved chunks.
  3. Detects phrases where the AI admits text was missing (e.g. "not reproduced in the excerpt").
- Integrated into guardrail_checker.py and guardrail_node.py:
  If an answer cites legal provisions that do not exist in the retrieved evidence, the guardrail rejects it,
  preventing hallucinated legal claims from reaching the user and triggering a retry to retrieve the missing law.

Simple result: The chatbot will never give an answer claiming a legal provision says something unless that provision is verified in the retrieved evidence.
*(Note: Temporarily deactivated in guardrail_checker.py per user request for unrestricted testing of retrieval and generation).*

---

## Fix 8 — MMR Deduplication was discarding distinct clauses of Section 3
File: app/retrieval/reranker_engine.py

What was wrong:
The reranker deduplication logic was using `(document_id, section)` as the uniqueness key.
Section 3 is broken into multiple chunks: `section_3_c0` (header), `c1` (clauses a-d), `c3` (clauses e-j), and `c4` (clauses k-p, including traditional knowledge clause p).
Because all of them share the label "Section 3", the dedup function assumed `c1`, `c3`, and `c4` were duplicates of `c0`, and silently dropped them!
This was why `section_3_c4` (clause p) kept vanishing right before reaching the final ranking.

What was fixed:
- Rewrote `_dedup_near_duplicates`:
  - Dedup now keys on `chunk_id` equality and exact/near-identical text content.
  - Different sub-chunks (different chunk IDs) of the same section are NEVER treated as duplicates, ensuring all distinct statutory clauses survive.

Simple result: Clause (p) (traditional knowledge exclusion) and all other distinct clauses of Section 3 will now survive deduplication.

---

## Fix 9 — Duplicate citation entries across sub-queries in output display
File: app/services/chatbot_service.py

What was wrong:
When displaying `[RETRIEVED LEGAL SOURCES]`, the chatbot service was reading raw, unranked evidence packs instead of the final deduplicated `top_evidences` list.
Because multiple sub-queries retrieved Section 3, Section 3 appeared multiple times in the final citation list.

What was fixed:
- `chatbot_service.py` now directly reads the final reranked `top_evidences` produced by `generate_node`.
- Added strict `chunk_id` deduplication across sub-queries when constructing the `sources` list shown to the user.

Simple result: The final citation list will show unique, non-duplicated legal sources.

---

## Summary Table

Problem                                          | File(s) Fixed               | Priority
------------------------------------------------|-----------------------------|----------
Section 3(p) / TK never searched               | query_decomposer.py         | CRITICAL
Evidence appeared twice in LLM context          | state.py, generate.py,      | HIGH
                                                | guardrail.py, evidence_pack |
All chunks scored flat 0.8275 (Section 3 lost)  | reranker_engine.py,         | CRITICAL
                                                | evidence_pack.py            |
Dedup dropped Section 3 clauses (c1, c3, c4)    | reranker_engine.py          | CRITICAL
Display triplication across sub-queries         | chatbot_service.py          | HIGH
Cross-encoder missing sub-query legal context   | reranker.py, reranker_engine| HIGH
Duplicate sections from same document           | reranker.py                 | MEDIUM
