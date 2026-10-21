import { useEffect, useState } from "react";
import { cn } from "../utils/cn";
import { fmtElapsed } from "../data";

interface TopBarProps {
  themeIndex: number;
  themeCount: number;
  themeName: string;
  onNextTheme: () => void;
  onPrevTheme: () => void;
  panelOpen: boolean;
  onTogglePanel: () => void;
  elapsed: number;
  playing: boolean;
}

function LogoMark() {
  return (
    <svg width="27" height="24" viewBox="0 0 27 24" fill="none" aria-hidden="true">
      <rect x="1" y="9.5" width="2" height="5" rx="1" fill="var(--accent)" opacity="0.55" />
      <rect x="5" y="6.5" width="2" height="11" rx="1" fill="var(--accent)" opacity="0.75" />
      <rect x="9" y="9" width="2" height="6" rx="1" fill="var(--accent)" opacity="0.55" />
      <path
        d="M19.2 2.6a9.2 9.2 0 1 0 5.2 15.6A7.4 7.4 0 0 1 14.6 12c0-3.6 2.6-6.6 6-7.3a9.4 9.4 0 0 0-1.4-2.1Z"
        fill="var(--accent)"
      />
    </svg>
  );
}

const iconBtn =
  "grid h-9 w-9 place-items-center rounded-full border border-[var(--line)] text-[var(--dim)] transition-all duration-200 hover:border-[var(--accent)] hover:text-[var(--ink)] hover:bg-[var(--hover)] active:scale-90";

export function TopBar({
  themeIndex,
  themeCount,
  themeName,
  onNextTheme,
  onPrevTheme,
  panelOpen,
  onTogglePanel,
  elapsed,
  playing,
}: TopBarProps) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 20_000);
    return () => window.clearInterval(id);
  }, []);

  const clock = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const day = now.toLocaleDateString([], { weekday: "short" });

  return (
    <header
      className={cn(
        "absolute top-0 left-0 z-20 flex w-full items-center justify-between gap-3 px-5 py-4 transition-[padding] duration-500 md:px-7",
        panelOpen && "md:pr-[384px]"
      )}
    >
      {/* brand */}
      <div className="flex items-center gap-3.5">
        <LogoMark />
        <div className="leading-none">
          <p className="font-display italic text-[21px] font-medium tracking-tight text-[var(--ink)]">
            Nocturne
          </p>
          <p className="mt-1 font-mono text-[8.5px] tracking-[0.34em] text-[var(--dim)] uppercase">
            live captions · ten scenes
          </p>
        </div>
      </div>

      {/* center — the hour */}
      <div className="hidden items-center gap-3 lg:flex">
        <span className="font-mono text-xs text-[var(--dim)]">{day}</span>
        <span className="h-3 w-px bg-[var(--line)]" />
        <span className="font-mono text-xs text-[var(--ink)]">{clock}</span>
      </div>

      {/* status cluster */}
      <div className="flex items-center gap-2.5">
        <div className="flex items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--panel-2)] py-1.5 pr-3 pl-2.5 backdrop-blur-sm">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full bg-[var(--accent)]",
              playing ? "pulse-dot" : "opacity-40"
            )}
          />
          <span className="font-mono text-[9px] tracking-[0.26em] text-[var(--dim)] uppercase">
            {playing ? "Rec" : "Hold"}
          </span>
          <span className="font-mono text-xs text-[var(--ink)] tabular-nums">{fmtElapsed(elapsed)}</span>
        </div>

        <span className="hidden rounded-full border border-[var(--line)] px-2.5 py-1.5 font-mono text-[10px] tracking-[0.18em] text-[var(--dim)] sm:block">
          EN
        </span>

        {/* scene cycler */}
        <div className="flex items-center">
          <button
            onClick={onPrevTheme}
            aria-label="Previous scene"
            title="Previous scene (←)"
            className={cn(iconBtn, "h-9 w-7 rounded-r-none border-r-0")}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M7.5 2.5 4 6l3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <button
            onClick={onNextTheme}
            title={`${themeName} — click for next scene (→)`}
            className="flex h-9 items-center gap-2 border-y border-[var(--line)] bg-[var(--panel-2)] px-3 font-mono text-[10px] tracking-[0.14em] text-[var(--dim)] backdrop-blur-sm transition-colors hover:text-[var(--ink)]"
          >
            <span className="text-[var(--ink)] tabular-nums">
              {String(themeIndex + 1).padStart(2, "0")}
            </span>
            <span className="opacity-60">/ {String(themeCount).padStart(2, "0")}</span>
          </button>
          <button
            onClick={onNextTheme}
            aria-label="Next scene"
            title="Next scene (→)"
            className={cn(iconBtn, "h-9 w-7 rounded-l-none border-l-0")}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="m4.5 2.5 3.5 3.5-3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* mic */}
        <button className={cn(iconBtn, "hidden sm:grid")} aria-label="Microphone active" title="Microphone — active">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <rect x="5" y="1" width="4" height="7.5" rx="2" stroke="currentColor" strokeWidth="1.3" />
            <path d="M2.5 6.5a4.5 4.5 0 0 0 9 0M7 11v2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </button>

        {/* panel toggle */}
        <button
          onClick={onTogglePanel}
          className={iconBtn}
          aria-label={panelOpen ? "Hide transcript history" : "Show transcript history"}
          title={panelOpen ? "Hide history" : "Show history"}
        >
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
            <rect x="1.5" y="2.5" width="12" height="10" rx="2" stroke="currentColor" strokeWidth="1.3" />
            <path d="M9.5 2.5v10" stroke="currentColor" strokeWidth="1.3" />
            <path
              d={panelOpen ? "m11.8 6-1.2 1.5L11.8 9" : "m10.6 6 1.2 1.5-1.2 1.5"}
              stroke="currentColor"
              strokeWidth="1.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </header>
  );
}
