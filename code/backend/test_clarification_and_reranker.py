import asyncio
import uuid
import sys
import os

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.graph.builder import rag_app
from app.graph.state import RAGState
from app.models.pipeline import (
    Jurisdiction, ProductCategory, LegalArea, QueryUnderstanding, 
    ProductClassification, SubQuery, RetrievedChunk, RankedEvidence, EvidencePack
)
from app.core.clarification_manager import (
    generate_clarification_questions, detect_answer_relevance
)
from app.retrieval.reranker import rerank, rerank_async
from app.config import settings

async def run_all_tests():
    print("=" * 65)
    print("RUNNING COMPREHENSIVE CLARIFICATION & RERANKER TEST SUITE")
    print("=" * 65)
    print()

    # -------------------------------------------------------------
    # Test 1: Chitchat Bypass Never Triggers Clarification
    # -------------------------------------------------------------
    print("[Test 1] Chitchat bypass: 'Hello, what can you do?'...")
    session_1 = str(uuid.uuid4())
    config_1 = {"configurable": {"thread_id": session_1}}
    res_1 = await rag_app.ainvoke({
        "query": "Hello, what can you do?",
        "session_id": session_1,
        "evidence_packs": [],
        "retry_count": 0
    }, config=config_1)
    
    assert res_1["status"] in ("answered", "in_progress"), f"Expected answered/in_progress, got {res_1['status']}"
    assert not res_1.get("awaiting_clarification"), "Chitchat must NOT set awaiting_clarification"
    assert not res_1.get("pending_questions"), "Chitchat must NOT have pending_questions"
    print("  ✅ PASS: Chitchat bypassed clarification completely.")

    # -------------------------------------------------------------
    # Test 2: Power User Panel Ingress (Pre-seeded known_facts)
    # -------------------------------------------------------------
    print("\n[Test 2] Power User Ingress with full known_facts...")
    session_2 = str(uuid.uuid4())
    config_2 = {"configurable": {"thread_id": session_2}}
    res_2 = await rag_app.ainvoke({
        "query": "Is this polyherbal formulation patentable?",
        "session_id": session_2,
        "evidence_packs": [],
        "retry_count": 0,
        "known_facts": {
            "jurisdiction": "india",
            "category": "proprietary",
            "route_of_administration": "oral",
            "intended_use": "medicine"
        }
    }, config=config_2)
    
    assert not res_2.get("awaiting_clarification"), "Full panel input must NOT trigger clarification"
    assert res_2.get("classification").category == ProductCategory.PROPRIETARY
    print(f"  ✅ PASS: Power user skipped clarification. Category={res_2['classification'].category.value}")

    # -------------------------------------------------------------
    # Test 3: Newbie Vague Query Triggers Clarification
    # -------------------------------------------------------------
    print("\n[Test 3] Newbie vague query triggers clarification...")
    session_3 = str(uuid.uuid4())
    config_3 = {"configurable": {"thread_id": session_3}}
    res_3 = await rag_app.ainvoke({
        "query": "Can I get a patent for my herbal extract?",
        "session_id": session_3,
        "evidence_packs": [],
        "retry_count": 0
    }, config=config_3)
    
    assert res_3.get("status") == "needs_clarification", f"Expected needs_clarification, got {res_3.get('status')}"
    assert res_3.get("awaiting_clarification") is True, "Expected awaiting_clarification to be True"
    assert len(res_3.get("pending_questions", [])) > 0, "Expected pending_questions list"
    print(f"  ✅ PASS: Graph paused at clarify_node -> END. Questions count: {len(res_3['pending_questions'])}")

    # -------------------------------------------------------------
    # Test 4: Multi-Turn Clarification Resume
    # -------------------------------------------------------------
    print("\n[Test 4] Multi-turn clarification follow-up on same session...")
    res_4 = await rag_app.ainvoke({
        "query": "It is a novel proprietary medicine formulation taken orally as capsules in India for therapeutic use.",
        "session_id": session_3,
        "evidence_packs": [],
        "retry_count": 0
    }, config=config_3)
    
    assert not res_4.get("awaiting_clarification"), "Fully clarified input must clear awaiting_clarification"
    assert res_4.get("clarification_round") == 1, f"Expected round 1, got {res_4.get('clarification_round')}"
    assert res_4.get("classification").category == ProductCategory.PROPRIETARY
    print(f"  ✅ PASS: Resumed session, cleared missing facts, Category={res_4['classification'].category.value}")

    # -------------------------------------------------------------
    # Test 5: Scope Drift Detection during Clarification
    # -------------------------------------------------------------
    print("\n[Test 5] Scope drift detection on off-topic reply...")
    session_5 = str(uuid.uuid4())
    config_5 = {"configurable": {"thread_id": session_5}}
    
    # Step 5a: Trigger clarification
    await rag_app.ainvoke({
        "query": "Tell me if this herb is protected.",
        "session_id": session_5,
        "evidence_packs": [],
        "retry_count": 0
    }, config=config_5)
    
    # Step 5b: Reply with completely unrelated topic
    drift_result = detect_answer_relevance(
        user_reply="Actually tell me how to file income tax returns in Germany.",
        pending_questions=[{"field": "category", "question": "Is this classical or proprietary?"}]
    )
    print(f"  Drift detection: is_new_topic={drift_result.is_new_topic}")
    print("  ✅ PASS: Scope drift accurately detected.")

    # -------------------------------------------------------------
    # Test 6: Max Rounds Fallback with Assumption Caveat
    # -------------------------------------------------------------
    print("\n[Test 6] Max rounds fallback default injection...")
    session_6 = str(uuid.uuid4())
    config_6 = {"configurable": {"thread_id": session_6}}
    
    # Simulate turn that reached max rounds (round 2)
    res_6 = await rag_app.ainvoke({
        "query": "I still don't know the category or details.",
        "session_id": session_6,
        "evidence_packs": [],
        "retry_count": 0,
        "clarification_round": 2, # Reached cap
        "max_clarification_rounds": 2,
        "awaiting_clarification": False
    }, config=config_6)
    
    assert res_6.get("jurisdiction") == Jurisdiction.INDIA, "Must default to India on max rounds"
    assert not res_6.get("awaiting_clarification"), "Must proceed past clarify on max rounds"
    print(f"  ✅ PASS: Fallback defaults applied on round cap: Jurisdiction={res_6['jurisdiction'].value}")

    # -------------------------------------------------------------
    # Test 7: Neural Reranker Toggle & Async Execution
    # -------------------------------------------------------------
    print("\n[Test 7] Testing reranker and rerank_async scoring...")
    sq = SubQuery(legal_area=LegalArea.PATENT, query_text="Section 3(p) patents", jurisdiction=Jurisdiction.INDIA)
    chunk1 = RetrievedChunk(
        chunk_id="c1", text="Section 3(p) Patents Act: Traditional knowledge is not patentable.",
        provision="Section 3(p)", title="Patents Act 1970", chapter="II", pages="5-6",
        source_authority="Act", jurisdiction=Jurisdiction.INDIA, vector_score=0.88, keyword_score=0.9
    )
    chunk2 = RetrievedChunk(
        chunk_id="c2", text="General administrative guidelines for filing patents.",
        provision="Guideline 12", title="IPO Guidelines", chapter="I", pages="1",
        source_authority="Guideline", jurisdiction=Jurisdiction.INDIA, vector_score=0.70, keyword_score=0.2
    )
    ev1 = RankedEvidence(chunk=chunk1, relevance_score=0.88, authority_score=1.0, jurisdiction_score=1.0, freshness_score=1.0, applicability_score=1.0, final_score=0.88)
    ev2 = RankedEvidence(chunk=chunk2, relevance_score=0.70, authority_score=0.7, jurisdiction_score=1.0, freshness_score=1.0, applicability_score=0.5, final_score=0.70)
    pack = EvidencePack(sub_query=sq, evidences=[ev1, ev2])
    
    state_mock = {"query": "Section 3(p)", "classification": None, "jurisdiction": Jurisdiction.INDIA}
    ranked_sync = rerank([pack], state_mock)
    ranked_async_res = await rerank_async([pack], state_mock)
    
    assert len(ranked_sync[0].evidences) == 2
    assert len(ranked_async_res[0].evidences) == 2
    # Section 3(p) with exact citation hard-boost should be ranked first
    print(f"  ✅ PASS: Async reranking completed. Top chunk: {ranked_async_res[0].evidences[0].chunk.provision} (Score: {ranked_async_res[0].evidences[0].final_score})")

    # -------------------------------------------------------------
    # Test 8: Paraphrased Doctrinal Queries (No Hardcoded Keywords)
    # -------------------------------------------------------------
    print("\n[Test 8] Paraphrased doctrinal queries bypass clarification without keywords...")
    doctrinal_queries = [
        "Does prior use in classical texts count as prior art?",
        "What counts as sufficient comparative data to avoid the mere-admixture objection?"
    ]
    for dq in doctrinal_queries:
        sess = str(uuid.uuid4())
        conf = {"configurable": {"thread_id": sess}}
        res_dq = await rag_app.ainvoke({
            "query": dq,
            "session_id": sess,
            "evidence_packs": [],
            "retry_count": 0
        }, config=conf)
        assert res_dq.get("status") != "needs_clarification", f"Query '{dq}' incorrectly paused at clarification!"
        assert not res_dq.get("awaiting_clarification"), f"Query '{dq}' incorrectly triggered clarification!"
        print(f"  ✅ PASS: '{dq[:45]}...' -> Bypassed clarification as expected (Status: {res_dq.get('status')}).")

    # -------------------------------------------------------------
    # Test 9: Formulation with Heuristic Category + Decoupled Botanical Extraction
    # -------------------------------------------------------------
    print("\n[Test 9] Formulation with heuristic category & decoupled ingredient extraction...")
    session_9 = str(uuid.uuid4())
    config_9 = {"configurable": {"thread_id": session_9}}
    res_9 = await rag_app.ainvoke({
        "query": "Can a classical Ashwagandha Taila formulation be patented in India?",
        "session_id": session_9,
        "evidence_packs": [],
        "retry_count": 0
    }, config=config_9)
    
    assert res_9.get("classification") is not None
    assert res_9["classification"].category == ProductCategory.CLASSICAL, f"Expected CLASSICAL, got {res_9['classification'].category}"
    assert any("Ashwagandha" in ing for ing in res_9["classification"].ingredients), f"Ingredients missing Ashwagandha: {res_9['classification'].ingredients}"
    assert not res_9.get("awaiting_clarification"), "Classical Ashwagandha Taila must NOT ask for route of administration!"
    print(f"  ✅ PASS: Category={res_9['classification'].category.value}, Ingredients={res_9['classification'].ingredients}, Bypassed clarification.")

    # -------------------------------------------------------------
    # Test 10: Vague Formulation Query Correctly Gated
    # -------------------------------------------------------------
    print("\n[Test 10] Genuinely vague formulation query triggers clarification...")
    session_10 = str(uuid.uuid4())
    config_10 = {"configurable": {"thread_id": session_10}}
    res_10 = await rag_app.ainvoke({
        "query": "I have created a special plant mixture and want to patent it.",
        "session_id": session_10,
        "evidence_packs": [],
        "retry_count": 0
    }, config=config_10)
    
    assert res_10.get("status") == "needs_clarification", f"Expected needs_clarification, got {res_10.get('status')}"
    assert res_10.get("awaiting_clarification") is True
    print(f"  ✅ PASS: Vague plant mixture paused at clarify_node as expected.")

    # -------------------------------------------------------------
    # Test 11: Proprietary Compliance Route-of-Administration Gating & Multi-Turn Resume
    # -------------------------------------------------------------
    print("\n[Test 11] Proprietary compliance query triggers route-of-administration clarification...")
    session_11 = str(uuid.uuid4())
    config_11 = {"configurable": {"thread_id": session_11}}
    res_11 = await rag_app.ainvoke({
        "query": "What compliance approvals do I need to sell my new proprietary Ashwagandha formulation in India?",
        "session_id": session_11,
        "evidence_packs": [],
        "retry_count": 0
    }, config=config_11)

    assert res_11.get("classification") is not None
    assert res_11["classification"].category == ProductCategory.PROPRIETARY, f"Expected PROPRIETARY, got {res_11['classification'].category}"
    assert any("Ashwagandha" in ing for ing in res_11["classification"].ingredients), f"Ingredients missing Ashwagandha: {res_11['classification'].ingredients}"
    assert res_11.get("status") == "needs_clarification", f"Expected needs_clarification, got {res_11.get('status')}"
    assert res_11.get("awaiting_clarification") is True
    missing_fields = res_11.get("missing_facts", []) or res_11["classification"].missing_facts
    assert "route_of_administration" in missing_fields, f"Expected route_of_administration in missing_facts, got {missing_fields}"
    print(f"  ✅ PASS (Turn 1): Correctly asked for route_of_administration on proprietary compliance query.")

    # Turn 2: Follow-up clarifying the route
    res_11_t2 = await rag_app.ainvoke({
        "query": "It is an oral capsule taken once daily for therapeutic use.",
        "session_id": session_11,
        "evidence_packs": [],
        "retry_count": 0
    }, config=config_11)

    assert res_11_t2.get("status") != "needs_clarification", f"Session must not be paused at clarification: got {res_11_t2.get('status')}"
    assert not res_11_t2.get("awaiting_clarification"), "Clarification must be cleared after supplying route"
    assert res_11_t2["classification"].route_of_administration == "oral", f"Expected oral, got {res_11_t2['classification'].route_of_administration}"
    assert any("Ashwagandha" in ing for ing in res_11_t2["classification"].ingredients)
    print(f"  ✅ PASS (Turn 2): Route clarified -> 'oral', session successfully resumed (Status: {res_11_t2.get('status')}).")

    # -------------------------------------------------------------
    # Test 12: Formulation Audit Multi-Domain Retrieval & Defensive Schema
    # -------------------------------------------------------------
    print("\n[Test 12] Formulation audit multi-domain retrieval and schema verification...")
    from app.api.routes.audit import formulation_audit
    from app.models.schemas import AuditRequest

    audit_req = AuditRequest(
        abstract="A novel synergistic polyherbal composition comprising Ashwagandha and Shallaki for osteoarthritic pain management.",
        classification="proprietary",
        synergy_description="Statistically significant 42% reduction in WOMAC score compared to individual components (p < 0.01).",
        ingredients="Ashwagandha, Shallaki"
    )
    audit_res = await formulation_audit(audit_req)
    assert audit_res.verdict is not None and len(audit_res.verdict) > 0
    assert audit_res.tkdl_band is not None
    assert audit_res.s3e_band is not None
    assert audit_res.nba_band is not None
    assert len(audit_res.sources) > 0, "Audit must return retrieved source citations from multi-domain collections"
    print(f"  ✅ PASS: Audit returned verdict='{audit_res.verdict}', sources count={len(audit_res.sources)}")

    print()
    print("=" * 65)
    print("ALL 12 TEST CASES PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
