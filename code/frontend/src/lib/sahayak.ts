export type Jurisdiction = "national" | "international";

export type SourceTag = {
  id: string;
  label: string;
  statute: StatuteId;
  // Enhanced fields from Stage 2 backend — explicitly unioned with undefined
  // to satisfy exactOptionalPropertyTypes in tsconfig.
  clauseId?: string | undefined;
  spanStart?: number | undefined;
  spanEnd?: number | undefined;
  sourceUrl?: string | undefined;
  breadcrumb?: string | undefined;
  title?: string | undefined;
  provision?: string | undefined;
  chapter?: string | undefined;
  pages?: string | undefined;
  sourceAuthority?: string | undefined;
  documentType?: string | undefined;
  legalArea?: string | undefined;
  text?: string | undefined;
  excerpts?: string[] | undefined;
};

// "unmapped" is a safe sentinel — renders with dynamic legal excerpt in Statute Reader
export type StatuteId =
  "patents-3p" | "patents-3e" | "patents-3d" | "bda-6" | "nba-form-iii" | "unmapped";

// Backend API types — mirror app/models/schemas.py
export type BackendSourceCitation = {
  id: string;
  provision: string;
  title: string;
  chapter?: string | null;
  pages?: string | null;
  source_url?: string | null;
  breadcrumb?: string | null;
  statute_id?: string | null;
  clause_id?: string | null;
  span_start?: number | null;
  span_end?: number | null;
  source_authority?: string | null;
  document_type?: string | null;
  legal_area?: string | null;
  text?: string | null;
  excerpts?: string[] | null;
  chunk_ids?: string[] | null;
  chunk_count?: number | null;
};

export type ClarificationQuestion = {
  field: string;
  question: string;
  options?: string[];
};

export type BackendChatResponse = {
  session_id: string;
  answer: string;
  sources: BackendSourceCitation[];
  turn_index: number;
  timestamp: string;
  status: "answered" | "abstained" | "needs_clarification";
  questions?: ClarificationQuestion[];
};

