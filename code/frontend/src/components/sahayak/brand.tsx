import { Leaf } from "lucide-react";
import assistantImg from "@/assets/sahayak-assistant.png";
import { cn } from "@/lib/utils";

export function LeafMark({ className }: { className?: string | undefined }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-soft",
        className,
      )}
    >
      <Leaf className="size-5" strokeWidth={2} />
    </span>
  );
}

export function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LeafMark className={compact ? "size-8 rounded-lg" : undefined} />
      <span className="font-display text-lg font-semibold tracking-tight text-foreground">
        IP SHAKTI
      </span>
    </span>
  );
}

export function AssistantAvatar({
  className,
  animate = true,
  priority = false,
}: {
  className?: string | undefined;
  animate?: boolean;
  priority?: boolean;
}) {
  return (
    <img
      src={assistantImg}
      alt="Illustration of the IP SHAKTI Sahayak legal assistant waving hello"
      width={768}
      height={896}
      loading={priority ? "eager" : "lazy"}
      className={cn(
        "select-none object-contain drop-shadow-[0_18px_36px_oklch(0.28_0.05_152/0.18)]",
        animate && "animate-wave",
        className,
      )}
      draggable={false}
    />
  );
}
