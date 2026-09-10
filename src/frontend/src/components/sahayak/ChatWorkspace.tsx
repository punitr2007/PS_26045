import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Copy,
  ExternalLink,
  FlaskConical,
  Globe2,
  HelpCircle,
  History,
  Landmark,
  Leaf,
  Menu,
  Plus,
  Scale,
  ScrollText,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { AssistantAvatar, BrandLockup, LeafMark } from "./brand";
import { RichText } from "./RichText";
import { FormulationAudit } from "./drawers";
import {
  normalizeCitation,
  parseCitations,
  SourceChipList,
  StatuteReaderPanel,
  type NormalizedCitation,
} from "./CitationComponents";
import {
  CASE_STUDIES,
  QUICK_CHIPS,
  STATUTES,
  WELCOME_MESSAGE,
  callBackend,
  streamBackend,
  loadHistory,
  makeTitle,
  pickEmoji,
  saveHistory,
  timeAgo,
  type ClarificationQuestion,
  type ChatMessage,
  type Conversation,
  type Jurisdiction,
  type StatuteId,
  type SourceTag,
} from "@/lib/sahayak";

const ROTATING = [
  "Let's navigate the rules together.",
  "Ready to explore your IP path?",
  "What's your formulation about today?",
  "Got a patent or ABS question?",
];

const uid = () => Math.random().toString(36).slice(2, 10);

function getChipIcon(idx: number) {
  switch (idx) {
    case 0:
      return <Scale className="size-3.5 text-primary shrink-0" />;
    case 1:
      return <FlaskConical className="size-3.5 text-leaf shrink-0" />;
    case 2:
      return <ScrollText className="size-3.5 text-amber-500 shrink-0" />;
    case 3:
      return <Globe2 className="size-3.5 text-blue-500 shrink-0" />;
    default:
      return <Sparkles className="size-3.5 text-primary shrink-0" />;
  }
}

type Props = {
  userName: string;
  onExit: () => void;
  pendingQuestion?: string | null | undefined;
  onPendingConsumed: () => void;
  showIntro: boolean;
  onIntroDismiss: () => void;
};

