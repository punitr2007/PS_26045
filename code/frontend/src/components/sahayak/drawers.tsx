import { useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  ExternalLink,
  FileCheck2,
  Loader2,
  ScrollText,
  ShieldCheck,
  Globe2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import {
  STATUTES,
  callAuditBackend,
  type BackendAuditResponse,
  type SourceTag,
  type StatuteId,
} from "@/lib/sahayak";
import { RichText } from "./RichText";

type Classification = "Classical ASU" | "Proprietary" | "Phytopharmaceutical" | "Nutraceutical";

const VERDICT_STYLES: Record<string, string> = {
  "Likely Blocked": "border-clay/40 bg-clay/10 text-clay",
  "Borderline — Needs Evidence": "border-gold/40 bg-gold/10 text-gold",
  "Reasonably Viable": "border-leaf/40 bg-leaf/10 text-leaf",
};

export function FormulationAudit({
  onClose,
  onInsert,
}: {
  onClose: () => void;
  onInsert: (text: string) => void;
}) {
  const [abstract, setAbstract] = useState("");
  const [classification, setClassification] = useState<Classification>("Classical ASU");
  const [synergy, setSynergy] = useState("");
  const [ingredients, setIngredients] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BackendAuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runAudit = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    const res = await callAuditBackend(abstract, classification, synergy, ingredients);
    setLoading(false);
    if (!res) {
      setError("Could not reach the audit backend. Check that the server is running.");
    } else {
      setResult(res);
    }
  };

  const buildInsertText = () => {
    if (!result) return "";
    return `**Formulation Audit — ${result.verdict}** 🇮🇳 India Domestic Analysis

**Section 3(p) / TKDL Bar:** ${result.tkdl_band}

**Section 3(e) / Synergy:** ${result.s3e_band}

**NBA Form III / Section 6:** ${result.nba_band}

${result.analysis}`;
  };

  return (
    <>
      <DrawerHeader
        icon={<FileCheck2 className="size-4" />}
        title="Formulation Audit"
        onClose={onClose}
      />

      {/* India-only scope label */}
      <div className="border-b border-border bg-accent/30 px-4 py-1.5">
        <p className="text-[11px] font-semibold text-muted-foreground">
          🇮🇳 India Domestic Analysis Only · Patents Act 1970 · Biological Diversity Act 2002
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        <div className="space-y-1.5">
          <Label htmlFor="abstract">Invention abstract / claim</Label>
          <Textarea
            id="abstract"
            rows={4}
            value={abstract}
            onChange={(e) => setAbstract(e.target.value)}
            placeholder="Describe the formulation, the carrier or process, and the claimed advance…"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="ingredients">
            Botanical / ingredient names
            <span className="ml-1 text-[11px] text-muted-foreground">(comma-separated)</span>
          </Label>
          <Textarea
            id="ingredients"
            rows={2}
            value={ingredients}
            onChange={(e) => setIngredients(e.target.value)}
            placeholder="e.g. Boswellia serrata, Withania somnifera, Curcuma longa"
          />
          <p className="text-[11px] text-muted-foreground">
            Required for NBA Form III / Section 6 assessment. Needed to check TKDL prior art
            coverage.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="classification">Legal Classification</Label>
          <select
            id="classification"
            value={classification}
            onChange={(e) => setClassification(e.target.value as Classification)}
            className="h-10 w-full rounded-lg border border-input bg-card px-3 text-sm"
          >
            {["Classical ASU", "Proprietary", "Phytopharmaceutical", "Nutraceutical"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="synergy">
            Synergy / Comparative Evidence
            <span className="ml-1 text-[11px] text-muted-foreground">(Section 3(e) bar)</span>
          </Label>
          <Textarea
            id="synergy"
            rows={3}
            value={synergy}
            onChange={(e) => setSynergy(e.target.value)}
            placeholder='Briefly describe any comparative efficacy data (e.g. "in-vivo anti-inflammatory study vs individual components, p&lt;0.05"). Leave blank if no data exists.'
          />
          <p className="text-[11px] text-muted-foreground">
            The quality and specificity of this description affects the Section 3(e) assessment.
          </p>
        </div>

        {/* Loading skeleton */}
        {loading && (
          <div className="flex items-center gap-2 rounded-2xl border border-border bg-surface p-4 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin text-primary" />
            Analysing against retrieved statutory sources… (this may take up to 15s on a local
            model)
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-2xl border border-clay/40 bg-clay/10 p-4 text-sm text-clay">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-3">
            <div
              className={cn(
                "rounded-2xl border p-4",
                VERDICT_STYLES[result.verdict] ?? "border-border bg-surface",
              )}
            >
              <p className="font-display text-base font-semibold">{result.verdict}</p>
              <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-widest opacity-70">
                Overall feasibility assessment
              </p>
            </div>

            <div className="space-y-2 rounded-2xl border border-border bg-surface p-4 text-sm">
              <BandRow label="Section 3(p) / TKDL" value={result.tkdl_band} />
              <BandRow label="Section 3(e) / Synergy" value={result.s3e_band} />
              <BandRow label="NBA Form III / Section 6" value={result.nba_band} />
            </div>

            <div className="rounded-2xl border border-border bg-surface p-4">
              <RichText text={result.analysis} />
            </div>

            <p className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-accent px-3 py-1 text-[11px] font-medium text-accent-foreground">
              ✅ Grounded against retrieved statutory sources · 🇮🇳 India only
            </p>
          </div>
        )}
      </div>

      <div className="space-y-2 border-t border-border p-4">
        {!result ? (
          <Button
            className="w-full gap-2"
            onClick={runAudit}
            disabled={!abstract.trim() || loading}
          >
            {loading ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Analysing…
              </>
            ) : (
              <>Run Statutory Audit</>
            )}
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => setResult(null)}>
              Re-run
            </Button>
            <Button className="flex-1 gap-2" onClick={() => onInsert(buildInsertText())}>
              Insert into Chat
            </Button>
          </div>
        )}
        <p className="text-center text-[11px] text-muted-foreground">
          Indicative analysis only. Verify with qualified IP/ABS counsel before filing.
        </p>
      </div>
    </>
  );
}

