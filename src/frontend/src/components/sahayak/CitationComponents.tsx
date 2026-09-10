import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ExternalLink,
  BookOpen,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  ScrollText,
  ShieldCheck,
  X,
  Loader2,
  Globe2,
  AlertTriangle,
} from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { STATUTES, type SourceTag, type StatuteId } from "@/lib/sahayak";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CitationSection {
  chunk_id: string;
  provision?: string;
  title?: string;
  text?: string;
  pages?: string | number;
  chapter?: string;
}

export interface CitationItem {
  id?: string;
  doc_id?: string;
  section?: string;
  chunk_id?: string;
  title?: string;
  section_title?: string;
  excerpt_text?: string;
  source_url?: string;
  page_number?: number | string | null;
  full_text?: string;
  // SourceTag compatibility & grouped schema:
  label?: string;
  statute?: StatuteId;
  text?: string;
  excerpts?: string[];
  provision?: string;
  provisions?: string[];
  sections?: CitationSection[];
  chunk_count?: number;
  chapter?: string;
  pages?: string;
  sourceAuthority?: string;
  documentType?: string;
  legalArea?: string;
  chunk_ids?: string[];
  clauseId?: string;
  breadcrumb?: string;
}

export interface NormalizedCitation {
  id: string;
  chunkId: string;
  docId: string;
  title: string;
  section: string;
  excerptText: string;
  fullText?: string;
  sourceUrl?: string;
  pageNumber?: string;
  statuteId?: StatuteId;
  sourceAuthority?: string;
  legalArea?: string;
  breadcrumb?: string;
  chapter?: string;
  documentType?: string;
  status?: string;
  effectiveFrom?: string;
  publicationDate?: string;
  provisions?: string[];
  sections?: CitationSection[];
  chunkCount?: number;
  raw: CitationItem | SourceTag;
}

// ---------------------------------------------------------------------------
// Normalizer
// ---------------------------------------------------------------------------

export function normalizeCitation(c: CitationItem | SourceTag): NormalizedCitation {
  const anyC = c as any;
  const id = anyC.id || anyC.chunk_id || anyC.doc_id || "unknown";
  const chunkId = anyC.chunk_id || anyC.id || id;
  const docId = anyC.doc_id || anyC.sourceId || id;
  const title =
    anyC.title ||
    anyC.label ||
    anyC.sourceAuthority ||
    "Official Legal Record";
  const section =
    anyC.section_title ||
    anyC.provision ||
    anyC.section ||
    anyC.clauseId ||
    "Statutory Provision";
  const excerptText =
    anyC.excerpt_text ||
    anyC.text ||
    (Array.isArray(anyC.excerpts) && anyC.excerpts[0]) ||
    "";
  const fullText = anyC.full_text || undefined;
  const sourceUrl = anyC.source_url || anyC.sourceUrl || undefined;

  // Clean page numbers: never allow "N/A", "?", or broken strings
  let pageNumber: string | undefined = undefined;
  if (anyC.page_number !== undefined && anyC.page_number !== null) {
    const pStr = String(anyC.page_number).trim();
    if (pStr && !pStr.includes("?") && pStr.toLowerCase() !== "n/a") {
      pageNumber = pStr;
    }
  } else if (anyC.pages) {
    const pStr = String(anyC.pages).trim();
    if (pStr && !pStr.includes("?") && pStr.toLowerCase() !== "n/a") {
      pageNumber = pStr;
    }
  }

  const statuteId: StatuteId | undefined = anyC.statute;
  const statuteDef = statuteId && STATUTES[statuteId] ? STATUTES[statuteId] : undefined;

  const docUpper = (anyC.doc_id || anyC.id || "").toUpperCase();
  const chunkUpper = (anyC.chunk_id || "").toUpperCase();

  const sourceAuthority =
    anyC.sourceAuthority ||
    anyC.authority ||
    (docUpper.includes("ABS") || chunkUpper.includes("ABS") || docUpper.includes("BDA") || chunkUpper.includes("BDA")
      ? "National Biodiversity Authority (NBA) · MoEFCC"
      : docUpper.includes("PAT") || chunkUpper.includes("PAT")
      ? "Office of the Controller General of Patents, Designs & Trade Marks (CGPDTM)"
      : docUpper.includes("TKDL") || chunkUpper.includes("TKDL")
      ? "CSIR · Traditional Knowledge Digital Library"
      : statuteDef
      ? "Government of India · Ministry of Law & Justice"
      : undefined);

  const legalArea =
    anyC.legalArea ||
    (docUpper.includes("ABS") || chunkUpper.includes("ABS") || docUpper.includes("BDA") || chunkUpper.includes("BDA")
      ? "Access & Benefit Sharing (Biological Diversity Act, 2002)"
      : docUpper.includes("PAT") || chunkUpper.includes("PAT")
      ? "Patentability Exclusions & Traditional Knowledge (Patents Act, 1970)"
      : statuteDef?.meta.productCategory || "Indian Intellectual Property & Statutory Grounding");

  const breadcrumb =
    anyC.breadcrumb ||
    anyC.context ||
    statuteDef?.meta.articlesCovered ||
    (anyC.chapter ? `Chapter ${anyC.chapter}` : undefined);

  const chapter = anyC.chapter || undefined;
  const documentType =
    anyC.documentType ||
    (statuteDef ? "Principal Statutory Enactment (Bare Act)" : "Official Statutory Record / Regulatory Guideline");
  const status = statuteDef?.meta.status || "In Force";
  const effectiveFrom = statuteDef?.meta.effectiveFrom;
  const publicationDate = statuteDef?.meta.publicationDate;

  const provisions: string[] | undefined =
    Array.isArray(anyC.provisions) && anyC.provisions.length > 0
      ? anyC.provisions
      : anyC.provision
      ? [anyC.provision]
      : undefined;

  const sections: CitationSection[] | undefined =
    Array.isArray(anyC.sections) && anyC.sections.length > 0
      ? anyC.sections
      : undefined;

  const chunkCount: number | undefined =
    typeof anyC.chunk_count === "number"
      ? anyC.chunk_count
      : Array.isArray(anyC.chunk_ids)
      ? anyC.chunk_ids.length
      : sections
      ? sections.length
      : undefined;

  return {
    id,
    chunkId,
    docId,
    title,
    section,
    excerptText,
    fullText,
    sourceUrl,
    pageNumber,
    statuteId,
    sourceAuthority,
    legalArea,
    breadcrumb,
    chapter,
    documentType,
    status,
    effectiveFrom,
    publicationDate,
    provisions,
    sections,
    chunkCount,
    raw: c,
  };
}