export type BackendAuditResponse = {
  verdict: "Likely Blocked" | "Borderline — Needs Evidence" | "Reasonably Viable";
  tkdl_band: string;
  s3e_band: string;
  nba_band: string;
  analysis: string;
  sources: BackendSourceCitation[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: SourceTag[];
  createdAt: number;
};

export type Conversation = {
  id: string;
  title: string;
  emoji: string;
  updatedAt: number;
  messages: ChatMessage[];
};

export type StatuteMeta = {
  documentTitle: string;
  productCategory: string;
  articlesCovered: string;
  publicationDate: string;
  effectiveFrom: string;
  effectiveUntil: string;
  status: string;
  supersedes: string;
  sourceUrl: string;
};

export const STATUTES: Record<
  StatuteId,
  { title: string; sourceId: string; meta: StatuteMeta; body: string[] }
> = {
  "patents-3p": {
    title: "Patents Act, 1970 — Section 3(p)",
    sourceId: "L0-IN-PAT-3P",
    meta: {
      documentTitle:
        "The Patents Act, 1970 (Act No. 39 of 1970) — incorporating all amendments till 01-08-2024",
      productCategory: "Classical ASU formulations · Traditional knowledge derived products",
      articlesCovered: "Chapter II, Section 3(p)",
      publicationDate: "19 September 1970",
      effectiveFrom: "20 April 1972",
      effectiveUntil: "Currently in force",
      status: "In force",
      supersedes:
        "Clause (p) inserted by the Patents (Amendment) Act, 2002 (38 of 2002), s. 4 (w.e.f. 20-05-2003)",
      sourceUrl:
        "https://ipindia.gov.in/writereaddata/Portal/IPOAct/1_31_1_patent-act-1970-11march2015.pdf",
    },
    body: [
      "3. What are not inventions.— The following are not inventions within the meaning of this Act,—",
      "(p) an invention which, in effect, is traditional knowledge or which is an aggregation or duplication of known properties of traditionally known component or components.",
      "Practice note: Examiners routinely cite Traditional Knowledge Digital Library (TKDL) records as prior art under this clause for classical ASU formulations.",
    ],
  },
  "patents-3e": {
    title: "Patents Act, 1970 — Section 3(e)",
    sourceId: "L0-IN-PAT-3E",
    meta: {
      documentTitle:
        "The Patents Act, 1970 (Act No. 39 of 1970) — incorporating all amendments till 01-08-2024",
      productCategory: "Proprietary combinations · Polyherbal admixtures · Nutraceuticals",
      articlesCovered: "Chapter II, Section 3(e)",
      publicationDate: "19 September 1970",
      effectiveFrom: "20 April 1972",
      effectiveUntil: "Currently in force",
      status: "In force",
      supersedes: "Original clause (e) as enacted; unamended to date",
      sourceUrl:
        "https://ipindia.gov.in/writereaddata/Portal/IPOAct/1_31_1_patent-act-1970-11march2015.pdf",
    },
    body: [
      "(e) a substance obtained by a mere admixture resulting only in the aggregation of the properties of the components thereof or a process for producing such substance.",
      "Practice note: The bar is overcome only by comparative experimental data establishing synergy over the individual components, filed with or before examination.",
    ],
  },
  "patents-3d": {
    title: "Patents Act, 1970 — Section 3(d)",
    sourceId: "L0-IN-PAT-3D",
    meta: {
      documentTitle:
        "The Patents Act, 1970 (Act No. 39 of 1970) — incorporating all amendments till 01-08-2024",
      productCategory: "Phytopharmaceuticals · Isolated fractions · Novel extracts and nano-forms",
      articlesCovered: "Chapter II, Section 3(d) with Explanation",
      publicationDate: "19 September 1970",
      effectiveFrom: "20 April 1972",
      effectiveUntil: "Currently in force",
      status: "In force",
      supersedes:
        "Clause (d) substituted by the Patents (Amendment) Act, 2005 (15 of 2005), s. 3 (w.e.f. 01-01-2005)",
      sourceUrl:
        "https://ipindia.gov.in/writereaddata/Portal/IPOAct/1_31_1_patent-act-1970-11march2015.pdf",
    },
    body: [
      "(d) the mere discovery of a new form of a known substance which does not result in the enhancement of the known efficacy of that substance...",
      "Explanation.— salts, esters, ethers, polymorphs, metabolites, pure form, particle size, isomers... shall be considered to be the same substance, unless they differ significantly in properties with regard to efficacy.",
    ],
  },
  "bda-6": {
    title: "Biological Diversity Act, 2002 — Section 6 (with 2023 Amendment)",
    sourceId: "L0-IN-BDA-06",
    meta: {
      documentTitle:
        "The Biological Diversity Act, 2002 (Act No. 18 of 2003) — as amended by Act 31 of 2023",
      productCategory: "All products based on Indian biological resources · AYUSH · Ayurveda-Aahar",
      articlesCovered: "Section 6, read with Sections 3 and 7",
      publicationDate: "5 February 2003",
      effectiveFrom: "1 October 2003",
      effectiveUntil: "Currently in force",
      status: "In force (as amended)",
      supersedes:
        "Amended by the Biological Diversity (Amendment) Act, 2023 (31 of 2023) (w.e.f. 01-04-2024)",
      sourceUrl: "https://nba.gov.in/content/biological_diversity_act.html",
    },
    body: [
      "6(1) No person shall apply for any intellectual property right, in or outside India, for any invention based on any research or information on a biological resource obtained from India without the approval of the National Biodiversity Authority before the grant of the intellectual property right.",
      "Provided that the Authority approval may be obtained after the acceptance of the patent but before the sealing of the patent by the patent authority concerned.",
      "Read with Section 3 (foreign entities) and Section 7 (intimation to the State Biodiversity Board by Indian entities for commercial utilisation).",
    ],
  },
  "nba-form-iii": {
    title: "NBA Form III — Application for IPR (ABS Rules, 2025)",
    sourceId: "L1-IN-NBA-F3",
    meta: {
      documentTitle:
        "Biological Diversity (Access to Biological Resources and Knowledge Associated thereto and Fair and Equitable Sharing of Benefits) Regulation — Form III",
      productCategory:
        "Any invention seeking IPR over Indian biological resources or associated knowledge",
      articlesCovered: "Form III, particulars 1–9 (filed under Section 6(1))",
      publicationDate: "9 January 2025",
      effectiveFrom: "9 January 2025",
      effectiveUntil: "Currently in force",
      status: "In force",
      supersedes: "Supersedes Form III under the Biological Diversity Rules, 2004",
      sourceUrl: "https://nba.gov.in/content/formsandfee.html",
    },
    body: [
      "Form III is filed for approval under Section 6(1) for seeking IPR over an invention based on Indian biological resources.",
      "Required particulars: applicant details, title and abstract of the invention, biological resources used with quantity and source, geographical location of collection, and details of benefit-sharing offered.",
      "Benefit sharing under the ABS Rules, 2025 is levied on the basis of annual gross ex-factory sale, in the slabs notified by the Authority.",
    ],
  },
  // "unmapped" is a sentinel for citations the frontend can't reliably map to a known statute.
  // The Statute Reader never opens for unmapped citations — this entry satisfies the Record type.
  unmapped: {
    title: "Source Citation",
    sourceId: "unmapped",
    meta: {
      documentTitle: "Unknown source document",
      productCategory: "",
      articlesCovered: "",
      publicationDate: "",
      effectiveFrom: "",
      effectiveUntil: "",
      status: "",
      supersedes: "",
      sourceUrl: "",
    },
    body: [],
  },
};

export const SOURCE = {
  tkdl: { id: "IN-TKDL-001", label: "TKDL Prior Art", statute: "patents-3p" },
  p3p: { id: "IN-PAT-001", label: "Patents Act — Section 3(p)", statute: "patents-3p" },
  p3e: { id: "IN-PAT-001", label: "Patents Act — Section 3(e)", statute: "patents-3e" },
  p3d: { id: "IN-PAT-001", label: "Patents Act — Section 3(d)", statute: "patents-3d" },
  bda: { id: "IN-BIO-001", label: "Biological Diversity Act — Section 6", statute: "bda-6" },
  f3: { id: "IN-NBA-001", label: "NBA Form III", statute: "nba-form-iii" },
} satisfies Record<string, SourceTag>;

export const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  createdAt: 0,
  content: `🙏 Namaste! I'm **IP SAKTI Sahayak** — I help you navigate IP protection and regulatory compliance for Ayurvedic, Siddha, and Unani formulations, across Indian and international regimes.

Ask a question or explore a case study — every answer names the specific Act, Rule, or record it's grounded in, so you can verify it yourself.`,
  sources: [SOURCE.p3p, SOURCE.bda],
};

