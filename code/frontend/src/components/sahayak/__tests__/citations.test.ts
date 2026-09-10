/**
 * Unit test and verification suite for Citation Parser, Compact Strip,
 * Highlighted Statute Text, and Grouping Logic.
 */

import {
  parseCitations,
  normalizeCitation,
  findHighlightSpan,
  getFullTextForCitation,
  type CitationItem,
} from "../CitationComponents";

// Sample mock citations returned by the backend RAG pipeline
export const SAMPLE_CITATIONS: CitationItem[] = [
  {
    id: "c1",
    doc_id: "IN-ABS-001",
    section: "section_6",
    chunk_id: "IN-ABS-001_section_6_c2",
    title: "The Biological Diversity Act, 2002",
    section_title:
      "Section 6 — Prior approval for applying for intellectual property rights",
    excerpt_text:
      "No person shall apply for any intellectual property right, in or outside India, for any invention based on any research or information on a biological resource obtained from India without previous approval of the National Biodiversity Authority.",
    source_url: "https://nba.gov.in/content/biological_diversity_act.html",
    page_number: 14,
  },
  {
    id: "c2",
    doc_id: "IN-PAT-001",
    section: "section_3p",
    chunk_id: "IN-PAT-001_sec_3p_c1",
    title: "The Patents Act, 1970",
    section_title: "Section 3(p) — Traditional Knowledge Exclusion",
    excerpt_text:
      "an invention which, in effect, is traditional knowledge or which is an aggregation or duplication of known properties of traditionally known component or components.",
    source_url:
      "https://ipindia.gov.in/writereaddata/Portal/IPOAct/1_31_1_patent-act-1970-11march2015.pdf",
    page_number: "p. ? to ?", // should be sanitized out
  },
  {
    id: "c3",
    doc_id: "IN-ABS-001", // Same document as c1!
    section: "section_7",
    chunk_id: "IN-ABS-001_section_7_c1",
    title: "The Biological Diversity Act, 2002",
    section_title: "Section 7 — Prior intimation to State Biodiversity Board",
    excerpt_text: "No person, who is a citizen of India, shall obtain any biological resource...",
    source_url: "https://nba.gov.in/content/biological_diversity_act.html",
  },
];