// ---------------------------------------------------------------------------
// Full-Text & Highlight Resolution Helpers
// ---------------------------------------------------------------------------

/**
 * Resolves full statutory text for a citation if available in the database,
 * or mapped from official Bare Acts.
 */
export function getFullTextForCitation(c: NormalizedCitation): string | undefined {
  if (c.fullText) return c.fullText;
  const rawAny = c.raw as any;
  if (rawAny?.full_text) return rawAny.full_text;

  // Check known Bare Acts in STATUTES
  if (c.statuteId && STATUTES[c.statuteId]?.body) {
    return STATUTES[c.statuteId].body.join("\n\n");
  }
  const chunkUpper = (c.chunkId || "").toUpperCase();
  const idUpper = (c.id || "").toUpperCase();

  if (chunkUpper.includes("PAT-3P") || idUpper.includes("PAT-3P")) {
    return STATUTES["patents-3p"]?.body.join("\n\n");
  }
  if (chunkUpper.includes("PAT-3E") || idUpper.includes("PAT-3E")) {
    return STATUTES["patents-3e"]?.body.join("\n\n");
  }
  if (chunkUpper.includes("PAT-3D") || idUpper.includes("PAT-3D")) {
    return STATUTES["patents-3d"]?.body.join("\n\n");
  }
  if (chunkUpper.includes("ABS-001") || chunkUpper.includes("BDA-06") || chunkUpper.includes("SECTION_6")) {
    return STATUTES["bda-6"]?.body.join("\n\n");
  }
  if (chunkUpper.includes("NBA-F3") || chunkUpper.includes("FORM_III")) {
    return STATUTES["nba-form-iii"]?.body.join("\n\n");
  }
  return undefined;
}

/**
 * Finds the start and end character offsets of an excerpt inside fullText.
 * Employs exact matching, case-insensitive matching, and phrase boundary normalization.
 */
export function findHighlightSpan(
  fullText: string,
  excerpt: string,
): { start: number; end: number } | null {
  if (!fullText || !excerpt) return null;
  const trimmedExcerpt = excerpt.trim();
  if (!trimmedExcerpt) return null;

  // 1. Direct exact match
  const idx = fullText.indexOf(trimmedExcerpt);
  if (idx !== -1) {
    return { start: idx, end: idx + trimmedExcerpt.length };
  }

  // 2. Case-insensitive direct match
  const lowerFull = fullText.toLowerCase();
  const lowerExc = trimmedExcerpt.toLowerCase();
  const lowerIdx = lowerFull.indexOf(lowerExc);
  if (lowerIdx !== -1) {
    return { start: lowerIdx, end: lowerIdx + trimmedExcerpt.length };
  }

  // 3. Multi-word boundary matching (for variations in linebreaks or quotes)
  const words = trimmedExcerpt.split(/\s+/).filter((w) => w.length > 2);
  if (words.length >= 3) {
    const firstPhrase = words.slice(0, 3).join(" ").toLowerCase();
    const startWordIdx = lowerFull.indexOf(firstPhrase);
    if (startWordIdx !== -1) {
      const lastPhrase = words.slice(-3).join(" ").toLowerCase();
      const endWordIdx = lowerFull.indexOf(lastPhrase, startWordIdx);
      if (endWordIdx !== -1) {
        return { start: startWordIdx, end: endWordIdx + lastPhrase.length };
      }
      return {
        start: startWordIdx,
        end: Math.min(fullText.length, startWordIdx + trimmedExcerpt.length),
      };
    }
  }

  return null;
}

// ---------------------------------------------------------------------------
// Regex & Citation Parser
// ---------------------------------------------------------------------------