// ---------------------------------------------------------------------------
// Backend API integration — replaces client-side generateAnswer() mock
// ---------------------------------------------------------------------------

/**
 * Maps a backend SourceCitation to a frontend SourceTag.
 * Uses statute_id from the backend when available (Phase 2+);
 * falls back to inferStatuteId() for older backend versions.
 * Unknown citations get the explicit "unmapped" StatuteId rather than
 * silently pointing at a real statute — this prevents the same failure
 * class (wrong-section citations) at the UI layer that was fixed in the
 * retrieval pipeline.
 */
function inferStatuteId(id: string, provision: string, backendStatuteId?: string): StatuteId {
  // Prefer the backend-supplied statute_id when available
  if (backendStatuteId) {
    const known: StatuteId[] = ["patents-3p", "patents-3e", "patents-3d", "bda-6", "nba-form-iii"];
    if (known.includes(backendStatuteId as StatuteId)) return backendStatuteId as StatuteId;
  }
  // Client-side inference as fallback
  const p = `${provision} ${id}`.toLowerCase();
  if (
    p.includes("3(p)") ||
    p.includes("-3p") ||
    p.includes("section 3p") ||
    p.includes("sec 3(p)") ||
    p.includes("traditional knowledge")
  )
    return "patents-3p";
  if (
    p.includes("3(e)") ||
    p.includes("-3e") ||
    p.includes("section 3e") ||
    p.includes("sec 3(e)") ||
    p.includes("admixture") ||
    p.includes("synergy")
  )
    return "patents-3e";
  if (
    p.includes("3(d)") ||
    p.includes("-3d") ||
    p.includes("section 3d") ||
    p.includes("sec 3(d)") ||
    p.includes("efficacy")
  )
    return "patents-3d";
  if (
    p.includes("section 6") ||
    p.includes("sec 6") ||
    p.includes("sec. 6") ||
    p.includes("bda") ||
    p.includes("biodiversity") ||
    p.includes("in-bda")
  )
    return "bda-6";
  if (
    p.includes("form iii") ||
    p.includes("form-iii") ||
    p.includes("nba") ||
    p.includes("in-nba")
  )
    return "nba-form-iii";
  return "unmapped";
}

