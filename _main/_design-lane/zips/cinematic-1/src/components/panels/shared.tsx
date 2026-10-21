import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import type { Scene } from "@/data/scenes";
import type { LiveLine, Segment } from "@/hooks/useTranscription";
import { useLevel } from "@/hooks/useTranscription";
import { cn } from "@/utils/cn";

export interface PanelProps {
  scene: Scene;
  segments: Segment[];
  live: LiveLine | null;
  paused: boolean;
  elapsed: number;
  onToggle: () => void;
  onClear: () => void;
}

/** Keeps a scroll container pinned to the newest line, softly. */
export function useAutoScroll<T extends HTMLElement>(dep: unknown) {
  const ref = useRef<T | null>(null);
  const first = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: first.current ? "auto" : "smooth" });
    first.current = false;
  }, [dep]);
  return ref;
}

export function LevelMeter({
  bars = 14,
  active = true,
  color,
  height = 13,
  width = 2,
  className,
}: {
  bars?: number;
  active?: boolean;
  color: string;
  height?: number;
  width?: number;
  className?: string;
}) {
  const levels = useLevel(bars, active);
  return (
    <div className={cn("flex items-end gap-[3px]", className)} style={{ height }} aria-hidden>
      {levels.map((v, i) => (
        <span
          key={i}
          style={{
            width,
            height: "100%",
            borderRadius: 999,
            background: color,
            transformOrigin: "bottom",
            transform: `scaleY(${active ? 0.18 + v * 0.82 : 0.12})`,
            transition: "transform 210ms linear",
          }}
        />
      ))}
    </div>
  );
}

export function LiveDot({
  color,
  size = 7,
  active = true,
  ring = true,
}: {
  color: string;
  size?: number;
  active?: boolean;
  ring?: boolean;
}) {
  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      {ring && active && (
        <span
          className="anim-ring absolute inset-0 rounded-full"
          style={{ background: color }}
          aria-hidden
        />
      )}
      <span
        className={cn("block rounded-full", active && "anim-dot")}
        style={{ width: size, height: size, background: color }}
      />
    </span>
  );
}

export const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");

export function wordsOf(segments: Segment[]) {
  return segments.reduce((n, s) => n + s.text.trim().split(/\s+/).filter(Boolean).length, 0);
}

/* ------------------------------------------------------------------ icons */
type IconProps = { className?: string; size?: number };
const base = (size = 14) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export const IconPause = ({ className, size = 14 }: IconProps) => (
  <svg {...base(size)} className={className}>
    <rect x="7" y="5" width="3.4" height="14" rx="1.2" />
    <rect x="13.6" y="5" width="3.4" height="14" rx="1.2" />
  </svg>
);

export const IconPlay = ({ className, size = 14 }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M8 5.5v13l11-6.5z" fill="currentColor" stroke="none" />
  </svg>
);

export const IconMic = ({ className, size = 14 }: IconProps) => (
  <svg {...base(size)} className={className}>
    <rect x="9" y="3" width="6" height="10" rx="3" />
    <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" />
  </svg>
);

export const IconWaves = ({ className, size = 14 }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M3 12h2.5l1.6-4.5L9 16l2.2-7 1.9 5.5L15 10l1.8 3.5H21" />
  </svg>
);

export const IconExport = ({ className, size = 14 }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M12 16V4m0 0L8 8m4-4 4 4M5 16v2.5A1.5 1.5 0 0 0 6.5 20h11A1.5 1.5 0 0 0 19 18.5V16" />
  </svg>
);

export const IconSearch = ({ className, size = 14 }: IconProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="11" cy="11" r="6" />
    <path d="m16 16 4 4" />
  </svg>
);

export const IconBroom = ({ className, size = 14 }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M4 20l4.5-4.5M14 4l6 6-8.5 8.5L5.5 12.5 14 4z" />
  </svg>
);

export const IconCheck = ({ className, size = 14 }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="m5 13 4.5 4.5L19 7" />
  </svg>
);

/* ----------------------------------------------------------- small pieces */
export function GhostPill({
  children,
  className,
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[10.5px]", className)}
      style={style}
    >
      {children}
    </span>
  );
}

export function GhostButton({
  children,
  onClick,
  title,
  className,
  style,
}: {
  children: ReactNode;
  onClick?: () => void;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] transition-all duration-300 hover:-translate-y-[1px]",
        className,
      )}
      style={style}
    >
      {children}
    </button>
  );
}