export const CITATION_REGEX =
  /(?:\(|\[)(?:Excerpt\s*\d+[,\s|]+)?Ref:\s*([A-Za-z0-9\-_.:]+)(?:\)|\])/gi;

export interface ParsedCitationsResult {
  processedText: string;
  citationMap: Map<string, { index: number; citation: NormalizedCitation }>;
  uniqueCitations: { index: number; citation: NormalizedCitation }[];
}

export function parseCitations(
  rawText: string,
  citations: (CitationItem | SourceTag)[] = [],
): ParsedCitationsResult {
  if (!rawText) {
    return {
      processedText: "",
      citationMap: new Map(),
      uniqueCitations: [],
    };
  }

  const normalized = citations.map(normalizeCitation);
  const citationMap = new Map<string, { index: number; citation: NormalizedCitation }>();
  const chunkToNumber = new Map<string, number>();
  const uniqueCitations: { index: number; citation: NormalizedCitation }[] = [];
  let nextIndex = 1;

  const processedText = rawText.replace(CITATION_REGEX, (fullMatch, refId) => {
    const cleanRefId = refId.trim();

    const found = normalized.find((c) => {
      if (c.chunkId === cleanRefId || c.id === cleanRefId) return true;
      if (c.docId === cleanRefId) return true;
      const anyRaw = c.raw as any;
      if (Array.isArray(anyRaw.chunk_ids) && anyRaw.chunk_ids.includes(cleanRefId)) {
        return true;
      }
      if (Array.isArray(c.sections) && c.sections.some((s) => s.chunk_id === cleanRefId)) {
        return true;
      }
      if (
        cleanRefId.startsWith(c.id) ||
        cleanRefId.startsWith(c.docId) ||
        c.chunkId.includes(cleanRefId) ||
        cleanRefId.includes(c.chunkId)
      ) {
        return true;
      }
      return false;
    });

    if (!found) {
      console.warn(
        `[CitationParser] Citation tag '${fullMatch}' (Ref: ${cleanRefId}) has no matching citation in payload. Rendering as plain text.`,
      );
      return fullMatch;
    }

    const key = found.chunkId;
    let index = chunkToNumber.get(key);
    if (index === undefined) {
      index = nextIndex++;
      chunkToNumber.set(key, index);
      uniqueCitations.push({ index, citation: found });
    }

    citationMap.set(cleanRefId, { index, citation: found });
    return ` [^${index}](#citation:${cleanRefId}) `;
  });

  return {
    processedText,
    citationMap,
    uniqueCitations,
  };
}

// ---------------------------------------------------------------------------
// PART 1: Compact Sources Strip Components
// ---------------------------------------------------------------------------

export interface SourceChipProps {
  index: number;
  title: string;
  count?: number;
  onClick: () => void;
  className?: string;
}

/**
 * Compact rounded-pill chip showing: [index] Short Title (truncated ~30 chars)
 * If multiple sections/chunks exist for this document, displays a discreet badge (e.g. "2 sections").
 * Native tooltip on hover reveals full title and provision details.
 */
export function SourceChip({ index, title, count, onClick, className }: SourceChipProps) {
  const truncatedTitle = title.length > 30 ? `${title.slice(0, 28)}…` : title;

  return (
    <button
      type="button"
      onClick={onClick}
      title={count && count > 1 ? `${title} (${count} provisions/sections cited)` : title}
      className={cn(
        "group inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-card/90 px-3 py-1 text-xs font-medium text-foreground shadow-2xs",
        "transition-all duration-150 hover:border-primary/40 hover:bg-accent hover:text-primary cursor-pointer active:scale-95",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring select-none",
        className,
      )}
    >
      <span className="font-bold text-primary text-[11px]">[{index}]</span>
      <span className="truncate max-w-[220px]">{truncatedTitle}</span>
      {count && count > 1 ? (
        <span className="ml-0.5 rounded-full bg-primary/10 px-1.5 py-0.2 text-[10px] font-semibold text-primary">
          {count} sections
        </span>
      ) : null}
    </button>
  );
}

export interface SourceChipListProps {
  citations: { index: number; citation: NormalizedCitation }[];
  maxVisible?: number;
  onChipClick: (citation: NormalizedCitation, allCitationsForDoc: NormalizedCitation[]) => void;
  className?: string;
}

/**
 * Compact "Sources" strip showing unique parent document sources as small clickable chips.
 * Chunks from the same document are consolidated into a SINGLE chip with section count.
 * Clicking the chip opens the Statute Reader showing the document metadata once
 * and all sections listed sequentially one below another.
 */