function BandRow({ label, value }: { label: string; value: string }) {
  const band = value.split("—")[0]?.trim() ?? "";
  const colorClass =
    band.includes("Blocked") || band.includes("Required")
      ? "text-clay"
      : band.includes("Borderline") || band.includes("Conditional")
        ? "text-gold"
        : "text-leaf";
  return (
    <div className="flex gap-2">
      <span className="w-44 shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className={cn("text-xs font-medium", colorClass)}>{value}</span>
    </div>
  );
}

function CopyExcerptButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
      onClick={copy}
    >
      {copied ? <Check className="size-3 text-leaf" /> : <Copy className="size-3" />}
      {copied ? "Copied" : "Copy Excerpt"}
    </Button>
  );
}

const BARE_ACT_ITEMS: { id: StatuteId; label: string; code: string }[] = [
  { id: "patents-3p", label: "Patents §3(p)", code: "L0-IN-PAT-3P" },
  { id: "patents-3e", label: "Patents §3(e)", code: "L0-IN-PAT-3E" },
  { id: "patents-3d", label: "Patents §3(d)", code: "L0-IN-PAT-3D" },
  { id: "bda-6", label: "Biodiversity §6", code: "L0-IN-BDA-06" },
  { id: "nba-form-iii", label: "NBA Form III", code: "L1-IN-NBA-F3" },
];

