import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  CitationChip,
  parseCitations,
  type CitationItem,
} from "./CitationComponents";
import type { SourceTag, StatuteId } from "@/lib/sahayak";

interface RichTextProps {
  text: string;
  className?: string;
  citations?: (CitationItem | SourceTag)[];
  onOpenStatute?: (statute: StatuteId, source?: SourceTag) => void;
}

export function RichText({
  text,
  className = "",
  citations = [],
  onOpenStatute,
}: RichTextProps) {
  if (!text) return null;

  const { processedText, citationMap } = useMemo(() => {
    if (!citations || citations.length === 0) {
      return { processedText: text, citationMap: new Map() };
    }
    return parseCitations(text, citations);
  }, [text, citations]);

  return (
    <div
      className={`space-y-2.5 text-[0.95rem] leading-relaxed text-surface-foreground ${className}`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="font-serif text-xl font-bold tracking-tight text-foreground mt-4 mb-2 pb-1 border-b border-border/40 first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="font-serif text-lg font-semibold tracking-tight text-foreground mt-3.5 mb-2 first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="font-serif text-base font-semibold text-foreground mt-3 mb-1.5 first:mt-0">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-sm font-semibold text-foreground mt-2 mb-1 first:mt-0">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="leading-relaxed text-surface-foreground my-2 first:mt-0 last:mb-0">
              {children}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-foreground">{children}</strong>
          ),
          em: ({ children }) => <em className="italic text-surface-foreground/90">{children}</em>,
          ul: ({ children }) => (
            <ul className="my-2 ml-4 list-disc space-y-1 text-surface-foreground marker:text-leaf">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="my-2 ml-4 list-decimal space-y-1 text-surface-foreground marker:font-medium marker:text-leaf">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="pl-1 leading-relaxed">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 rounded-r-lg border-l-3 border-leaf/70 bg-accent/25 py-2 px-3.5 italic text-surface-foreground/90">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-3.5 max-w-full overflow-x-auto rounded-lg border border-border/80 bg-card/60 shadow-2xs">
              <table className="w-full border-collapse text-left text-xs sm:text-sm">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="border-b border-border bg-surface/90 text-foreground font-semibold">
              {children}
            </thead>
          ),
          tbody: ({ children }) => <tbody className="divide-y divide-border/40">{children}</tbody>,
          tr: ({ children }) => (
            <tr className="transition-colors hover:bg-accent/15">{children}</tr>
          ),
          th: ({ children }) => (
            <th className="px-3.5 py-2 font-medium text-foreground uppercase tracking-wider text-[11px]">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3.5 py-2.5 text-surface-foreground align-top leading-normal">
              {children}
            </td>
          ),
          hr: () => <hr className="my-4 border-t border-border/70" />,
          a: ({ href, children }) => {
            if (href?.startsWith("#citation:")) {
              const refId = href.replace("#citation:", "");
              const entry = citationMap.get(refId);
              if (entry) {
                return (
                  <CitationChip
                    id={refId}
                    index={entry.index}
                    citation={entry.citation}
                    onOpenStatute={onOpenStatute}
                  />
                );
              }
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-primary underline underline-offset-2 transition-colors hover:text-leaf"
              >
                {children}
              </a>
            );
          },
          code: ({ className: codeClassName, children, ...props }) => {
            const isBlock = Boolean(codeClassName && codeClassName.includes("language-"));
            if (isBlock) {
              return (
                <pre className="my-2.5 overflow-x-auto rounded-lg border border-border bg-surface p-3 font-mono text-xs text-foreground">
                  <code className={codeClassName} {...props}>
                    {children}
                  </code>
                </pre>
              );
            }
            return (
              <code
                className="rounded border border-border/60 bg-surface px-1.5 py-0.5 font-mono text-[0.85em] font-medium text-primary"
                {...props}
              >
                {children}
              </code>
            );
          },
        }}
      >
        {processedText}
      </ReactMarkdown>
    </div>
  );
}