export function SourceChipList({
  citations,
  maxVisible = 5,
  onChipClick,
  className,
}: SourceChipListProps) {
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  // Consolidate citations by canonical document (docId or canonical title)
  const groupedDocMap = new Map<
    string,
    {
      primaryIndex: number;
      primaryCitation: NormalizedCitation;
      allCitations: NormalizedCitation[];
      totalSectionsCount: number;
    }
  >();

  citations.forEach(({ index, citation }) => {
    const docKey = (citation.docId || citation.title || "unknown").toLowerCase().trim();
    const existing = groupedDocMap.get(docKey);

    if (!existing) {
      const initialCount = citation.sections?.length || citation.chunkCount || 1;
      groupedDocMap.set(docKey, {
        primaryIndex: index,
        primaryCitation: citation,
        allCitations: [citation],
        totalSectionsCount: initialCount,
      });
    } else {
      existing.allCitations.push(citation);
      const additionalCount = citation.sections?.length || citation.chunkCount || 1;
      existing.totalSectionsCount = Math.max(existing.totalSectionsCount + additionalCount, existing.allCitations.length);
    }
  });

  const uniqueDocList = Array.from(groupedDocMap.values());
  const hasMore = uniqueDocList.length > maxVisible;
  const visibleDocList = expanded ? uniqueDocList : uniqueDocList.slice(0, maxVisible);
  const remainingCount = uniqueDocList.length - maxVisible;

  const handleChipClick = (
    primaryCitation: NormalizedCitation,
    allCitations: NormalizedCitation[],
  ) => {
    onChipClick(primaryCitation, allCitations.length > 0 ? allCitations : [primaryCitation]);
  };

  return (
    <div
      role="region"
      aria-label="Citations and Sources"
      className={cn("mt-2.5 flex flex-wrap items-center gap-1.5 pt-1", className)}
    >
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mr-1 flex items-center gap-1 select-none">
        <ScrollText className="size-3 text-primary/80" /> Sources:
      </span>

      {visibleDocList.map(({ primaryIndex, primaryCitation, allCitations, totalSectionsCount }) => (
        <SourceChip
          key={primaryCitation.docId || primaryCitation.chunkId || `${primaryCitation.id}-${primaryIndex}`}
          index={primaryIndex}
          title={primaryCitation.title}
          count={totalSectionsCount}
          onClick={() => handleChipClick(primaryCitation, allCitations)}
        />
      ))}

      {hasMore && !expanded && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="inline-flex items-center rounded-full border border-dashed border-border bg-accent/40 px-2.5 py-1 text-xs font-medium text-muted-foreground hover:border-primary/40 hover:bg-accent hover:text-foreground transition-colors cursor-pointer active:scale-95"
          title={`Show ${remainingCount} more citation sources`}
        >
          +{remainingCount} more
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Highlighted Statute Text Component
// ---------------------------------------------------------------------------

export interface HighlightedStatuteTextProps {
  fullText?: string;
  highlightSpan?: { start: number; end: number } | null;
  highlightExcerpt?: string;
  className?: string;
}

/**
 * Renders full statute/section text with the cited chunk/excerpt highlighted in context.
 * If full section text is not available and only the chunk excerpt exists, shows
 * the chunk excerpt with the required fallback note.
 */
export function HighlightedStatuteText({
  fullText,
  highlightSpan,
  highlightExcerpt,
  className,
}: HighlightedStatuteTextProps) {
  const isExcerptOnly =
    !fullText || (highlightExcerpt && fullText.trim() === highlightExcerpt.trim());

  if (isExcerptOnly) {
    const textToDisplay = highlightExcerpt || fullText || "";
    return (
      <div className={cn("space-y-2.5", className)}>
        <div className="rounded-xl border border-primary/25 bg-primary/5 p-4 font-serif text-[0.95rem] leading-relaxed text-foreground shadow-2xs">
          <p className="rounded-md border-l-3 border-primary bg-primary/15 px-2.5 py-1 text-foreground">
            {textToDisplay}
          </p>
        </div>
        <p className="text-[11px] italic text-muted-foreground flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-muted-foreground/60" />
          Full section text unavailable — showing retrieved excerpt only.
        </p>
      </div>
    );
  }

  // Determine highlight span within full text
  let span = highlightSpan;
  if (!span && highlightExcerpt) {
    span = findHighlightSpan(fullText, highlightExcerpt);
  }

  if (!span || span.start < 0 || span.end > fullText.length || span.start >= span.end) {
    return (
      <div className={cn("space-y-3 font-serif text-[0.95rem] leading-relaxed text-foreground", className)}>
        <div className="rounded-xl border border-border/80 bg-surface/70 p-4 whitespace-pre-line">
          <p>{fullText}</p>
        </div>
        {highlightExcerpt && (
          <div className="rounded-xl border border-primary/25 bg-primary/5 p-3.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-primary block mb-1">
              Retrieved Chunk Excerpt:
            </span>
            <p className="rounded-md border-l-2 border-primary bg-primary/15 px-2 py-1 font-serif text-sm">
              {highlightExcerpt}
            </p>
          </div>
        )}
      </div>
    );
  }

  const before = fullText.slice(0, span.start);
  const highlighted = fullText.slice(span.start, span.end);
  const after = fullText.slice(span.end);

  return (
    <div
      className={cn(
        "rounded-xl border border-border/80 bg-surface/70 p-4 font-serif text-[0.95rem] leading-relaxed text-foreground whitespace-pre-line shadow-2xs",
        className,
      )}
    >
      <span>{before}</span>
      <mark className="rounded-md border-l-3 border-primary bg-primary/25 px-1.5 py-0.5 font-semibold text-foreground not-italic shadow-xs">
        {highlighted}
      </mark>
      <span>{after}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PART 2: Dedicated Slide-in Statute Reader Panel
// ---------------------------------------------------------------------------

export interface StatuteReaderPanelProps {
  citation: NormalizedCitation | null;
  allCitationsForDoc?: NormalizedCitation[];
  onSelectCitation?: (citation: NormalizedCitation) => void;
  onClose: () => void;
  isLoading?: boolean;
  jurisdiction?: "national" | "international";
  className?: string;
}

/**
 * Slide-in Statute Reader panel showing:
 * 1. HEADER: Document title + Close button (X).
 * 2. SUBHEADER: Section name/number + "Verified Legal Authority" badge.
 * 3. IN-PANEL JUMP LIST: When multiple citations from the same doc exist, shows an in-panel
 *    jump list to jump between sections without separate reader instances.
 * 4. BODY: Full retrieved statute/section text not truncated, with specific cited excerpt highlighted in context.
 * 5. FOOTER: "Open Full Source ↗" button if source_url exists; internal ref/chunk ID in small muted text.
 *    No "p. ? to ?" or "N/A" ever rendered.
 */
export function CopyExcerptButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <Button
      variant="ghost"
      size="sm"
      className={cn("h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground cursor-pointer", className)}
      onClick={copy}
    >
      {copied ? <Check className="size-3 text-leaf" /> : <Copy className="size-3" />}
      {copied ? "Copied" : "Copy Excerpt"}
    </Button>
  );
}

function StatuteDetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-1 px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <dt className="text-xs font-medium text-muted-foreground shrink-0">{label}</dt>
      <dd className="text-xs font-semibold text-foreground sm:text-right break-words">{value}</dd>
    </div>
  );
}

export function isValidWebUrl(url?: string): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function StatuteReaderPanel({
  citation,
  allCitationsForDoc = [],
  onSelectCitation,
  onClose,
  isLoading = false,
  jurisdiction = "national",
  className,
}: StatuteReaderPanelProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [activeSectionId, setActiveSectionId] = useState<string>("");

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Group citations for this document
  const effectiveDocCitations =
    allCitationsForDoc.length > 0 ? allCitationsForDoc : citation ? [citation] : [];
  const activeCit = citation || effectiveDocCitations[0];

  // Build unified array of sections to display sequentially one below another
  const displayedSections = useMemo(() => {
    if (!activeCit) return [];

    // 1. If activeCit has structured sections from backend, map them
    if (activeCit.sections && activeCit.sections.length > 0) {
      return activeCit.sections.map((sec, idx) => {
        const dummyNorm: NormalizedCitation = {
          ...activeCit,
          chunkId: sec.chunk_id || `${activeCit.chunkId}_sec_${idx}`,
          section: sec.provision || sec.title || `Section ${idx + 1}`,
          excerptText: sec.text || "",
          fullText: sec.text,
        };
        const full = getFullTextForCitation(dummyNorm) || sec.text || activeCit.excerptText;
        return {
          chunkId: sec.chunk_id || `${activeCit.chunkId}_sec_${idx}`,
          section: sec.provision || sec.title || `Section ${idx + 1}`,
          title: sec.title || activeCit.title,
          excerptText: sec.text || activeCit.excerptText,
          fullText: full,
          pageNumber: sec.pages ? String(sec.pages).trim() : activeCit.pageNumber,
          originalCitation: activeCit,
        };
      });
    }

    // 2. If effectiveDocCitations has multiple items (e.g. from frontend grouping)
    if (effectiveDocCitations.length > 1) {
      return effectiveDocCitations.map((item, idx) => ({
        chunkId: item.chunkId || `${item.id}_${idx}`,
        section: item.section || `Section ${idx + 1}`,
        title: item.title,
        excerptText: item.excerptText,
        fullText: getFullTextForCitation(item) || item.excerptText,
        pageNumber: item.pageNumber,
        originalCitation: item,
      }));
    }

    // 3. Single citation fallback
    return [
      {
        chunkId: activeCit.chunkId,
        section: activeCit.section,
        title: activeCit.title,
        excerptText: activeCit.excerptText,
        fullText: getFullTextForCitation(activeCit) || activeCit.excerptText,
        pageNumber: activeCit.pageNumber,
        originalCitation: activeCit,
      },
    ];
  }, [activeCit, effectiveDocCitations]);

  // Scroll spy observer for sticky in-panel jump list
  useEffect(() => {
    if (displayedSections.length <= 1) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const chunkId = entry.target.getAttribute("data-chunk-id");
            if (chunkId) {
              setActiveSectionId(chunkId);
            }
          }
        }
      },
      { root: null, rootMargin: "-15% 0px -50% 0px", threshold: 0.1 },
    );

    displayedSections.forEach((item, idx) => {
      const el = document.getElementById(`statute-section-${item.chunkId || idx}`);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [displayedSections]);

  if (!citation && !isLoading) {
    return null;
  }

  const handleJumpTo = (chunkId: string, idx: number, originalCitation?: NormalizedCitation) => {
    if (originalCitation) {
      onSelectCitation?.(originalCitation);
    }
    setActiveSectionId(chunkId);
    const targetEl = document.getElementById(`statute-section-${chunkId || idx}`);
    if (targetEl) {
      targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const isInternational = jurisdiction === "international";

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-modal="true"
      aria-label={activeCit?.title || "Statute Reader"}
      className={cn("flex h-full flex-col bg-card text-foreground select-text", className)}
    >
      {/* 1. HEADER */}
      <div className="flex items-start justify-between border-b border-border bg-card/95 px-5 py-4 backdrop-blur-xs">
        <div className="min-w-0 flex-1 pr-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <ScrollText className="size-3.5 text-primary" />
            <span>Statute Reader & Grounding</span>
          </div>
          <h2 className="mt-1 font-display text-lg font-bold tracking-tight text-foreground sm:text-xl leading-snug">
            {activeCit?.title || "Statutory Document"}
          </h2>
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close reader"
          onClick={onClose}
          className="size-8 shrink-0 rounded-full hover:bg-accent cursor-pointer"
        >
          <X className="size-4" />
        </Button>
      </div>

      {/* 2. SUBHEADER */}
      {activeCit && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 bg-accent/25 px-5 py-2.5">
          <div className="min-w-0 flex-1 flex items-center gap-2">
            <span className="text-xs font-semibold text-primary">
              {activeCit.section || "Statutory Provision"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {activeCit.sourceUrl && (
              <a
                href={activeCit.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-[11px] font-semibold text-primary hover:bg-primary hover:text-primary-foreground transition-colors"
                title="Open official government source document"
              >
                <span>Original Source Link</span>
                <ExternalLink className="size-3" />
              </a>
            )}
            <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-[11px] font-semibold text-primary">
              <ShieldCheck className="size-3 text-primary" />
              Verified Legal Authority
            </span>
          </div>
        </div>
      )}

      {/* IN-PANEL JUMP LIST (if multiple sections exist from this document) */}
      {displayedSections.length > 1 && (
        <div className="sticky top-0 z-10 flex items-center gap-1.5 overflow-x-auto border-b border-border/80 bg-card/95 px-5 py-2 backdrop-blur-xs scrollbar-thin">
          <span className="shrink-0 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider select-none">
            Jump to:
          </span>
          {displayedSections.map((sec, idx) => {
            const isCurrent = activeSectionId
              ? activeSectionId === sec.chunkId
              : (activeCit?.chunkId === sec.chunkId || idx === 0);
            return (
              <button
                key={sec.chunkId || idx}
                type="button"
                onClick={() => handleJumpTo(sec.chunkId, idx, sec.originalCitation)}
                className={cn(
                  "shrink-0 rounded-full px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer",
                  isCurrent
                    ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : "border border-border bg-surface text-surface-foreground hover:bg-accent hover:border-primary/40",
                )}
              >
                {sec.section || `Section ${idx + 1}`}
              </button>
            );
          })}
        </div>
      )}

      {/* 3. BODY */}
      <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
        {/* International Regime Notice if active */}
        {isInternational && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs space-y-1.5">
            <div className="flex items-center gap-2 font-semibold text-amber-600 dark:text-amber-400">
              <Globe2 className="size-4 shrink-0" />
              <span>International Regime Active · Statutory Bare Acts Unavailable</span>
            </div>
            <p className="text-muted-foreground leading-relaxed">
              Foreign and international statutory texts (e.g. USPTO, EPO, Nagoya Protocol foreign implementing legislations) are currently restricted and not hosted directly in the bare-act database. Legal analysis for international regimes is generated from comparative principles and verified bilateral treaty guidelines.
            </p>
          </div>
        )}

        {isLoading ? (
          /* Loading skeleton */
          <div className="space-y-4 animate-pulse pt-2">
            <div className="h-6 w-3/4 rounded-md bg-muted" />
            <div className="h-4 w-1/2 rounded-md bg-muted/70" />
            <div className="space-y-2 pt-4">
              <div className="h-4 w-full rounded-md bg-muted/50" />
              <div className="h-4 w-full rounded-md bg-muted/50" />
              <div className="h-4 w-4/5 rounded-md bg-muted/50" />
            </div>
          </div>
        ) : (
          <>
            {/* Prominent Original Source Link Banner */}
            {activeCit?.sourceUrl && isValidWebUrl(activeCit.sourceUrl) && (
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-2xl border border-primary/30 bg-primary/5 p-3.5 shadow-2xs">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <ExternalLink className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-bold text-foreground">Official Government Record</span>
                      <span className="rounded bg-primary/10 px-1.5 py-0.2 text-[10px] font-semibold text-primary">
                        Verified
                      </span>
                    </div>
                    <p className="text-[11px] text-muted-foreground truncate max-w-[280px] sm:max-w-[380px]">
                      {activeCit.sourceUrl}
                    </p>
                  </div>
                </div>
                <a
                  href={activeCit.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground shadow-xs hover:bg-primary/90 transition-all hover:scale-102 cursor-pointer"
                >
                  <span>Open Full Source ↗</span>
                </a>
              </div>
            )}

            {/* Major Statutory Details Grid (Rendered ONCE per Document) */}
            {activeCit && (
              <div className="rounded-2xl border border-border bg-card/80 shadow-2xs overflow-hidden">
                <div className="border-b border-border/60 bg-accent/25 px-4 py-2 flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <FileText className="size-3.5 text-primary" /> Major Statutory Details
                  </span>
                  {activeCit.sourceAuthority && (
                    <span className="text-[10px] font-medium text-muted-foreground hidden sm:inline">
                      {activeCit.sourceAuthority}
                    </span>
                  )}
                </div>
                <dl className="divide-y divide-border/60 text-xs">
                  <StatuteDetailRow label="Statute / Enactment" value={activeCit.title} />
                  <StatuteDetailRow
                    label="Provision / Section"
                    value={
                      activeCit.provisions && activeCit.provisions.length > 0
                        ? activeCit.provisions.join(", ")
                        : activeCit.section
                    }
                  />
                  {activeCit.sourceAuthority && (
                    <StatuteDetailRow label="Issuing Authority" value={activeCit.sourceAuthority} />
                  )}
                  {activeCit.legalArea && (
                    <StatuteDetailRow label="Legal Framework" value={activeCit.legalArea} />
                  )}
                  {activeCit.breadcrumb && (
                    <StatuteDetailRow label="Statutory Scope" value={activeCit.breadcrumb} />
                  )}
                  {activeCit.documentType && (
                    <StatuteDetailRow label="Document Type" value={activeCit.documentType} />
                  )}
                  {activeCit.status && (
                    <StatuteDetailRow
                      label="Enactment Status"
                      value={
                        <span className="inline-flex items-center gap-1 rounded-full bg-leaf/15 px-2 py-0.5 text-[10px] font-bold text-leaf">
                          <Check className="size-3" /> {activeCit.status}
                        </span>
                      }
                    />
                  )}
                  {(activeCit.publicationDate || activeCit.effectiveFrom) && (
                    <StatuteDetailRow
                      label="Gazette & Enforcement"
                      value={[
                        activeCit.publicationDate ? `Notified: ${activeCit.publicationDate}` : null,
                        activeCit.effectiveFrom ? `Effective: ${activeCit.effectiveFrom}` : null,
                      ].filter(Boolean).join(" · ")}
                    />
                  )}
                  {activeCit.sourceUrl && (
                    <StatuteDetailRow
                      label="Original Source Link"
                      value={
                        isValidWebUrl(activeCit.sourceUrl) ? (
                          <a
                            href={activeCit.sourceUrl}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="inline-flex items-center gap-1.5 font-semibold text-primary underline underline-offset-2 hover:text-primary/80"
                          >
                            <span>Open Verified Government Record</span>
                            <ExternalLink className="size-3.5 shrink-0" aria-hidden />
                          </a>
                        ) : (
                          <span className="font-mono text-muted-foreground text-[11px]">
                            {activeCit.sourceUrl}
                          </span>
                        )
                      }
                    />
                  )}
                </dl>
              </div>
            )}

            {/* Sections Content: Rendered sequentially one below another */}
            {displayedSections.length > 1 ? (
              <div className="space-y-6 pt-2">
                <div className="flex items-center justify-between border-b border-border/60 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <BookOpen className="size-3.5 text-primary" /> Cited Sections in Context ({displayedSections.length})
                  </h3>
                </div>

                {displayedSections.map((item, idx) => {
                  const isSelected = activeSectionId
                    ? activeSectionId === item.chunkId
                    : activeCit?.chunkId === item.chunkId;
                  return (
                    <section
                      key={item.chunkId || idx}
                      id={`statute-section-${item.chunkId || idx}`}
                      data-chunk-id={item.chunkId}
                      className={cn(
                        "rounded-2xl border p-4 transition-all duration-150 space-y-3",
                        isSelected
                          ? "border-primary/40 bg-accent/15 shadow-soft ring-1 ring-primary/20"
                          : "border-border/80 bg-card/60",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2 border-b border-border/60 pb-2">
                        <div>
                          <h4 className="font-display text-sm font-bold text-foreground">
                            {item.section || item.title}
                          </h4>
                          <span className="text-[10px] font-mono text-muted-foreground">
                            Section {idx + 1} of {displayedSections.length}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <CopyExcerptButton text={item.excerptText} />
                        </div>
                      </div>

                      <HighlightedStatuteText
                        fullText={item.fullText}
                        highlightExcerpt={item.excerptText}
                      />

                      {/* Per-section metadata */}
                      <div className="flex items-center justify-between pt-2 text-[10px] text-muted-foreground border-t border-border/40">
                        <span className="font-mono opacity-80">Ref: {item.chunkId}</span>
                        {item.pageNumber && (
                          <span className="font-medium">Page {item.pageNumber}</span>
                        )}
                      </div>
                    </section>
                  );
                })}
              </div>
            ) : (
              /* Single section */
              displayedSections[0] && (
                <div className="space-y-3 pt-2">
                  <div className="flex items-center justify-between border-b border-border/60 pb-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <BookOpen className="size-3.5 text-primary" /> Statutory Text in Context
                    </h3>
                    <CopyExcerptButton text={displayedSections[0].excerptText} />
                  </div>
                  <HighlightedStatuteText
                    fullText={displayedSections[0].fullText}
                    highlightExcerpt={displayedSections[0].excerptText}
                  />
                  <div className="flex items-center justify-between pt-2 text-[10px] text-muted-foreground border-t border-border/40">
                    <span className="font-mono opacity-80">Ref: {displayedSections[0].chunkId}</span>
                    {displayedSections[0].pageNumber && (
                      <span className="font-medium">Page {displayedSections[0].pageNumber}</span>
                    )}
                  </div>
                </div>
              )
            )}
          </>
        )}
      </div>

      {/* 4. FOOTER */}
      {activeCit && (
        <div className="border-t border-border bg-card/95 px-5 py-3.5 backdrop-blur-xs flex flex-wrap items-center justify-between gap-2">
          {activeCit.sourceUrl ? (
            <a
              href={activeCit.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
            >
              <span>Open Original Source</span>
              <ExternalLink className="size-3.5" />
            </a>
          ) : (
            <div />
          )}

          {/* Internal ref/chunk ID shown ONLY as small muted text at the very bottom */}
          <div className="text-right">
            <span
              className="font-mono text-[10px] text-muted-foreground/75"
              title={`Internal Chunk Identifier: ${activeCit.chunkId}`}
            >
              Ref: {activeCit.chunkId}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Citation Popover Chip (Inline [1] inside assistant prose)
// ---------------------------------------------------------------------------

export interface CitationChipProps {
  id: string;
  index: number;
  citation: NormalizedCitation;
  onOpenStatute?: (statute: StatuteId, source?: SourceTag) => void;
  className?: string;
}

export function CitationChip({
  id,
  index,
  citation,
  onOpenStatute,
  className,
}: CitationChipProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyExcerpt = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!citation.excerptText) return;
    navigator.clipboard.writeText(citation.excerptText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleOpenStatute = (e: React.MouseEvent) => {
    e.stopPropagation();
    setOpen(false);
    if (onOpenStatute) {
      onOpenStatute(
        citation.statuteId || "unmapped",
        citation.raw as SourceTag,
      );
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Citation reference ${index}: ${citation.title}`}
          className={cn(
            "group inline-flex items-center justify-center align-super text-[11px] font-bold tracking-tight",
            "mx-0.5 px-1.5 py-0.5 min-w-[20px] h-[18px] rounded-full",
            "border border-primary/30 bg-accent text-primary transition-all duration-150",
            "hover:border-primary hover:bg-primary hover:text-primary-foreground hover:scale-105 hover:shadow-xs",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring active:scale-95",
            className,
          )}
        >
          <span>[{index}]</span>
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        side="top"
        sideOffset={6}
        className="w-80 sm:w-96 rounded-2xl border border-border bg-card p-4 shadow-lift"
      >
        <div className="space-y-3">
          {/* Header */}
          <div className="flex items-start justify-between gap-2 border-b border-border pb-2.5">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                  {index}
                </span>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Verified Legal Citation
                </span>
              </div>
              <h4 className="mt-1 font-display text-sm font-semibold leading-snug text-foreground">
                {citation.title}
              </h4>
              {citation.section && citation.section !== citation.title && (
                <p className="mt-0.5 text-xs font-medium text-primary">
                  {citation.section}
                </p>
              )}
            </div>
          </div>

          {/* Excerpt text */}
          {citation.excerptText ? (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[11px] font-medium text-muted-foreground">
                <span className="flex items-center gap-1">
                  <BookOpen className="size-3 text-primary" /> Retrieved Excerpt
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={copyExcerpt}
                  className="h-6 gap-1 px-1.5 text-[10px] text-muted-foreground hover:text-foreground"
                >
                  {copied ? <Check className="size-3 text-leaf" /> : <Copy className="size-3" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
              <div className="max-h-44 overflow-y-auto rounded-xl border border-border/80 bg-surface p-3 font-serif text-xs leading-relaxed text-surface-foreground scrollbar-thin">
                <p>{citation.excerptText}</p>
              </div>
            </div>
          ) : (
            <p className="text-xs italic text-muted-foreground">
              Reference grounded from statutory index. Excerpt text available in Statute Reader.
            </p>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-1">
            {onOpenStatute && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleOpenStatute}
                className="flex-1 h-7 text-xs gap-1.5 font-medium border-primary/25 hover:bg-accent"
              >
                <ScrollText className="size-3.5 text-primary" /> Read in Statute Drawer
              </Button>
            )}
            {citation.sourceUrl && (
              <a
                href={citation.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-7 items-center justify-center gap-1 rounded-md border border-border bg-card px-2.5 text-xs font-medium text-foreground transition-colors hover:bg-accent hover:text-primary"
                title="Open official document"
              >
                <span>Gov PDF</span>
                <ExternalLink className="size-3 text-muted-foreground" />
              </a>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Backwards Compatibility Alias
// ---------------------------------------------------------------------------

export type SourcesSummaryPanelProps = SourceChipListProps;
export const SourcesSummaryPanel = SourceChipList;