function mapSources(backendSources: BackendSourceCitation[]): SourceTag[] {
  return (backendSources ?? []).map((s) => {
    const prov = (s.provision || "")
      .replace(/^s\.(\d+)/i, "Section $1")
      .replace(/^sec\.?\s*(\d+)/i, "Section $1")
      .trim();
    let title = (s.title || "").trim();

    if (
      title.startsWith("The claims") ||
      title.startsWith("Document") ||
      title.toLowerCase().includes("retrieved snippet")
    ) {
      title = "";
    }

    let cleanLabel = s.breadcrumb || prov || title || "Statutory Provision";
    if (!s.breadcrumb) {
      if (title && prov && title !== prov) {
        cleanLabel = `${title} — ${prov}`;
      } else if (title) {
        cleanLabel = title;
      } else if (prov) {
        cleanLabel = prov;
      }
    }

    return {
      id: s.id,
      label: cleanLabel,
      statute: inferStatuteId(s.id, s.provision, s.statute_id ?? undefined),
      clauseId: s.clause_id ?? undefined,
      spanStart: s.span_start ?? undefined,
      spanEnd: s.span_end ?? undefined,
      sourceUrl: s.source_url ?? undefined,
      breadcrumb: s.breadcrumb ?? undefined,
      title: s.title ?? undefined,
      provision: s.provision ?? undefined,
      chapter: s.chapter ?? undefined,
      pages: s.pages ?? undefined,
      sourceAuthority: s.source_authority ?? undefined,
      documentType: s.document_type ?? undefined,
      legalArea: s.legal_area ?? undefined,
      text: s.text ?? undefined,
      excerpts: s.excerpts ?? undefined,
    };
  });
}

export type StreamCallbacks = {
  onStatus?: (message: string) => void;
  onSources?: (sources: SourceTag[]) => void;
  onToken?: (token: string) => void;
  onReset?: () => void;
  onClarification?: (questions: ClarificationQuestion[], answer: string) => void;
  onDone?: (payload: {
    session_id: string;
    turn_index: number;
    status: "answered" | "abstained" | "needs_clarification";
    sources?: SourceTag[];
    answer?: string;
  }) => void;
  onError?: (err: Error) => void;
};

/**
 * Resolves the backend base URL:
 * - Local dev: defaults to "" so requests route through the Vite dev server proxy (/api/* -> localhost:8001).
 * - Deployment: uses VITE_BACKEND_URL or VITE_API_URL (e.g. "https://backend-service.onrender.com").
 */
export const BACKEND_BASE_URL = (
  (typeof import.meta !== "undefined" &&
    (import.meta.env?.VITE_BACKEND_URL || import.meta.env?.VITE_API_URL)) ||
  (typeof window !== "undefined" && window.location.hostname.includes("vercel.app")
    ? "https://ayurveda-ps-26045-git-980610462790.europe-west1.run.app"
    : "")
).replace(/\/$/, "");

/**
 * Streams chat responses from the FastAPI backend using Server-Sent Events (SSE).
 * Delivers incremental retrieval status, cited statute sources, and real-time LLM tokens.
 */