export function ChatWorkspace({
  userName,
  onExit,
  pendingQuestion,
  onPendingConsumed,
  showIntro,
  onIntroDismiss,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [jurisdiction, setJurisdiction] = useState<Jurisdiction>("national");
  const [collapsed, setCollapsed] = useState(true);
  const [mobileNav, setMobileNav] = useState(false);
  const [drawer, setDrawer] = useState<null | "audit" | "statute">(null);
  const [drawerWidth, setDrawerWidth] = useState<number>(() => {
    if (typeof window !== "undefined") {
      return Math.min(Math.max(window.innerWidth * 0.45, 540), 780);
    }
    return 680;
  });
  const [isResizing, setIsResizing] = useState(false);
  const [statute, setStatute] = useState<StatuteId>("patents-3p");
  const [selectedSource, setSelectedSource] = useState<SourceTag | null>(null);
  const [activeCitation, setActiveCitation] = useState<NormalizedCitation | null>(null);
  const [allCitationsForDoc, setAllCitationsForDoc] = useState<NormalizedCitation[]>([]);
  const [history, setHistory] = useState<Conversation[]>([]);
  const [chatId, setChatId] = useState(() => uid());
  const [confirmNew, setConfirmNew] = useState(false);
  const [rotIndex, setRotIndex] = useState(0);
  // sessionId persists the LangGraph thread across clarification turns.
  // Initialized to null; set from the first backend response.
  const [sessionId, setSessionId] = useState<string | null>(null);
  // Clarification questions returned by the backend (status === "needs_clarification")
  const [pendingClarifications, setPendingClarifications] = useState<ClarificationQuestion[]>([]);
  const [showQuickChips, setShowQuickChips] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const minWidth = 400;
      const maxWidth = Math.min(window.innerWidth - 48, 1280);
      const newWidth = Math.max(minWidth, Math.min(maxWidth, window.innerWidth - e.clientX));
      setDrawerWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing]);

  const consultationSources = useMemo(() => {
    const map = new Map<string, SourceTag>();
    for (const m of messages) {
      if (m.sources) {
        for (const s of m.sources) {
          if (!map.has(s.id)) {
            map.set(s.id, s);
          }
        }
      }
    }
    return Array.from(map.values());
  }, [messages]);

  const started = messages.length > 0;

  useEffect(() => setHistory(loadHistory()), []);

  useEffect(() => {
    if (started || input.trim().length > 0) return;
    const t = window.setInterval(() => setRotIndex((i) => (i + 1) % ROTATING.length), 4200);
    return () => window.clearInterval(t);
  }, [started, input]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  // Auto-grow textarea up to 160px smoothly without clipping
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  // Abort background stream on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setTyping(false);
      setStatusMessage(null);
      toast.info("Generation stopped");
    }
  }, []);

  const persist = useCallback(
    (msgs: ChatMessage[]) => {
      const firstUser = msgs.find((m) => m.role === "user");
      if (!firstUser) return;
      setHistory((prev) => {
        const entry: Conversation = {
          id: chatId,
          title: makeTitle(firstUser.content),
          emoji: pickEmoji(firstUser.content),
          updatedAt: Date.now(),
          messages: msgs,
        };
        const next = [entry, ...prev.filter((c) => c.id !== chatId)];
        saveHistory(next);
        return next;
      });
    },
    [chatId],
  );

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || typing) return;
      const base =
        messages.length === 0 ? [{ ...WELCOME_MESSAGE, createdAt: Date.now() }] : messages;
      const userMsg: ChatMessage = {
        id: uid(),
        role: "user",
        content: text,
        createdAt: Date.now(),
      };

      const assistantId = uid();
      const initialAssistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        sources: [],
        createdAt: Date.now(),
      };

      const withUser = [...base, userMsg];
      setMessages(withUser);
      setInput("");
      setTyping(true);
      setStatusMessage("Connecting to legal RAG engine...");
      setPendingClarifications([]);

      let accumulatedContent = "";
      let currentSources: SourceTag[] = [];

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        await streamBackend(
          text,
          sessionId,
          jurisdiction,
          {
            onStatus: (status) => {
              setStatusMessage(status);
            },
            onSources: (sources) => {
              currentSources = sources;
              setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, sources } : m)));
            },
            onToken: (token) => {
              if (!accumulatedContent) {
                setMessages((prev) => {
                  const exists = prev.some((m) => m.id === assistantId);
                  if (!exists) {
                    return [
                      ...prev,
                      { ...initialAssistantMsg, content: token, sources: currentSources },
                    ];
                  }
                  return prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + token, sources: currentSources }
                      : m,
                  );
                });
              } else {
                setMessages((prev) =>
                  prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + token } : m)),
                );
              }
              accumulatedContent += token;
              setStatusMessage(null);
            },
            onReset: () => {
              accumulatedContent = "";
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, content: "" } : m)),
              );
            },
            onClarification: (questions, clarifyText) => {
              setPendingClarifications(questions);
              if (clarifyText && !accumulatedContent) {
                accumulatedContent = clarifyText;
                setMessages((prev) => {
                  const exists = prev.some((m) => m.id === assistantId);
                  if (!exists) {
                    return [
                      ...prev,
                      { ...initialAssistantMsg, content: clarifyText, sources: currentSources },
                    ];
                  }
                  return prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: clarifyText, sources: currentSources }
                      : m,
                  );
                });
              }
            },
            onDone: (payload) => {
              setSessionId(payload.session_id);
              const finalContent = payload.answer || accumulatedContent;
              setMessages((prev) => {
                const final = prev.map((m) => {
                  if (m.id === assistantId) {
                    return {
                      ...m,
                      content: finalContent || m.content,
                      sources: payload.sources || m.sources,
                    };
                  }
                  return m;
                });
                persist(final);
                return final;
              });
            },
            onError: (err) => {
              throw err;
            },
          },
          controller.signal,
        );
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          // Stream cancelled by user; keep whatever content arrived so far
          return;
        }
        const errMsg = err instanceof Error ? err.message : "Unknown error";
        toast.error(`Sahayak couldn't reach the backend: ${errMsg}`);
        if (!accumulatedContent) {
          setMessages(base);
        }
      } finally {
        abortControllerRef.current = null;
        setTyping(false);
        setStatusMessage(null);
      }
    },
    [messages, typing, jurisdiction, sessionId, persist],
  );

  useEffect(() => {
    if (!pendingQuestion || showIntro) return;
    send(pendingQuestion);
    onPendingConsumed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestion, showIntro]);

  const startNew = (force = false) => {
    if (!force && started) {
      setConfirmNew(true);
      return;
    }
    setConfirmNew(false);
    setMessages([]);
    setInput("");
    setChatId(uid());
    setSelectedSource(null);
    // Reset session so the new conversation gets a fresh LangGraph thread.
    setSessionId(null);
    setPendingClarifications([]);
    setMobileNav(false);
    toast.success("New consultation started 🌿");
  };

  const openConversation = (c: Conversation) => {
    setChatId(c.id);
    setMessages(c.messages);
    setSelectedSource(null);
    setMobileNav(false);
    toast("Consultation reloaded", { description: c.title });
  };

  const openStatuteReader = useCallback(
    (citation: NormalizedCitation, docCitations: NormalizedCitation[] = []) => {
      setActiveCitation(citation);
      setAllCitationsForDoc(docCitations.length > 0 ? docCitations : [citation]);
      setDrawer("statute");
      setMobileNav(false);
      toast(`📑 ${citation.title}`, { description: citation.section || "Statute Reader" });
    },
    [],
  );

  const openStatute = useCallback(
    (id: StatuteId, source?: SourceTag) => {
      setStatute(id);
      setSelectedSource(source ?? null);
      if (source) {
        const norm = normalizeCitation(source);
        openStatuteReader(norm, [norm]);
      } else {
        const statuteInfo = STATUTES[id] || STATUTES["patents-3p"];
        const bareCit: NormalizedCitation = {
          id: statuteInfo.sourceId,
          chunkId: statuteInfo.sourceId,
          docId: statuteInfo.sourceId,
          title: statuteInfo.meta.documentTitle || statuteInfo.title,
          section: statuteInfo.title,
          excerptText: statuteInfo.body[0] || "",
          sourceUrl: statuteInfo.meta.sourceUrl,
          statuteId: id,
          raw: {
            id: statuteInfo.sourceId,
            label: statuteInfo.title,
            statute: id,
            text: statuteInfo.body.join("\n\n"),
            sourceUrl: statuteInfo.meta.sourceUrl,
          } as any,
        };
        openStatuteReader(bareCit, [bareCit]);
      }
    },
    [openStatuteReader],
  );

  const switchJurisdiction = (j: Jurisdiction) => {
    if (j === jurisdiction) return;
    setJurisdiction(j);
    const note =
      j === "national"
        ? "National regime activated. Prioritizing Indian patent, biodiversity and AYUSH statutory sources."
        : "International regime activated. (Note: Statutory bare-act texts are unavailable due to licensing & cross-border restrictions; guidance is grounded in comparative treaties & export frameworks).";
    toast(note);
    setMessages((prev) =>
      prev.length === 0
        ? prev
        : [...prev, { id: uid(), role: "system", content: note, createdAt: Date.now() }],
    );
  };

  const insertAudit = (text: string) => {
    const base = messages.length === 0 ? [{ ...WELCOME_MESSAGE, createdAt: Date.now() }] : messages;
    const final: ChatMessage[] = [
      ...base,
      { id: uid(), role: "assistant", content: text, createdAt: Date.now(), sources: [] },
    ];
    setMessages(final);
    persist(final);
    setDrawer(null);
    toast.success("Evaluation inserted into the consultation");
  };

  const sidebar = useMemo(
    () => (
      <SidebarBody
        collapsed={collapsed}
        history={history}
        onNew={() => startNew()}
        onOpen={openConversation}
        onCase={(q) => {
          setMobileNav(false);
          send(q);
        }}
        onStatute={openStatute}
      />
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [collapsed, history, messages, typing],
  );

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-dvh max-h-dvh w-full flex-col overflow-hidden bg-background">
        {/* Header */}
        <header className="z-30 shrink-0 flex items-center gap-2 border-b border-border bg-card/90 px-3 py-2.5 backdrop-blur sm:px-4">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Open navigation"
            onClick={() => setMobileNav(true)}
          >
            <Menu className="size-5" />
          </Button>
          <BrandLockup compact />
          <span className="hidden rounded-full border border-border bg-accent px-2.5 py-1 text-[11px] font-medium text-accent-foreground sm:inline">
            Sahayak AI
          </span>

          <div className="ml-auto flex items-center gap-1.5">
            <div
              role="radiogroup"
              aria-label="Legal regime"
              className="flex rounded-full border border-border bg-surface p-0.5"
            >
              {(["national", "international"] as const).map((j) => (
                <button
                  key={j}
                  role="radio"
                  aria-checked={jurisdiction === j}
                  onClick={() => switchJurisdiction(j)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                    jurisdiction === j
                      ? "bg-primary text-primary-foreground shadow-soft"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {j === "national" ? (
                    <Landmark className="size-3.5" />
                  ) : (
                    <Globe2 className="size-3.5" />
                  )}
                  <span className="hidden sm:inline">
                    {j === "national" ? "National" : "International"}
                  </span>
                </button>
              ))}
            </div>

            {/* Formulation Audit hidden for now per user instruction */}
            {/* <HeaderAction
              icon={<FlaskConical className="size-4" />}
              label="Formulation Audit"
              onClick={() => setDrawer("audit")}
            /> */}
            <HeaderAction
              icon={<ScrollText className="size-4" />}
              label="Statute Reader"
              onClick={() => setDrawer("statute")}
            />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Back to home" onClick={onExit}>
                  <ArrowLeft className="size-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Back to home</TooltipContent>
            </Tooltip>
          </div>
        </header>

        <div className="flex min-h-0 flex-1 overflow-hidden">
          {/* Desktop sidebar */}
          <aside
            className={cn(
              "hidden shrink-0 border-r border-sidebar-border bg-sidebar transition-[width] duration-300 lg:flex lg:flex-col",
              collapsed ? "w-[68px]" : "w-[272px]",
            )}
          >
            <div className="flex items-center justify-between px-2 py-2">
              {!collapsed && (
                <span className="pl-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Workspace
                </span>
              )}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                    aria-expanded={!collapsed}
                    onClick={() => setCollapsed((c) => !c)}
                  >
                    {collapsed ? (
                      <ChevronRight className="size-4" />
                    ) : (
                      <ChevronLeft className="size-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {collapsed ? "Expand sidebar" : "Collapse sidebar"}
                </TooltipContent>
              </Tooltip>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">{sidebar}</div>
          </aside>

          {/* Mobile drawer */}
          {mobileNav && (
            <div className="fixed inset-0 z-50 lg:hidden">
              <button
                aria-label="Close navigation"
                className="absolute inset-0 bg-foreground/30 backdrop-blur-sm"
                onClick={() => setMobileNav(false)}
              />
              <div className="animate-rise absolute inset-y-0 left-0 flex w-[85%] max-w-[300px] flex-col bg-sidebar shadow-lift">
                <div className="flex items-center justify-between border-b border-sidebar-border px-3 py-2.5">
                  <BrandLockup compact />
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Close navigation"
                    onClick={() => setMobileNav(false)}
                  >
                    <X className="size-5" />
                  </Button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto">
                  <SidebarBody
                    collapsed={false}
                    history={history}
                    onNew={() => startNew()}
                    onOpen={openConversation}
                    onCase={(q) => {
                      setMobileNav(false);
                      send(q);
                    }}
                    onStatute={openStatute}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Conversation */}
          <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
              <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
                {!started ? (
                  <EmptyState userName={userName} line={ROTATING[rotIndex] ?? ROTATING[0]!} />
                ) : (
                  <div className="space-y-5">
                    {messages.map((m) => (
                      <MessageBubble
                        key={m.id}
                        message={m}
                        onSource={openStatute}
                        onOpenReader={openStatuteReader}
                      />
                    ))}
                    {typing && <TypingIndicator status={statusMessage} />}
                    {/* Clarification questions — rendered inline when backend returns
                        status=needs_clarification. User answers by typing normally. */}
                    {!typing && pendingClarifications.length > 0 && (
                      <ClarificationPanel
                        questions={pendingClarifications}
                        onAnswer={(ans) => {
                          setPendingClarifications([]);
                          void send(ans);
                        }}
                      />
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Composer */}
            <div className="shrink-0 border-t border-border bg-card/80 backdrop-blur">
              <div className="mx-auto w-full max-w-3xl px-4 py-3 sm:px-6">
                <div className="mb-2">
                  {started && (
                    <button
                      type="button"
                      onClick={() => setShowQuickChips((prev) => !prev)}
                      className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground cursor-pointer"
                    >
                      <Sparkles className="size-3 text-primary" />
                      <span>Suggested queries</span>
                      {showQuickChips ? (
                        <ChevronUp className="size-3" />
                      ) : (
                        <ChevronDown className="size-3" />
                      )}
                    </button>
                  )}
                  {(!started || showQuickChips) && (
                    <div className="flex flex-wrap gap-1.5 animate-rise">
                      {QUICK_CHIPS.map((c, idx) => (
                        <button
                          key={c.label}
                          onClick={() => send(c.question)}
                          className="flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-surface-foreground transition-all hover:-translate-y-px hover:border-primary/40 hover:bg-accent"
                        >
                          {getChipIcon(idx)}
                          <span>{c.label}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    send(input);
                  }}
                  className="flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-soft transition-shadow focus-within:border-primary/50 focus-within:shadow-lift"
                >
                  <label className="sr-only" htmlFor="sahayak-input">
                    Your legal question
                  </label>
                  <Textarea
                    id="sahayak-input"
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        send(input);
                      }
                    }}
                    rows={1}
                    placeholder="Type your question… e.g. Section 3(p), NBA clearance, classical formulations…"
                    className="max-h-40 min-h-11 resize-none border-0 bg-transparent text-[0.95rem] shadow-none focus-visible:ring-0"
                  />
                  {typing ? (
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={stopGeneration}
                      className="h-10 gap-1.5 animate-pulse"
                      title="Stop generating"
                    >
                      <Square className="size-3.5 fill-current" /> Stop
                    </Button>
                  ) : (
                    <Button type="submit" disabled={!input.trim()} className="h-10 gap-1.5">
                      <Send className="size-4" /> Consult
                    </Button>
                  )}
                </form>
                <p className="mt-1.5 text-center text-[11px] text-muted-foreground">
                  Answers cite verified statutory and regulatory sources. Verify with counsel before
                  filing.
                </p>
              </div>
            </div>
          </main>
        </div>

        {/* Right drawers */}
        {drawer && (
          <div className="fixed inset-0 z-50">
            <button
              aria-label="Close panel"
              className="absolute inset-0 bg-foreground/30 backdrop-blur-sm transition-opacity"
              onClick={() => setDrawer(null)}
            />
            <div
              style={{
                width: typeof window !== "undefined" && window.innerWidth >= 640 ? `${drawerWidth}px` : "100%",
                maxWidth: "100vw",
              }}
              className={cn(
                "animate-rise absolute inset-y-0 right-0 flex w-full flex-col bg-card shadow-lift border-l border-border",
                !isResizing && "transition-[width] duration-150 ease-out"
              )}
            >
              {/* Left-edge Resize Handle */}
              <div
                role="separator"
                aria-orientation="vertical"
                aria-label="Resize panel width"
                title="Drag to resize width (Double click to reset)"
                onMouseDown={startResizing}
                onDoubleClick={() => {
                  setDrawerWidth(Math.min(Math.max(window.innerWidth * 0.45, 540), 780));
                }}
                className={cn(
                  "hidden sm:flex absolute -left-2 top-0 bottom-0 w-4 cursor-col-resize z-50 items-center justify-center group select-none touch-none",
                  isResizing && "cursor-col-resize"
                )}
              >
                <div
                  className={cn(
                    "w-1 h-12 rounded-full bg-border/80 group-hover:bg-primary group-hover:h-20 transition-all duration-150",
                    isResizing && "bg-primary h-24 w-1.5 ring-2 ring-primary/30"
                  )}
                />
              </div>

              {drawer === "audit" ? (
                <FormulationAudit onClose={() => setDrawer(null)} onInsert={insertAudit} />
              ) : (
                <StatuteReaderPanel
                  citation={activeCitation}
                  allCitationsForDoc={allCitationsForDoc}
                  onSelectCitation={(c) => setActiveCitation(c)}
                  onClose={() => setDrawer(null)}
                  jurisdiction={jurisdiction}
                />
              )}
            </div>
          </div>
        )}

        {/* New consultation confirmation */}
        {confirmNew && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <button
              aria-label="Dismiss"
              className="absolute inset-0 bg-foreground/30 backdrop-blur-sm"
              onClick={() => setConfirmNew(false)}
            />
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Start a new consultation"
              className="animate-rise relative w-full max-w-sm rounded-2xl border border-border bg-card p-5 shadow-lift"
            >
              <h2 className="font-display text-lg font-semibold">Start a new consultation?</h2>
              <p className="mt-1.5 text-sm text-muted-foreground">
                Your current consultation is saved in Chat History and can be reopened anytime.
              </p>
              <div className="mt-4 flex justify-end gap-2">
                <Button variant="outline" onClick={() => setConfirmNew(false)}>
                  Continue
                </Button>
                <Button onClick={() => startNew(true)}>New Consultation</Button>
              </div>
            </div>
          </div>
        )}

        {showIntro && <IntroOverlay userName={userName} onDone={onIntroDismiss} />}
      </div>
    </TooltipProvider>
  );
}

function HeaderAction({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          onClick={onClick}
          className="gap-1.5"
          aria-label={label}
        >
          {icon}
          <span className="hidden md:inline">{label}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function SidebarBody({
  collapsed,
  history,
  onNew,
  onOpen,
  onCase,
  onStatute,
}: {
  collapsed: boolean;
  history: Conversation[];
  onNew: () => void;
  onOpen: (c: Conversation) => void;
  onCase: (q: string) => void;
  onStatute: (id: StatuteId) => void;
}) {
  const [historySearch, setHistorySearch] = useState("");

  const filteredHistory = useMemo(() => {
    if (!historySearch.trim()) return history;
    const q = historySearch.toLowerCase();
    return history.filter((c) => c.title.toLowerCase().includes(q));
  }, [history, historySearch]);

  const statutes: { id: StatuteId; label: string }[] = [
    { id: "patents-3p", label: "Patents Act, 1970 (Sec 3(p), 3(e), 3(d))" },
    { id: "bda-6", label: "Biological Diversity Act (Sec 3, 6 & Form III)" },
    { id: "nba-form-iii", label: "NBA Form III Specification (ABS Rules 2025)" },
  ];

  if (collapsed) {
    return (
      <nav className="flex flex-col items-center gap-1 py-1" aria-label="Workspace">
        <IconRail icon={<Plus className="size-5" />} label="New Chat" onClick={onNew} />
        <IconRail
          icon={<History className="size-5" />}
          label={`Chat History (${history.length})`}
          onClick={() => history[0] && onOpen(history[0])}
        />
        <IconRail
          icon={<BookOpen className="size-5" />}
          label="Case Studies"
          onClick={() => onCase(CASE_STUDIES[0]!.question)}
        />
        <IconRail
          icon={<ScrollText className="size-5" />}
          label="Bare Act Statutes"
          onClick={() => onStatute("patents-3p")}
        />
      </nav>
    );
  }

  return (
    <nav className="space-y-5 px-3 pb-4" aria-label="Workspace">
      <Button onClick={onNew} className="w-full gap-1.5">
        <Plus className="size-4" /> New Chat
      </Button>

      <Section title="Chat History" icon={<History className="size-3.5" />}>
        {history.length > 0 && (
          <div className="relative mb-2 px-1">
            <Search className="absolute left-3 top-2.5 size-3.5 text-muted-foreground" />
            <input
              type="text"
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
              placeholder="Search consultations..."
              className="w-full rounded-md border border-sidebar-border bg-sidebar-accent/50 pl-8 pr-2.5 py-1 text-xs text-sidebar-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        )}
        {history.length === 0 ? (
          <p className="px-1 text-xs text-muted-foreground">No consultations yet.</p>
        ) : filteredHistory.length === 0 ? (
          <p className="px-1 text-xs text-muted-foreground">No matching consultations.</p>
        ) : (
          filteredHistory.map((c) => (
            <button
              key={c.id}
              onClick={() => onOpen(c)}
              className="w-full rounded-lg px-2 py-2 text-left transition-colors hover:bg-sidebar-accent"
            >
              <span className="line-clamp-1 text-sm text-sidebar-foreground">
                {c.title}
              </span>
              <span className="text-[11px] text-muted-foreground">{timeAgo(c.updatedAt)}</span>
            </button>
          ))
        )}
      </Section>

      <Section title="Case Studies" icon={<BookOpen className="size-3.5" />}>
        {CASE_STUDIES.map((c) => (
          <button
            key={c.title}
            onClick={() => onCase(c.question)}
            className="w-full rounded-lg border border-transparent px-2 py-2 text-left transition-colors hover:border-sidebar-border hover:bg-sidebar-accent"
          >
            <span className="flex items-center gap-1.5 text-sm font-medium text-sidebar-foreground">
              <BookOpen className="size-3.5 text-primary shrink-0" />
              <span>{c.title}</span>
            </span>
            <span className="block pl-5 text-[11px] leading-snug text-muted-foreground">
              {c.subtitle}
            </span>
          </button>
        ))}
      </Section>

      <Section title="Bare Act Statutes" icon={<ScrollText className="size-3.5" />}>
        {statutes.map((s) => (
          <button
            key={s.id}
            onClick={() => onStatute(s.id)}
            className="flex items-center gap-2 w-full rounded-lg px-2 py-2 text-left text-sm leading-snug text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
          >
            <ScrollText className="size-3.5 text-muted-foreground shrink-0" />
            <span>{s.label}</span>
          </button>
        ))}
      </Section>
    </nav>
  );
}

function IconRail({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={label} onClick={onClick}>
          {icon}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h2 className="mb-1.5 flex items-center gap-1.5 px-1 font-sans text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {icon} {title}
      </h2>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function EmptyState({ userName, line }: { userName: string; line: string }) {
  return (
    <div className="flex min-h-[52vh] flex-col items-center justify-center text-center">
      <div className="mb-4 flex items-center justify-center gap-3" aria-hidden="true">
        <div className="flex size-10 items-center justify-center rounded-xl border border-leaf/30 bg-leaf/10 text-leaf shadow-sm">
          <Leaf className="size-5" />
        </div>
        <div className="flex size-10 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary shadow-sm">
          <FlaskConical className="size-5" />
        </div>
        <div className="flex size-10 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-500 shadow-sm">
          <Scale className="size-5" />
        </div>
        <div className="flex size-10 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-500 shadow-sm">
          <Sparkles className="size-5" />
        </div>
      </div>
      <h1 className="font-display text-3xl font-semibold text-foreground sm:text-4xl">
        Welcome, {userName}
      </h1>
      <p className="mt-2.5 text-base font-medium text-primary">IP SHAKTI Sahayak</p>
      <p key={line} className="animate-line mt-2 min-h-7 text-lg text-muted-foreground">
        {line}
      </p>

      <div className="mt-8 w-full max-w-md rounded-2xl border border-border bg-surface/70 p-4 text-left">
        <p className="mb-2.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Try asking about
        </p>
        <ul className="grid gap-2 text-sm text-surface-foreground sm:grid-cols-2">
          <li className="flex items-center gap-2">
            <Leaf className="size-4 text-leaf shrink-0" />
            <span>Classical formulations</span>
          </li>
          <li className="flex items-center gap-2">
            <Scale className="size-4 text-primary shrink-0" />
            <span>Patent exclusions & Sec 3</span>
          </li>
          <li className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-emerald-500 shrink-0" />
            <span>Biodiversity compliance</span>
          </li>
          <li className="flex items-center gap-2">
            <Globe2 className="size-4 text-blue-500 shrink-0" />
            <span>International export & PCT</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  onSource,
  onOpenReader,
}: {
  message: ChatMessage;
  onSource: (id: StatuteId, source?: SourceTag) => void;
  onOpenReader: (citation: NormalizedCitation, allCitationsForDoc: NormalizedCitation[]) => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    toast.success("Consultation response copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  if (message.role === "system") {
    return (
      <p className="animate-rise mx-auto max-w-lg rounded-full border border-border bg-surface px-4 py-1.5 text-center text-xs text-muted-foreground">
        {message.content}
      </p>
    );
  }

  if (message.role === "user") {
    return (
      <div className="animate-rise flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-[0.95rem] leading-relaxed text-primary-foreground shadow-soft">
          {message.content}
        </div>
      </div>
    );
  }

  const { uniqueCitations } = useMemo(() => {
    if (!message.sources || message.sources.length === 0) {
      return { uniqueCitations: [] };
    }
    const res = parseCitations(message.content, message.sources);
    // If the answer text didn't have explicit inline (Ref: XYZ) tags,
    // still display all sources in the collapsible summary panel!
    if (res.uniqueCitations.length === 0 && message.sources.length > 0) {
      return {
        uniqueCitations: message.sources.map((s, i) => ({
          index: i + 1,
          citation: normalizeCitation(s),
        })),
      };
    }
    return res;
  }, [message.content, message.sources]);

  return (
    <article className="animate-rise flex gap-3 group">
      <LeafMark className="mt-0.5 size-8 rounded-lg shrink-0" />
      <div className="min-w-0 flex-1 border-l-2 border-leaf/60 pl-4">
        <RichText
          text={message.content}
          citations={message.sources}
          onOpenStatute={onSource}
        />

        {/* Action bar and citations */}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/40 pt-2">
          {uniqueCitations.length > 0 ? (
            <SourceChipList
              citations={uniqueCitations}
              maxVisible={5}
              onChipClick={onOpenReader}
            />
          ) : (
            <div />
          )}

          {message.content && (
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors cursor-pointer active:scale-95"
              title="Copy answer to clipboard"
            >
              {copied ? (
                <Check className="size-3.5 text-leaf" />
              ) : (
                <Copy className="size-3.5" />
              )}
              <span>{copied ? "Copied" : "Copy answer"}</span>
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

/**
 * Inline panel shown when the backend returns status="needs_clarification".
 * Each question is listed with its options (if provided) as quick-reply buttons,
 * or the user can type a free-form answer in the normal chat input.
 */
function ClarificationPanel({
  questions,
  onAnswer,
}: {
  questions: { field: string; question: string; options?: string[] }[];
  onAnswer: (text: string) => void;
}) {
  return (
    <div className="animate-rise rounded-2xl border border-primary/25 bg-accent/50 p-4">
      <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        <HelpCircle className="size-3.5" /> Sahayak needs a few more details
      </p>
      <div className="space-y-3">
        {questions.map((q) => (
          <div key={q.field}>
            <p className="text-sm font-medium text-surface-foreground">{q.question}</p>
            {q.options && q.options.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {q.options.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => onAnswer(opt)}
                    className="rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-surface-foreground transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-primary hover:text-primary-foreground"
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-muted-foreground">
        Or type your answer in the input below.
      </p>
    </div>
  );
}

function TypingIndicator({ status }: { status?: string | null }) {
  return (
    <div className="flex items-center gap-3" aria-live="polite">
      <LeafMark className="size-8 rounded-lg" />
      <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2">
        <span className="sr-only">Sahayak is preparing a source-cited answer</span>
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="size-1.5 animate-bounce rounded-full bg-leaf"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
        {status && (
          <span className="animate-pulse pl-1 text-xs text-muted-foreground">{status}</span>
        )}
      </div>
    </div>
  );
}

function IntroOverlay({ userName, onDone }: { userName: string; onDone: () => void }) {
  const [second, setSecond] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setSecond(true), 3400);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="IP SHAKTI assistant introduction"
      className="fixed inset-0 z-[60] flex items-end justify-center bg-background/55 p-4 backdrop-blur-md sm:items-center"
    >
      <div className="animate-rise relative w-full max-w-lg rounded-3xl border border-border bg-card/95 p-6 text-center shadow-lift">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Skip introduction"
          className="absolute right-2 top-2"
          onClick={onDone}
        >
          <X className="size-4" />
        </Button>
        <AssistantAvatar className="mx-auto -mt-20 h-40 w-auto sm:-mt-24 sm:h-48" priority />
        <h2 className="font-display text-2xl font-semibold text-foreground">Hi, {userName} 👋</h2>
        <p className="mt-1 text-sm font-medium text-primary">I'm your IP SHAKTI assistant.</p>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-relaxed text-muted-foreground">
          I'll help you navigate patent, traditional knowledge, biodiversity regulations, and ABS
          requirements.
        </p>
        {second && (
          <p className="animate-line mt-3 text-sm text-surface-foreground">
            Let's find the right legal path for your innovation. 🌿
          </p>
        )}
        <Button size="lg" className="mt-6 w-full gap-2 sm:w-auto" onClick={onDone} autoFocus>
          Get Started <ArrowRight className="size-4" />
        </Button>
        <p className="mt-3 flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
          <Sparkles className="size-3" /> Source-cited answers · Verified statutory authority
        </p>
      </div>
    </div>
  );
}