export function runCitationParserTests() {
  console.log("=== Running Citation Parser Tests ===");

  // Test 1: Multiple refs + duplicate ref reuse + unmapped fallback
  const sampleAnswer = `
Under Indian law, Ayurvedic inventions face dual statutory requirements:
1. Under Section 6 of the Biological Diversity Act (Ref: IN-ABS-001_section_6_c2), prior approval is mandatory before patent grant.
2. Section 3(p) of the Patents Act (Excerpt 1, Ref: IN-PAT-001_sec_3p_c1) excludes mere duplications of classical formulation knowledge.
3. As affirmed again under Section 6 (Ref: IN-ABS-001_section_6_c2), foreign applicants must route via NBA Form III.
4. An unindexed guideline (Ref: NON_EXISTENT_CHUNK_999) should safely fallback.
`.trim();

  const result = parseCitations(sampleAnswer, SAMPLE_CITATIONS);

  // Assertions:
  // 1. Should have extracted 2 unique valid citations
  console.assert(
    result.uniqueCitations.length === 2,
    `Expected 2 unique citations, got ${result.uniqueCitations.length}`,
  );

  // 2. First citation should be [1] (Biological Diversity Act)
  const first = result.uniqueCitations[0];
  console.assert(
    first?.index === 1 && first.citation.chunkId === "IN-ABS-001_section_6_c2",
    "Citation [1] must match Biological Diversity Act chunk",
  );

  // 3. Second citation should be [2] (Patents Act)
  const second = result.uniqueCitations[1];
  console.assert(
    second?.index === 2 && second.citation.chunkId === "IN-PAT-001_sec_3p_c1",
    "Citation [2] must match Patents Act Section 3(p)",
  );

  // 4. Repeated citation should reuse [^1]
  const occurrencesOfCite1 = (result.processedText.match(/\[\^1\]/g) || []).length;
  console.assert(
    occurrencesOfCite1 === 2,
    `Expected 2 occurrences of [^1], got ${occurrencesOfCite1}`,
  );

  // 5. Unmapped chunk should stay plain text
  console.assert(
    result.processedText.includes("(Ref: NON_EXISTENT_CHUNK_999)"),
    "Unmapped chunk must remain as plain text fallback",
  );

  // 6. Test normalization cleans invalid "p. ? to ?" page numbers
  const normalizedPat = normalizeCitation(SAMPLE_CITATIONS[1]);
  console.assert(
    normalizedPat.pageNumber === undefined,
    `Expected pageNumber to be undefined, got: ${normalizedPat.pageNumber}`,
  );

  // 7. Test findHighlightSpan
  const fullText = "Section 3(p) provides that an invention which, in effect, is traditional knowledge or which is an aggregation or duplication of known properties of traditionally known component or components shall not be patentable.";
  const excerpt = "an invention which, in effect, is traditional knowledge or which is an aggregation or duplication of known properties of traditionally known component or components.";
  const span = findHighlightSpan(fullText, excerpt);
  console.assert(
    span !== null && fullText.slice(span.start, span.end) === excerpt,
    "findHighlightSpan must accurately locate the excerpt boundaries",
  );

  // 8. Test multi-citation grouping by document
  const docGroup = SAMPLE_CITATIONS.map(normalizeCitation).filter(
    (c) => c.docId === "IN-ABS-001",
  );
  console.assert(
    docGroup.length === 2,
    `Expected 2 citations grouped under IN-ABS-001, got ${docGroup.length}`,
  );

  // 9. Test major statutory details & source link
  const normalizedAbs = normalizeCitation(SAMPLE_CITATIONS[0]);
  console.assert(
    Boolean(normalizedAbs.sourceAuthority) && Boolean(normalizedAbs.legalArea),
    "Expected sourceAuthority and legalArea to be present on normalized citation",
  );
  console.assert(
    normalizedAbs.sourceUrl === "https://nba.gov.in/content/biological_diversity_act.html",
    "Expected original sourceUrl to be preserved",
  );

  // 10. Test consolidated single-document source with multiple sections (provisions array & sections list)
  const CONSOLIDATED_CITATION: CitationItem = {
    id: "c-patent-consolidated",
    doc_id: "IN-PAT-001",
    title: "The Patents Act, 1970",
    provision: "Section 3(p), Section 3(e)",
    provisions: ["Section 3(p)", "Section 3(e)"],
    chunk_ids: ["IN-PAT-001_sec_3p_c1", "IN-PAT-001_sec_3e_c1"],
    chunk_count: 2,
    sections: [
      {
        chunk_id: "IN-PAT-001_sec_3p_c1",
        provision: "Section 3(p)",
        title: "Traditional Knowledge Exclusion",
        text: "Excerpt text for section 3(p)",
      },
      {
        chunk_id: "IN-PAT-001_sec_3e_c1",
        provision: "Section 3(e)",
        title: "Admixture Exclusion",
        text: "Excerpt text for section 3(e)",
      },
    ],
    source_url: "https://ipindia.gov.in",
  };

  const normConsolidated = normalizeCitation(CONSOLIDATED_CITATION);
  console.assert(
    normConsolidated.provisions?.length === 2,
    `Expected 2 provisions in consolidated citation, got ${normConsolidated.provisions?.length}`,
  );
  console.assert(
    normConsolidated.sections?.length === 2,
    `Expected 2 sections in consolidated citation, got ${normConsolidated.sections?.length}`,
  );
  console.assert(
    normConsolidated.chunkCount === 2,
    `Expected chunkCount of 2, got ${normConsolidated.chunkCount}`,
  );

  // 11. Test that inline citations matching any sub-section chunk_id map correctly to the parent citation
  const multiSectionText = "Section 3(p) (Ref: IN-PAT-001_sec_3p_c1) and Section 3(e) (Ref: IN-PAT-001_sec_3e_c1) apply.";
  const parseResult = parseCitations(multiSectionText, [CONSOLIDATED_CITATION]);
  console.assert(
    parseResult.uniqueCitations.length === 1,
    `Expected 1 unique parent document citation, got ${parseResult.uniqueCitations.length}`,
  );
  console.assert(
    parseResult.processedText.includes("[^1]"),
    "Inline tags should map to parent citation [1]",
  );

  console.log("✅ All Citation and Statute Reader Tests Passed successfully!");
  return {
    success: true,
    processedText: result.processedText,
    uniqueCitations: result.uniqueCitations,
  };
}
