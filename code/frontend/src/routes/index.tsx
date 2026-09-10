import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BadgeCheck,
  Clock3,
  Globe2,
  Landmark,
  Layers,
  Quote,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AssistantAvatar, BrandLockup, LeafMark } from "@/components/sahayak/brand";
import { ChatWorkspace } from "@/components/sahayak/ChatWorkspace";
import { HERO_CHIPS, INTRO_KEY, USER_KEY, getUserName } from "@/lib/sahayak";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "IP SHAKTI Sahayak — Legal Intelligence for Ayurveda & Biodiversity" },
      {
        name: "description",
        content:
          "Source-cited answers on patents, ABS, traditional knowledge and biodiversity law for AYUSH innovators, researchers and legal teams.",
      },
      {
        property: "og:title",
        content: "IP SHAKTI Sahayak — Legal Intelligence for AYUSH Innovation",
      },
      {
        property: "og:description",
        content:
          "Jurisdiction-aware, source-cited legal answers on patents, TKDL, ABS and biodiversity compliance.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  const [view, setView] = useState<"landing" | "chat">("landing");
  const [userName, setUserName] = useState("Researcher");
  const [pending, setPending] = useState<string | null>(null);
  const [showIntro, setShowIntro] = useState(false);

  useEffect(() => setUserName(getUserName()), []);

  useEffect(() => {
    if (view === "chat") {
      window.scrollTo(0, 0);
      document.documentElement.style.overflow = "hidden";
      document.body.style.overflow = "hidden";
    } else {
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
    }
    return () => {
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
    };
  }, [view]);

  const enterChat = useCallback((question?: string) => {
    const seen = window.localStorage.getItem(INTRO_KEY) === "1";
    setShowIntro(!seen);
    setPending(question ?? null);
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    setView("chat");
  }, []);

  const dismissIntro = useCallback(() => {
    window.localStorage.setItem(INTRO_KEY, "1");
    setShowIntro(false);
  }, []);

  const editName = () => {
    const next = window.prompt("Display name shown by your Sahayak", userName);
    if (next && next.trim()) {
      const value = next.trim();
      window.localStorage.setItem(USER_KEY, value);
      setUserName(value);
    }
  };

  return (
    <>
      <div className={cn("min-h-dvh bg-background", view === "landing" ? "block" : "hidden")}>
        <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center gap-6 px-5 py-3">
            <BrandLockup />
            <nav aria-label="Main" className="ml-auto flex items-center gap-1 text-sm">
              <a
                href="#home"
                className="rounded-lg px-3 py-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                Home
              </a>
              <a
                href="#about"
                className="rounded-lg px-3 py-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                About
              </a>
              <a
                href="#knowledge"
                className="rounded-lg px-3 py-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                Knowledge
              </a>
              <button
                onClick={editName}
                className="ml-1 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-surface-foreground transition-colors hover:bg-accent"
                aria-label={`Signed in as ${userName}. Change display name`}
              >
                {userName}
              </button>
            </nav>
          </div>
        </header>

        <main id="home">
          {/* Hero */}
          <section className="paper-grain border-b border-border">
            <div className="mx-auto grid max-w-6xl items-center gap-10 px-5 py-14 lg:grid-cols-[1.45fr_0.75fr] lg:gap-14 lg:py-20">
              <div>
                <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-accent px-3.5 py-1.5 text-sm font-medium text-accent-foreground">
                  <BadgeCheck className="size-4" /> Legal Intelligence for Ayurveda &amp;
                  Biodiversity
                </span>
                <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] text-foreground sm:text-6xl lg:text-7xl">
                  Legal Intelligence for
                  <br />
                  <span className="text-primary">Ayurveda, AYUSH &amp; Biodiversity</span>
                  <br />
                  Innovation
                </h1>
                <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground sm:text-xl">
                  Ask anything about patents, ABS, traditional knowledge, and biodiversity law. Get
                  jurisdiction-aware, source-cited answers in seconds.
                </p>
                <p className="mt-3 text-base text-muted-foreground">
                  Powered by verified primary statutory sources · Updated with 2023–2025 amendments
                </p>

                <ul className="mt-8 flex flex-wrap gap-2.5">
                  {HERO_CHIPS.map((c) => (
                    <li key={c.label}>
                      <button
                        onClick={() => enterChat(c.question)}
                        className="rounded-full border border-border bg-card px-4 py-2.5 text-base text-surface-foreground shadow-soft transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-accent"
                      >
                        {c.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Assistant entry point */}
              <div
                role="button"
                tabIndex={0}
                onClick={() => enterChat()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    enterChat();
                  }
                }}
                className="group relative mx-auto w-full max-w-xs cursor-pointer rounded-3xl border border-primary/40 bg-primary p-5 pb-7 text-center shadow-lift transition-all hover:-translate-y-1 hover:shadow-lift focus-visible:-translate-y-1"
                aria-label={`Chat with your IP SHAKTI assistant, ${userName}`}
              >
                <AssistantAvatar
                  priority
                  className="mx-auto h-40 w-auto transition-transform duration-500 group-hover:scale-[1.03] sm:h-48"
                />
                <p className="font-display text-xl font-semibold text-primary-foreground">
                  Hi, {userName} 👋
                </p>
                <p className="mt-1 text-sm text-primary-foreground/80">
                  I&apos;m your IP SHAKTI assistant.
                </p>
                <span className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-card px-6 py-5 font-display text-xl font-semibold text-primary shadow-soft transition-transform group-hover:translate-y-0.5 sm:text-2xl">
                  Chat with me <ArrowRight className="size-5" />
                </span>
              </div>
            </div>
          </section>

          {/* Why */}
          <section id="about" className="mx-auto max-w-6xl px-5 py-16">
            <h2 className="font-display text-3xl font-semibold">Why IP SHAKTI?</h2>
            <p className="mt-2 max-w-2xl text-muted-foreground">
              Built for researchers, AYUSH innovators, patent professionals and biodiversity
              stakeholders who need clause-level answers, not generic summaries.
            </p>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  icon: <Zap className="size-5" />,
                  title: "Instant Legal Answers",
                  body: "Clause-level positions on patentability, exclusions and compliance in seconds.",
                },
                {
                  icon: <Globe2 className="size-5" />,
                  title: "Jurisdiction-Aware",
                  body: "Switch between the Indian regime and international regulatory context.",
                },
                {
                  icon: <Clock3 className="size-5" />,
                  title: "Always Current",
                  body: "Aligned with the 2023 Biological Diversity amendment and ABS Rules, 2025.",
                },
                {
                  icon: <Quote className="size-5" />,
                  title: "Source-Cited Answers",
                  body: "Every answer carries the bare act, record or form it rests on.",
                },
              ].map((c) => (
                <article
                  key={c.title}
                  className="rounded-2xl border border-border bg-card p-5 shadow-soft transition-all hover:-translate-y-1 hover:shadow-lift"
                >
                  <span className="inline-flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                    {c.icon}
                  </span>
                  <h3 className="mt-3 font-display text-lg font-semibold">{c.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{c.body}</p>
                </article>
              ))}
            </div>
          </section>

          {/* Knowledge corpus */}
          <section id="knowledge" className="border-y border-border bg-surface/60">
            <div className="mx-auto max-w-6xl px-5 py-16">
              <h2 className="font-display text-3xl font-semibold">Knowledge Corpus</h2>
              <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["50+", "Primary Sources"],
                  ["12", "Jurisdictions"],
                  ["100%", "Authority Ranked"],
                  ["✅", "Verified"],
                ].map(([value, label]) => (
                  <div
                    key={label}
                    className="rounded-2xl border border-border bg-card p-5 text-center shadow-soft"
                  >
                    <p className="font-display text-3xl font-semibold text-primary">{value}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{label}</p>
                  </div>
                ))}
              </div>

              <div className="mt-6 grid gap-4 lg:grid-cols-3">
                {[
                  {
                    icon: <Landmark className="size-5" />,
                    title: "Patent Law",
                    meta: "12 core statutes & guidelines",
                    body: "Sections 3(p), 3(e) and 3(d), examination practice and TKDL citations.",
                  },
                  {
                    icon: <Layers className="size-5" />,
                    title: "ABS & Biodiversity",
                    meta: "38 statutory rules & forms",
                    body: "Biological Diversity Act, 2023 amendment, ABS Rules 2025 and NBA forms.",
                  },
                  {
                    icon: <Sparkles className="size-5" />,
                    title: "Traditional Knowledge",
                    meta: "9 regulatory monographs",
                    body: "TKDL practice, defensive protection and community benefit sharing.",
                  },
                ].map((d) => (
                  <article
                    key={d.title}
                    className={cn(
                      "rounded-2xl border border-border bg-card p-5 shadow-soft",
                      "transition-all hover:-translate-y-1 hover:shadow-lift",
                    )}
                  >
                    <span className="inline-flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                      {d.icon}
                    </span>
                    <h3 className="mt-3 font-display text-lg font-semibold">{d.title}</h3>
                    <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                      {d.meta}
                    </p>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{d.body}</p>
                  </article>
                ))}
              </div>

              <div className="mt-8 flex justify-center">
                <Button size="lg" className="gap-2" onClick={() => enterChat()}>
                  Chat with me <ArrowRight className="size-4" />
                </Button>
              </div>
            </div>
          </section>
        </main>

        <footer className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-5 py-10 text-center">
          <LeafMark />
          <p className="text-sm text-muted-foreground">
            Legal intelligence for Ayurveda, AYUSH &amp; Biodiversity · Source-cited answers
          </p>
        </footer>
      </div>

      <div className={cn("fixed inset-0 z-40 h-dvh max-h-dvh w-full overflow-hidden", view === "chat" ? "block" : "hidden")}>
        <ChatWorkspace
          userName={userName}
          onExit={() => {
            setView("landing");
            window.scrollTo({ top: 0, left: 0, behavior: "instant" });
          }}
          pendingQuestion={pending}
          onPendingConsumed={() => setPending(null)}
          showIntro={showIntro}
          onIntroDismiss={dismissIntro}
        />
      </div>
    </>
  );
}
