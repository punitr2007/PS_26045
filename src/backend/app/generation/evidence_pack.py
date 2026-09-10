from typing import List, Tuple, Dict, Any
from collections import defaultdict
from app.schemas.pipeline import EvidencePack, RankedEvidence


def canonical_doc_info(chunk) -> Tuple[str, str, str, str]:
    """
    Extracts canonical (document_title, source_authority, legal_area, source_url)
    for a chunk so all provisions from the same statute/act are unified under
    a single parent document rather than scattered per section.
    """
    prov = getattr(chunk, "provision", "") or getattr(chunk, "node_title", "")
    title = getattr(chunk, "title", "")
    source_auth = getattr(chunk, "source_authority", "") or ""
    legal_area = getattr(chunk, "legal_area", "") or ""
    chunk_id = getattr(chunk, "chunk_id", "")

    low_text = f"{prov} {title} {source_auth} {chunk_id}".lower()

    # Determine canonical document title
    if "patent" in low_text or "pat-" in low_text or "3(p)" in low_text or "3(e)" in low_text or "3(d)" in low_text:
        doc_title = "The Patents Act, 1970"
        authority = "Office of the Controller General of Patents, Designs & Trade Marks (CGPDTM)"
        area = legal_area or "Patentability Exclusions & Traditional Knowledge"
        url = "https://ipindia.gov.in/writereaddata/Portal/IPOAct/1_31_1_patent-act-1970-11march2015.pdf"
    elif "biodiversity" in low_text or "bda" in low_text or "nba" in low_text or "abs" in low_text:
        doc_title = "The Biological Diversity Act, 2002"
        authority = "National Biodiversity Authority (NBA) · MoEFCC"
        area = legal_area or "Access & Benefit Sharing (ABS) Clearance"
        url = "https://nba.gov.in/content/biological_diversity_act.html"
    elif "drugs and cosmetics" in low_text or "d&c" in low_text or "158b" in low_text or "ayush" in low_text:
        doc_title = "The Drugs and Cosmetics Act, 1940 & Rules 1945"
        authority = "Ministry of AYUSH / Central Drugs Standard Control Organisation"
        area = legal_area or "Manufacturing Licensing & Regulatory Standards"
        url = getattr(chunk, "source_url", "") or "https://ayush.gov.in"
    elif "tkdl" in low_text:
        doc_title = "Traditional Knowledge Digital Library (TKDL)"
        authority = "Council of Scientific & Industrial Research (CSIR)"
        area = legal_area or "Prior Art & Classical Formulation Citations"
        url = getattr(chunk, "source_url", "") or "https://www.tkdl.res.in"
    else:
        # Fallback to source authority or title if available
        doc_title = source_auth or title or "Statutory Document"
        authority = source_auth or "Official Statutory Authority"
        area = legal_area or "Indian Regulatory Framework"
        url = getattr(chunk, "source_url", "") or ""

    return doc_title, authority, area, url


def merge(evidence_packs: List[EvidencePack], top_n_total: int = 8) -> Tuple[str, List[RankedEvidence]]:
    """
    Merges and formats the highest-scoring RankedEvidence objects from 
    all evidence packs into a structured, document-grouped context string
    for the LLM prompt.
    
    All chunks from the same document are consolidated under a SINGLE document
    header, with individual sections/provisions listed sequentially one below another.
    """
    # 1. Flatten all ranked evidences
    all_evidences = []
    for pack in evidence_packs:
        all_evidences.extend(pack.evidences)

    # 2. Deduplicate by chunk_id — keep the instance with the highest final_score
    seen_ids: dict = {}
    for ev in all_evidences:
        cid = ev.chunk.chunk_id
        if cid not in seen_ids or ev.final_score > seen_ids[cid].final_score:
            seen_ids[cid] = ev
    deduped_evidences = list(seen_ids.values())

    # 3. Sort globally by final_score, breaking ties deterministically
    deduped_evidences.sort(
        key=lambda e: (
            round(e.final_score, 4),
            round(e.relevance_score, 4),
            round(getattr(e.chunk, "vector_score", 0.0) or 0.0, 4)
        ),
        reverse=True
    )
    
    # 4. Take top N highest-scoring evidence chunks
    top_evidences = deduped_evidences[:top_n_total]
    
    # 5. Group evidences strictly by parent document to prevent scattered/duplicated document headers
    grouped_docs: Dict[str, List[RankedEvidence]] = defaultdict(list)
    doc_order: List[str] = []
    doc_metadata: Dict[str, Tuple[str, str, str, str]] = {}

    for evidence in top_evidences:
        chunk = evidence.chunk
        doc_title, authority, area, url = canonical_doc_info(chunk)
        doc_key = doc_title.lower().strip()
        
        if doc_key not in grouped_docs:
            doc_order.append(doc_key)
            doc_metadata[doc_key] = (doc_title, authority, area, url)
        grouped_docs[doc_key].append(evidence)

    # 6. Format into consolidated document blocks: Document details once, provisions stacked below
    context_blocks = []
    for doc_key in doc_order:
        doc_title, authority, area, _ = doc_metadata[doc_key]
        ev_list = grouped_docs[doc_key]

        # Document details rendered ONLY ONCE
        doc_header = f"### [DOCUMENT: {doc_title} | Authority: {authority} | Legal Framework: {area}]"
        
        # Sections and provisions listed sequentially one below another
        provision_blocks = []
        for idx, ev in enumerate(ev_list, 1):
            c = ev.chunk
            prov = getattr(c, "provision", "") or getattr(c, "title", f"Section {idx}")
            pages_str = f", Pages: {c.pages}" if c.pages and c.pages != "?" else ""
            chapter_str = f", Chapter: {c.chapter}" if getattr(c, "chapter", "") and c.chapter != "N/A" else ""
            
            excerpt_header = f"• [Provision: {prov} | Ref: {c.chunk_id}{chapter_str}{pages_str}]"
            provision_blocks.append(f"{excerpt_header}\n{c.text.strip()}")

        block = f"{doc_header}\n" + "\n\n".join(provision_blocks)
        context_blocks.append(block)
        
    return "\n\n---\n\n".join(context_blocks), top_evidences