export function StatuteReader({
  activeStatute,
  activeSource,
  consultationSources = [],
  onSelectStatute,
  onSelectSource,
  onClose,
  jurisdiction = "national",
}: {
  activeStatute: StatuteId;
  activeSource?: SourceTag | null;
  consultationSources?: SourceTag[];
  onSelectStatute: (id: StatuteId) => void;
  onSelectSource: (source: SourceTag | null) => void;
  onClose: () => void;
  jurisdiction?: "national" | "international";
}) {
  const hasConsultationSources = consultationSources.length > 0;
  const [tab, setTab] = useState<"cited" | "library">(() =>
    activeSource || hasConsultationSources ? "cited" : "library",
  );

  // If user clicks bare act tab or has no activeSource
  const effectiveStatute: StatuteId =
    activeStatute === "unmapped" ? "patents-3p" : activeStatute;
  const bareDoc = STATUTES[effectiveStatute] || STATUTES["patents-3p"];

  return (
    <>
      <DrawerHeader
        icon={<ScrollText className="size-4 text-primary" />}
        title="Statute Reader & Legal Grounding"
        onClose={onClose}
      />

      {/* Top mode switch tabs if consultation has citations */}
      {hasConsultationSources && (
        <div className="flex border-b border-border bg-accent/20 px-3 py-1.5 gap-2">
          <button
            type="button"
            onClick={() => setTab("cited")}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
              tab === "cited"
                ? "bg-primary text-primary-foreground shadow-soft"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <BookOpen className="size-3.5" />
            Cited Sources ({consultationSources.length})
          </button>
          <button
            type="button"
            onClick={() => {
              setTab("library");
              onSelectSource(null);
            }}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
              tab === "library"
                ? "bg-primary text-primary-foreground shadow-soft"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <ShieldCheck className="size-3.5" />
            Bare Act Library ({BARE_ACT_ITEMS.length})
          </button>
        </div>
      )}

      {/* Source selector pills */}
      {tab === "cited" && hasConsultationSources ? (
        <div className="flex gap-1.5 overflow-x-auto border-b border-border bg-card px-3 py-2 scrollbar-thin">
          {consultationSources.map((s) => {
            const isSelected = activeSource?.id === s.id;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => onSelectSource(s)}
                aria-pressed={isSelected}
                className={cn(
                  "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all",
                  isSelected
                    ? "border-primary bg-primary text-primary-foreground shadow-soft"
                    : "border-border bg-surface text-surface-foreground hover:border-primary/40 hover:bg-accent",
                )}
              >
                <ScrollText className="size-3.5" />
                <span className="max-w-[180px] truncate">{s.label}</span>
                {s.clauseId && <span className="opacity-70">§{s.clauseId}</span>}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="flex gap-1.5 overflow-x-auto border-b border-border bg-card px-3 py-2 scrollbar-thin">
          {BARE_ACT_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                onSelectStatute(item.id);
                onSelectSource(null);
              }}
              aria-pressed={activeStatute === item.id && !activeSource}
              className={cn(
                "whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                activeStatute === item.id && !activeSource
                  ? "border-primary bg-primary text-primary-foreground shadow-soft"
                  : "border-border bg-surface text-surface-foreground hover:border-primary/40 hover:bg-accent",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* Main Drawer Scroll Area */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
        {jurisdiction === "international" && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs space-y-1.5">
            <div className="flex items-center gap-2 font-semibold text-amber-600 dark:text-amber-400">
              <Globe2 className="size-4 shrink-0" />
              <span>International Regime Active · Statutory Bare Acts Unavailable</span>
            </div>
            <p className="text-muted-foreground leading-relaxed">
              Foreign and international statutory texts (e.g. USPTO 35 U.S.C., EPO European Patent Convention, foreign ABS national access laws) are currently restricted and not hosted directly in the bare-act database. Legal analysis for international regimes is generated from comparative principles and verified bilateral treaty guidelines.
            </p>
          </div>
        )}

        {tab === "cited" && activeSource ? (
          /* Viewing a specific citation from current conversation */
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-accent px-2.5 py-1 text-xs font-semibold text-primary">
                <span className="size-1.5 rounded-full bg-leaf animate-pulse" aria-hidden />
                🌿 Grounded in Consultation
              </span>
              <span className="text-xs font-mono text-muted-foreground">{activeSource.id}</span>
            </div>

            <div>
              <h3 className="font-display text-xl font-bold tracking-tight text-foreground sm:text-2xl">
                {activeSource.label}
              </h3>
              {activeSource.title && activeSource.title !== activeSource.label && (
                <p className="mt-1 text-sm font-medium text-muted-foreground">
                  {activeSource.title}
                </p>
              )}
            </div>

            {/* Dynamic Excerpt / Legal Text if available */}
            {(activeSource.text || (activeSource.excerpts && activeSource.excerpts.length > 0)) && (
              <div className="rounded-2xl border border-primary/25 bg-accent/40 p-4 shadow-soft">
                <div className="flex items-center justify-between border-b border-border/60 pb-2 mb-2.5">
                  <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-primary">
                    <BookOpen className="size-3.5" /> Retrieved Grounding Excerpt
                  </span>
                  <CopyExcerptButton
                    text={activeSource.text || activeSource.excerpts?.join("\n\n") || ""}
                  />
                </div>
                <div className="space-y-2.5 font-serif text-[0.95rem] leading-relaxed text-foreground">
                  {activeSource.excerpts && activeSource.excerpts.length > 0
                    ? activeSource.excerpts.map((exc, idx) => (
                        <div
                          key={idx}
                          className="rounded-xl border border-border/60 bg-card/80 p-3.5 shadow-xs"
                        >
                          <p>{exc}</p>
                        </div>
                      ))
                    : activeSource.text && (
                        <div className="rounded-xl border border-border/60 bg-card/80 p-3.5 shadow-xs">
                          <p>{activeSource.text}</p>
                        </div>
                      )}
                </div>
              </div>
            )}

            {/* Document metadata table */}
            <dl className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card shadow-soft">
              <MetaRow
                label="Provision / Section"
                value={activeSource.provision || activeSource.clauseId || "Statutory Provision"}
              />
              {activeSource.sourceAuthority && (
                <MetaRow label="Authority / Issuer" value={activeSource.sourceAuthority} />
              )}
              {activeSource.breadcrumb && (
                <MetaRow label="Legal Context" value={activeSource.breadcrumb} />
              )}
              {(activeSource.chapter || activeSource.pages) && (
                <MetaRow
                  label="Chapter & Pages"
                  value={
                    [
                      activeSource.chapter ? `Chapter ${activeSource.chapter}` : null,
                      activeSource.pages ? `Pages: ${activeSource.pages}` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "N/A"
                  }
                />
              )}
              {activeSource.legalArea && (
                <MetaRow label="Legal Area" value={activeSource.legalArea} />
              )}
              {activeSource.sourceUrl && (
                <MetaRow
                  label="Official Source Record"
                  value={
                    <a
                      href={activeSource.sourceUrl}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1.5 font-medium text-primary underline underline-offset-2 hover:text-primary/80"
                    >
                      <span>Open Verified Document</span>
                      <ExternalLink className="size-3.5 shrink-0" aria-hidden />
                    </a>
                  }
                />
              )}
            </dl>

            {/* If mapped to a known Bare Act, also show full statutory text below */}
            {activeSource.statute !== "unmapped" && STATUTES[activeSource.statute] && (
              <div className="space-y-3 pt-2">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="size-4 text-primary" />
                  <h4 className="font-display text-sm font-bold uppercase tracking-wider text-muted-foreground">
                    Official Gazette Text · {STATUTES[activeSource.statute].title}
                  </h4>
                </div>
                <div className="space-y-3 rounded-2xl border border-border bg-surface p-4 font-serif text-[0.95rem] leading-relaxed text-surface-foreground">
                  {STATUTES[activeSource.statute].body.map((para, i) => (
                    <p key={i}>{para}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Viewing Bare Act Library */
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-accent px-2.5 py-1 text-xs font-semibold text-primary">
                <ShieldCheck className="size-3.5 text-primary" />
                Verified Bare Act Gazette Record
              </span>
              <span className="text-xs font-mono text-muted-foreground">
                Source ID · {bareDoc.sourceId}
              </span>
            </div>

            <div>
              <h3 className="font-display text-xl font-bold tracking-tight text-foreground sm:text-2xl">
                {bareDoc.title}
              </h3>
              <p className="mt-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Official Legislative Act
              </p>
            </div>

            {/* Document metadata */}
            <dl className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card shadow-soft">
              <MetaRow label="Document Title" value={bareDoc.meta.documentTitle} />
              <MetaRow label="Product Category" value={bareDoc.meta.productCategory} />
              <MetaRow label="Articles Covered" value={bareDoc.meta.articlesCovered} />
              <MetaRow label="Publication Date" value={bareDoc.meta.publicationDate} />
              <MetaRow label="Effective From" value={bareDoc.meta.effectiveFrom} />
              <MetaRow label="Effective Until" value={bareDoc.meta.effectiveUntil} />
              <MetaRow
                label="Current Status"
                value={
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground">
                    <span className="size-1.5 rounded-full bg-leaf" aria-hidden />
                    {bareDoc.meta.status}
                  </span>
                }
              />
              <MetaRow label="Supersedes / Amended By" value={bareDoc.meta.supersedes} />
              <MetaRow
                label="Official Source URL"
                value={
                  <a
                    href={bareDoc.meta.sourceUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1 break-all font-medium text-primary underline underline-offset-2 hover:text-primary/80"
                  >
                    <span>{bareDoc.meta.sourceUrl}</span>
                    <ExternalLink className="size-3 shrink-0" aria-hidden />
                  </a>
                }
              />
            </dl>

            {/* Act / document text */}
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Statutory Legislative Text
              </p>
              <div className="space-y-3 rounded-2xl border border-border bg-surface p-4 font-serif text-[0.95rem] leading-relaxed text-surface-foreground">
                {bareDoc.body.map((para, i) => (
                  <p key={i}>{para}</p>
                ))}
              </div>
            </div>

            <p className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-accent px-3 py-1 text-[11px] font-medium text-accent-foreground">
              ✅ Verified Bare Act Gazette Record · Government of India
            </p>
          </div>
        )}
      </div>

      {/* Footer bar with external link button if URL is present */}
      {((tab === "cited" && activeSource?.sourceUrl) || bareDoc.meta.sourceUrl) && (
        <div className="flex items-center justify-between border-t border-border bg-card/60 px-4 py-3 sm:px-6">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            Official Government Record
          </span>
          <a
            href={(tab === "cited" && activeSource?.sourceUrl) || bareDoc.meta.sourceUrl}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground shadow-soft transition-transform hover:-translate-y-px hover:shadow-lift"
          >
            <span>Open Government Gazette / PDF</span>
            <ExternalLink className="size-3.5" />
          </a>
        </div>
      )}
    </>
  );
}

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid gap-1 px-4 py-2.5 transition-colors hover:bg-accent/40 sm:grid-cols-[11rem_1fr] sm:gap-4">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm leading-relaxed text-surface-foreground break-words">{value}</dd>
    </div>
  );
}

function DrawerHeader({
  icon,
  title,
  onClose,
}: {
  icon: React.ReactNode;
  title: string;
  onClose: () => void;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border px-4 py-3.5 sm:px-6">
      <h2 className="flex items-center gap-2 font-display text-base font-semibold">
        {icon} {title}
      </h2>
      <Button variant="ghost" size="icon" aria-label={`Close ${title}`} onClick={onClose}>
        <X className="size-5" />
      </Button>
    </div>
  );
}
