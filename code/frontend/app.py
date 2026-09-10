"""
🌿 IP-SAKTI Sahayak — Legal & Regulatory Intelligence Frontend
==============================================================
Streamlit UI for Ayurvedic Intellectual Property, Biodiversity ABS,
and Drug/Food/Cosmetic Regulatory Compliance.

Key UX Improvements:
- Answer-first display: Preliminary legal analysis is shown before clarification chips
- Interactive clarification chips: Single-click radio buttons, not text prompts
- Rich structured layout: Tables, dual-pathway sections, citation drawers
- Connects to FastAPI LangGraph backend on port 8001
"""

import streamlit as st
import requests
import uuid
from typing import Dict, Any, List, Optional

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IP-SAKTI Sahayak | Ayurvedic Legal Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom Styling ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1b4332;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    .sub-title {
        font-size: 1rem;
        color: #52b788;
        margin-bottom: 1.8rem;
    }
    .source-card {
        background: linear-gradient(135deg, #f8fffe 0%, #f0faf5 100%);
        border-left: 4px solid #2d6a4f;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-radius: 6px;
        font-size: 0.88rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .chip-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 12px 0;
    }
    .refine-banner {
        background: linear-gradient(135deg, #fffbeb 0%, #fef9c3 100%);
        border: 1px solid #fbbf24;
        border-radius: 8px;
        padding: 14px 18px;
        margin-top: 12px;
    }
    .refine-title {
        font-weight: 600;
        color: #92400e;
        margin-bottom: 6px;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Backend Configuration ─────────────────────────────────────────────────────
BACKEND_BASE_URL = "http://localhost:8001"
CHAT_ENDPOINT = f"{BACKEND_BASE_URL}/api/v1/chat"
HEALTH_ENDPOINT = f"{BACKEND_BASE_URL}/api/v1/health"

# ── Session State Initialization ──────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_clarifications" not in st.session_state:
    st.session_state.pending_clarifications = None
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

# ── Helpers ───────────────────────────────────────────────────────────────────
def check_health() -> bool:
    try:
        return requests.get(HEALTH_ENDPOINT, timeout=2.0).status_code == 200
    except Exception:
        return False

def send_query(message: str, known_facts: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
    payload = {"session_id": st.session_state.session_id, "message": message, "top_k": 8}
    if known_facts:
        payload["known_facts"] = known_facts
    try:
        r = requests.post(CHAT_ENDPOINT, json=payload, timeout=200.0)
        return r.json() if r.status_code == 200 else None
    except requests.exceptions.ConnectionError:
        st.error("❌ Backend is offline. Run: `uvicorn app.main:app --port 8001 --reload`")
        return None
    except requests.exceptions.Timeout:
        st.error("⏳ LLM inference timed out. The model may be busy.")
        return None

def render_sources(sources: List[Dict]):
    if not sources:
        return
    with st.expander(f"📚 Grounded Legal Provisions ({len(sources)} cited)", expanded=False):
        for src in sources:
            st.markdown(f"""
            <div class="source-card">
                <b>📌 {src.get('provision', 'N/A')} — {src.get('title', 'N/A')}</b><br/>
                <small>
                    📖 <b>Chapter:</b> {src.get('chapter', 'N/A')} &nbsp;|&nbsp;
                    📄 <b>Pages:</b> {src.get('pages', 'N/A')} &nbsp;|&nbsp;
                    🏛️ <b>Authority:</b> {src.get('id', 'N/A')}
                </small>
            </div>
            """, unsafe_allow_html=True)

def render_clarification_chips(questions: List[Dict], known_facts: Dict):
    """
    Renders interactive clarification chips below the preliminary answer.
    Uses a compact form with radio buttons — one click submits the refinement.
    """
    st.markdown("""
    <div class="refine-banner">
        <div class="refine-title">🔍 Refine for Your Specific Case</div>
        Answer below to get a targeted statutory analysis for your exact product:
    </div>
    """, unsafe_allow_html=True)

    with st.form(key=f"clarify_form_{st.session_state.session_id[:8]}"):
        collected = {}
        cols = st.columns(min(len(questions), 3))
        for i, q in enumerate(questions):
            field = q.get("field", f"field_{i}")
            question_text = q.get("question", "Please specify:")
            options = q.get("options") or []
            col = cols[i % len(cols)]
            with col:
                if options:
                    st.markdown(f"**{question_text}**")
                    collected[field] = st.radio(
                        label=question_text,
                        options=options,
                        label_visibility="collapsed",
                        key=f"chip_{field}"
                    )
                else:
                    collected[field] = st.text_input(
                        label=question_text,
                        key=f"chip_text_{field}"
                    )

        submitted = st.form_submit_button("🚀 Get Precise Statutory Analysis", use_container_width=True)
        if submitted:
            summary = ", ".join(f"{k}: {v}" for k, v in collected.items() if v)
            st.session_state.messages.append({"role": "user", "content": f"Refinement: {summary}"})
            st.session_state.pending_clarifications = None

            # Merge clarification answers into known_facts
            merged_facts = {**known_facts}
            for field, val in collected.items():
                # Map option text back to structured fact values
                v = val.lower()
                if field == "category":
                    if "classical" in v: merged_facts["category"] = "classical"
                    elif "proprietary" in v: merged_facts["category"] = "proprietary"
                    elif "phyto" in v: merged_facts["category"] = "phytopharmaceutical"
                    elif "aahar" in v or "food" in v: merged_facts["category"] = "ayurveda_aahar"
                    elif "cosmetic" in v: merged_facts["category"] = "cosmetic"
                elif field == "route_of_administration":
                    if "oral" in v: merged_facts["route_of_administration"] = "oral"
                    elif "topical" in v or "external" in v: merged_facts["route_of_administration"] = "external"
                elif field == "intended_use":
                    if "therapeutic" in v or "medicinal" in v: merged_facts["intended_use"] = "medicine"
                    elif "food" in v or "supplement" in v: merged_facts["intended_use"] = "food"
                    elif "cosmetic" in v: merged_facts["intended_use"] = "cosmetic"
                elif field == "jurisdiction":
                    merged_facts["jurisdiction"] = "india" if "india" in v else "international"

            # Find the original query from conversation history for complete context
            original_query = ""
            for msg in reversed(st.session_state.messages[:-1]):
                if msg.get("role") == "user" and not msg.get("content", "").startswith("Refinement:"):
                    original_query = msg.get("content", "")
                    break
            
            combined_query = f"{original_query} (Refinement: {summary})" if original_query else summary

            with st.spinner("🧠 Generating precise statutory analysis..."):
                resp = send_query(combined_query, known_facts=merged_facts)
                if resp:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": resp.get("answer", ""),
                        "sources": resp.get("sources", []),
                        "status": resp.get("status", "answered"),
                        "questions": resp.get("questions")
                    })
                    if resp.get("status") == "needs_clarification" and resp.get("questions"):
                        st.session_state.pending_clarifications = resp["questions"]
            st.rerun()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌿 IP-SAKTI Sahayak")
    st.caption("Ayurvedic & Traditional Knowledge Legal Intelligence")

    if check_health():
        st.success("🟢 Backend Connected (Port 8001)")
    else:
        st.error("🔴 Backend Offline")
        st.code("uvicorn app.main:app --port 8001 --reload", language="bash")

    st.divider()

    st.markdown("### 💬 Session")
    st.code(st.session_state.session_id[:8] + "...", language="text")
    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.pending_clarifications = None
        st.rerun()

    st.divider()

    # Ground Truth Panel
    st.markdown("### 📋 Formulation Pre-Seeding")
    st.caption("Bypass auto-classification by specifying known facts:")

    use_facts = st.checkbox("Enable Pre-Seeding", value=False)
    known_facts: Dict[str, Any] = {}

    if use_facts:
        jur = st.selectbox("Jurisdiction", ["India", "International (PCT / US / EPO)"])
        known_facts["jurisdiction"] = "india" if "India" in jur else "international"

        cat = st.selectbox("Product Category", [
            "Auto-detect",
            "Classical (Ayurvedic Pharmacopoeia / TKDL)",
            "Proprietary Medicine (Novel Combination)",
            "Standardized Phytopharmaceutical",
            "Ayurveda Aahar (Dietary / Food)",
            "Ayurvedic Cosmetic (Topical)"
        ])
        cat_map = {
            "Classical": "classical", "Proprietary": "proprietary",
            "Phytopharmaceutical": "phytopharmaceutical",
            "Aahar": "ayurveda_aahar", "Cosmetic": "cosmetic"
        }
        for k, v in cat_map.items():
            if k in cat:
                known_facts["category"] = v
                break

        route = st.selectbox("Route of Administration", [
            "Auto-detect", "Oral (Tablet/Syrup/Kwatha)", "Topical/External (Cream/Lepa/Oil)"
        ])
        if "Oral" in route:
            known_facts["route_of_administration"] = "oral"
        elif "Topical" in route:
            known_facts["route_of_administration"] = "external"

    st.divider()

    # Quick Query Samples
    st.markdown("### 💡 Sample Queries")
    SAMPLES = [
        ("🧴 Ashwagandha Cream Limits", "What heavy metal limits and labelling rules apply to an Ayurvedic herbal anti-aging cream containing Ashwagandha?"),
        ("⚖️ Patentability Section 3(p)", "Is a novel synergistic blend of Ashwagandha and Curcumin patentable under Section 3(p) of the Patents Act?"),
        ("🍃 FSSAI Aahar Labelling", "What are the mandatory labelling requirements under FSSAI Ayurveda Aahar Regulations 2022?"),
        ("🌿 NBA Biodiversity Clearance", "Do foreign companies need NBA approval under the Biological Diversity Act before filing a patent in India?"),
    ]
    for label, query in SAMPLES:
        if st.button(label, use_container_width=True):
            st.session_state.pending_query = query
            st.rerun()

# ── Main UI ───────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🌿 IP-SAKTI Sahayak</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Statutory Legal Research · Indian Ayurvedic IP · Drug Licensing · Biodiversity Compliance</div>', unsafe_allow_html=True)

# ── Render Chat History ───────────────────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            render_sources(msg["sources"])

# ── Pending Clarification Chips (bottom of history) ──────────────────────────
# Show chips only for the LAST assistant message, not for all history
if st.session_state.pending_clarifications:
    render_clarification_chips(
        st.session_state.pending_clarifications,
        known_facts if use_facts else {}
    )

# ── Handle Sample Query Click ─────────────────────────────────────────────────
query_to_run = None
if st.session_state.pending_query:
    query_to_run = st.session_state.pending_query
    st.session_state.pending_query = None

# ── Chat Input ────────────────────────────────────────────────────────────────
user_input = st.chat_input(
    "Ask about Ayurvedic patents, heavy metal limits, NBA clearance, FSSAI Aahar rules..."
)
final_query = user_input or query_to_run

if final_query:
    st.session_state.pending_clarifications = None
    st.session_state.messages.append({"role": "user", "content": final_query})
    with st.chat_message("user"):
        st.markdown(final_query)

    with st.chat_message("assistant"):
        with st.spinner("🧠 Querying statutory corpus via LangGraph RAG pipeline..."):
            resp = send_query(final_query, known_facts=known_facts if use_facts else None)

        if resp:
            status = resp.get("status", "answered")
            answer = resp.get("answer", "")
            sources = resp.get("sources", [])
            questions = resp.get("questions") or []

            st.markdown(answer)
            render_sources(sources)

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "status": status
            })

            if status == "needs_clarification" and questions:
                st.session_state.pending_clarifications = questions
                st.rerun()