def format_sources(top_evidences: List[RankedEvidence], max_sources: int = 8) -> List[Dict[str, Any]]:
    """
    Consolidates multiple chunks from the same document into a single source citation
    dictionary. Document metadata is presented only once, with all cited provisions,
    chunk IDs, and excerpts collected one below another.
    """
    if not top_evidences:
        return []

    grouped: Dict[str, Dict[str, Any]] = {}
    ordered_keys: List[str] = []

    for evidence in top_evidences:
        chunk = evidence.chunk
        doc_title, authority, area, default_url = canonical_doc_info(chunk)
        doc_key = doc_title.lower().strip()

        prov = getattr(chunk, "provision", "") or getattr(chunk, "section", "") or getattr(chunk, "node_title", "")
        title = getattr(chunk, "title", "")
        clean_prov = prov or title or "Statutory Provision"

        chunk_text = getattr(chunk, "text", "") or ""
        clean_text = chunk_text.strip()
        source_url = getattr(chunk, "source_url", None) or default_url

        if doc_key not in grouped:
            ordered_keys.append(doc_key)
            grouped[doc_key] = {
                "id": chunk.chunk_id,  # Primary ID for statute reader linking
                "doc_id": doc_key,
                "title": doc_title,
                "provision": clean_prov,
                "provisions": [clean_prov] if clean_prov else [],
                "chapter": getattr(chunk, "chapter", None),
                "pages": getattr(chunk, "pages", None),
                "source_url": source_url,
                "breadcrumb": getattr(chunk, "breadcrumb", None),
                "clause_id": getattr(chunk, "clause_id", None),
                "span_start": getattr(chunk, "span_start", None),
                "span_end": getattr(chunk, "span_end", None),
                "source_authority": authority,
                "document_type": getattr(chunk, "document_type", None) or "Principal Statutory Enactment",
                "legal_area": area,
                "text": clean_text[:1200] if clean_text else None,
                "excerpts": [clean_text[:600]] if clean_text else [],
                "chunk_ids": [chunk.chunk_id],
                "chunk_count": 1,
                "sections": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "provision": clean_prov,
                        "title": title,
                        "text": clean_text,
                        "pages": getattr(chunk, "pages", None),
                        "chapter": getattr(chunk, "chapter", None),
                    }
                ],
            }
        else:
            # Aggregate under existing parent document citation
            existing = grouped[doc_key]
            
            # Add chunk ID if not seen
            if chunk.chunk_id not in existing["chunk_ids"]:
                existing["chunk_ids"].append(chunk.chunk_id)
                existing["chunk_count"] += 1

            # Accumulate provisions
            if clean_prov and clean_prov not in existing["provisions"]:
                existing["provisions"].append(clean_prov)
                existing["provision"] = ", ".join(existing["provisions"])

            # Accumulate excerpts
            if clean_text and clean_text[:600] not in existing.get("excerpts", []):
                existing.setdefault("excerpts", []).append(clean_text[:600])

            # Append structured section
            existing.setdefault("sections", []).append({
                "chunk_id": chunk.chunk_id,
                "provision": clean_prov,
                "title": title,
                "text": clean_text,
                "pages": getattr(chunk, "pages", None),
                "chapter": getattr(chunk, "chapter", None),
            })

            # Combine pages if distinct
            p = getattr(chunk, "pages", None)
            if p and p != "?" and p not in (existing.get("pages") or ""):
                if existing.get("pages") and existing["pages"] != "?":
                    existing["pages"] = f"{existing['pages']}, {p}"
                else:
                    existing["pages"] = p

    sources = [grouped[k] for k in ordered_keys]
    return sources[:max_sources]