export async function streamBackend(
  message: string,
  sessionId: string | null,
  jurisdiction: Jurisdiction,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BACKEND_BASE_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      filters: { jurisdiction },
      top_k: 8,
      stream: true,
    }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Backend error ${res.status}: ${text}`);
  }

  if (!res.body) {
    throw new Error("Response body is not readable for SSE streaming.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const trimmed = part.trim();
        if (!trimmed) continue;

        for (const line of trimmed.split("\n")) {
          const lineTrimmed = line.trim();
          if (!lineTrimmed.startsWith("data:")) continue;

          const jsonStr = lineTrimmed.replace(/^data:\s*/, "");
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "status" && event.message) {
              callbacks.onStatus?.(event.message);
            } else if (event.type === "sources" && Array.isArray(event.sources)) {
              callbacks.onSources?.(mapSources(event.sources));
            } else if (event.type === "token" && typeof event.token === "string") {
              callbacks.onToken?.(event.token);
            } else if (event.type === "reset") {
              callbacks.onReset?.();
            } else if (event.type === "clarification") {
              callbacks.onClarification?.(event.questions ?? [], event.answer ?? "");
            } else if (event.type === "done") {
              callbacks.onDone?.({
                session_id: event.session_id,
                turn_index: event.turn_index,
                status: event.status,
                sources: event.sources ? mapSources(event.sources) : undefined,
                answer: event.answer,
              });
            } else if (event.type === "error") {
              callbacks.onError?.(new Error(event.message || "Streaming error"));
            }
          } catch (err) {
            console.warn("Could not parse SSE payload:", jsonStr, err);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Calls the FastAPI backend chat endpoint.
 * The Vite proxy forwards /api/* → localhost:8001 so no CORS headers needed.
 *
 * Session continuity: pass sessionId from the previous response so the backend
 * LangGraph thread retains clarification context across turns (critical for the
 * original_query preservation fix in understand.py).
 */
export async function callBackend(
  message: string,
  sessionId: string | null,
  jurisdiction: Jurisdiction,
): Promise<{
  session_id: string;
  answer: string;
  sources: SourceTag[];
  turn_index: number;
  timestamp: string;
  status: "answered" | "abstained" | "needs_clarification";
  questions?: ClarificationQuestion[] | undefined;
}> {
  const res = await fetch(`${BACKEND_BASE_URL}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      filters: { jurisdiction },
      top_k: 8,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Backend error ${res.status}: ${text}`);
  }
  const data: BackendChatResponse = await res.json();
  return {
    session_id: data.session_id,
    answer: data.answer,
    sources: mapSources(data.sources),
    turn_index: data.turn_index,
    timestamp: data.timestamp,
    status: data.status,
    questions: data.questions,
  };
}

/**
 * Fetch live statute text from backend.
 * Falls back to the static STATUTES record on network failure so demo never breaks.
 */
export async function loadStatute(id: StatuteId): Promise<(typeof STATUTES)["patents-3p"] | null> {
  if (id === "unmapped") return null;
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/v1/statute/${id}`);
    if (res.ok) return res.json();
  } catch {
    /* network failure — use static fallback below */
  }
  return STATUTES[id] ?? null;
}

/**
 * Calls the backend Formulation Audit endpoint.
 * Falls back to null on error so the drawer can show a graceful degraded state.
 */
export async function callAuditBackend(
  abstract: string,
  classification: string,
  synergyDescription: string,
  ingredients: string,
): Promise<BackendAuditResponse | null> {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/api/v1/audit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        abstract,
        classification,
        synergy_description: synergyDescription,
        ingredients,
      }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Legacy mock — kept only as reference; no longer called by ChatWorkspace.
// ---------------------------------------------------------------------------

const A = (content: string, sources: SourceTag[]) => ({ content, sources });

/** @deprecated Use callBackend() instead. This mock is retained only for
 *  offline fallback reference and will be removed once all demo paths are
 *  verified against the live backend. */
export function generateAnswer(
  question: string,
  jurisdiction: Jurisdiction,
): { content: string; sources: SourceTag[] } {
  const q = question.toLowerCase();
  const intl = jurisdiction === "international";

  if (q.includes("taila") || (q.includes("classical") && q.includes("patent"))) {
    return A(
      `**1. Legal position**
A classical ASU formulation documented in the Ayurvedic texts (and therefore in TKDL) is not patentable as such. Section 3(p) excludes traditional knowledge and mere aggregation or duplication of known properties of traditionally known components.

**2. Why it matters**
For Mahanarayan Taila the full recipe, ratios and indications sit in TKDL in machine-readable form, so an examiner can raise a 3(p) objection at first examination with a single prior-art citation.

**3. What you should check**
Identify what is genuinely outside the classical disclosure — a new delivery system, standardised marker-based process, or an unexpected therapeutic effect with comparative data. Claim that, not the formulation.${
        intl
          ? "\n\n**4. International note**\nTKDL access agreements are in force with the EPO, USPTO and several other offices, so the same disclosure is citable abroad. Confirm the position with local counsel in the target jurisdiction."
          : ""
      }

**Sources**`,
      [SOURCE.p3p, SOURCE.tkdl],
    );
  }

  if (q.includes("3(e)") || q.includes("synergy") || q.includes("shallaki") || q.includes("nano")) {
    return A(
      `**1. Legal position**
Section 3(e) bars a substance that is a mere admixture giving only an aggregation of the properties of its components. A nano-carrier gel of Boswellia serrata (Shallaki) extract is patentable only if the carrier produces an effect greater than the sum of the parts.

**2. Why it matters**
The objection is almost automatic for multi-ingredient herbal compositions. It is rebutted by evidence, not by argument.

**3. What you should check**
File comparative data: extract alone vs carrier alone vs the combination, on the same model, with statistical significance. Add bioavailability or permeation data for the carrier claim, and consider a process claim as a fallback.${
        intl
          ? "\n\n**4. International note**\nMost offices test the same facts as inventive step / non-obviousness rather than as a statutory exclusion, so the synergy dataset remains the key exhibit."
          : ""
      }

**Sources**`,
      [SOURCE.p3e, SOURCE.p3d],
    );
  }

  if (q.includes("form iii") || q.includes("nba") || q.includes("abs") || q.includes("benefit")) {
    return A(
      `**1. Legal position**
Under Section 6(1) of the Biological Diversity Act, NBA approval is required before grant of an IPR on an invention based on an Indian biological resource. Form III is the application for that approval; approval may be taken after acceptance but before sealing of the patent.

**2. Why it matters**
A missing approval is a ground of opposition and can stall sealing. Under the ABS Rules, 2025 benefit sharing is computed on annual gross ex-factory sale in notified slabs.

**3. What you should check**
Map every biological resource in your claims to its source and geographical location, keep collection records, and decide the benefit-sharing offer before filing Form III. Indian entities must also intimate the State Biodiversity Board under Section 7 for commercial utilisation.

**Sources**`,
      [SOURCE.bda, SOURCE.f3],
    );
  }

  if (
    q.includes("export") ||
    q.includes("us ") ||
    q.includes("ashwagandha") ||
    q.includes("international")
  ) {
    return A(
      `**1. Legal position**
Two regimes apply in parallel. In India, export of an Ashwagandha-based product for commercial utilisation triggers Biological Diversity Act obligations (Section 3 for foreign-controlled entities, Section 7 intimation for Indian entities, Section 6 for any IPR). In the United States, a botanical sold as a supplement is regulated under DSHEA as a dietary supplement, not a drug.

**2. Why it matters**
US labelling cannot carry disease claims without drug approval, and a New Dietary Ingredient notification may be required depending on the ingredient's pre-1994 marketing history.

**3. What you should check**
Confirm the DSHEA classification and structure/function claim wording, verify NDI status, and complete the NBA / SBB paperwork on the Indian side before shipment. Confirm state-level rules with local counsel.

**Sources**`,
      [SOURCE.bda, SOURCE.f3],
    );
  }

  if (q.includes("section 3") && (q.includes("biodiversity") || q.includes("7"))) {
    return A(
      `**1. Legal position**
Section 3 requires prior approval of the National Biodiversity Authority for non-citizens, non-resident citizens and body corporates with foreign participation before obtaining any biological resource occurring in India for research or commercial utilisation. Section 7 requires an Indian person or entity to give prior intimation to the State Biodiversity Board for commercial utilisation.

**2. Why it matters**
The trigger is the identity of the applicant and the purpose, not the size of the project. The 2023 amendment narrowed several categories, including registered AYUSH practitioners and codified traditional knowledge users.

**3. What you should check**
Determine your entity status first, then the purpose (research, commercial utilisation, bio-survey), then the correct form — approval vs intimation. Document the chain of custody of the resource.

**Sources**`,
      [SOURCE.bda, SOURCE.f3],
    );
  }

  if (q.includes("traditional knowledge") || q.includes("tkdl") || q.includes("3(p)")) {
    return A(
      `**1. Legal position**
Traditional knowledge is protected defensively in India: TKDL documentation makes codified ASU knowledge citable prior art, and Section 3(p) excludes it from patentability. There is no positive sui generis TK patent right; protection runs through prior art, ABS and GI routes.

**2. Why it matters**
Defensive protection stops misappropriation but does not by itself reward the holder — that is what benefit sharing under the Biological Diversity Act is for.

**3. What you should check**
Search TKDL before drafting, record community sources of any undisclosed knowledge, and structure benefit sharing where a community contribution exists.

**Sources**`,
      [SOURCE.p3p, SOURCE.tkdl, SOURCE.bda],
    );
  }

  return A(
    `**1. Legal position**
Your question touches the AYUSH–IP interface, where three instruments usually operate together: the Patents Act exclusions (Sections 3(p), 3(e), 3(d)), the Biological Diversity Act access and benefit-sharing regime, and TKDL prior art.

**2. Why it matters**
Most filings fail on one of these rather than on novelty in the abstract, so the exclusion analysis should come before drafting.

**3. What you should check**
Tell me the formulation, the claimed advance and the target jurisdiction${
      intl ? " (international regime is active)" : ""
    }, and I will give you the clause-level position with the bare-act text.

**Sources**`,
    [SOURCE.p3p, SOURCE.p3e, SOURCE.bda],
  );
}

export function pickEmoji(text: string) {
  const q = text.toLowerCase();
  if (q.includes("export") || q.includes("us") || q.includes("international")) return "🌐";
  if (q.includes("nba") || q.includes("form") || q.includes("section") || q.includes("statute"))
    return "📑";
  if (q.includes("biodiversity") || q.includes("abs") || q.includes("resource")) return "🌿";
  if (q.includes("nano") || q.includes("carrier") || q.includes("3(e)")) return "🧪";
  return "🏺";
}

export function makeTitle(text: string) {
  const t = text.trim().replace(/\s+/g, " ");
  return t.length > 42 ? `${t.slice(0, 42)}…` : t;
}

const HISTORY_KEY = "ipshakti.history.v1";
export const USER_KEY = "ipshakti.user.v1";
export const INTRO_KEY = "ipshakti.intro-seen.v1";

export function loadHistory(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as Conversation[]) : [];
  } catch {
    return [];
  }
}

export function saveHistory(items: Conversation[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 40)));
  } catch {
    /* ignore quota errors */
  }
}

export function getUserName(): string {
  if (typeof window === "undefined") return "Researcher";
  return window.localStorage.getItem(USER_KEY) || "Researcher";
}

export function timeAgo(ts: number) {
  const diff = Date.now() - ts;
  const m = Math.round(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hr ago`;
  return `${Math.round(h / 24)} d ago`;
}

export const CASE_STUDIES = [
  {
    emoji: "🏺",
    title: "Classical Mahanarayan Taila",
    subtitle: "TKDL prior art & Sec 3(p) bar",
    question:
      "Can we patent a classical Mahanarayan Taila formulation given TKDL prior art and the Section 3(p) bar?",
  },
  {
    emoji: "🧪",
    title: "Shallaki Nano-Carrier Gel",
    subtitle: "Novel carrier & Sec 3(e) synergy",
    question:
      "How do we overcome Section 3(e) for a Shallaki nano-carrier gel with a novel carrier and synergy data?",
  },
  {
    emoji: "📦",
    title: "Ashwagandha US Export",
    subtitle: "US FDA DSHEA & NBA Form I",
    question:
      "What do we need for Ashwagandha export to the US under FDA DSHEA and Indian NBA clearance?",
  },
];

export const QUICK_CHIPS = [
  {
    emoji: "🏺",
    label: "Patent Classical Taila?",
    question: "Can a classical Taila formulation be patented in India?",
  },
  {
    emoji: "🧪",
    label: "Shallaki Section 3(e)",
    question: "How is Section 3(e) synergy proved for a Shallaki composition?",
  },
  {
    emoji: "📑",
    label: "NBA Form III",
    question: "What is required in NBA Form III for an IPR application?",
  },
  {
    emoji: "🌐",
    label: "Export Ashwagandha to US",
    question: "What compliance is needed to export Ashwagandha products to the US?",
  },
];

export const HERO_CHIPS = [
  {
    label: "Patentability of classical formulations",
    question: "Explain the patentability of classical Ayurvedic formulations in India.",
  },
  {
    label: "ABS compliance for AYUSH products",
    question: "What ABS compliance applies to AYUSH products under the Biological Diversity Act?",
  },
  {
    label: "Biodiversity Act Section 3 & 7",
    question: "Explain Biodiversity Act Section 3 and Section 7 obligations.",
  },
  {
    label: "Traditional Knowledge protection",
    question: "How is Traditional Knowledge protected under Indian IP law?",
  },
];
