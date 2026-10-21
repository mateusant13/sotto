import type { Theme } from "../themes";

interface Props {
  theme: Theme;
  running: boolean;
  level: number;
  speed: number;
  elapsed: number;
  lines: number;
  speakers: number;
  confidence: number;
  scriptTitle: string;
  sessionLabel: string;
  panelOpen: boolean;
  rightInset: number;
  themeIndex: number;
  themeCount: number;
  onToggle: () => void;
  onSpeed: () => void;
  onGallery: () => void;
  onTogglePanel: () => void;
  onImmersive: () => void;
  onPrev: () => void;
  onNext: () => void;
}

const IconPlay = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
    <path d="M4.5 2.8v10.4c0 .5.55.8.97.53l8.2-5.2a.64.64 0 0 0 0-1.06l-8.2-5.2A.64.64 0 0 0 4.5 2.8Z" />
  </svg>
);
const IconPause = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
    <rect x="3.4" y="2.6" width="3.4" height="10.8" rx="1.1" />
    <rect x="9.2" y="2.6" width="3.4" height="10.8" rx="1.1" />
  </svg>
);
const IconGrid = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
    <rect x="2" y="2" width="5" height="5" rx="1.3" />
    <rect x="9" y="2" width="5" height="5" rx="1.3" />
    <rect x="2" y="9" width="5" height="5" rx="1.3" />
    <rect x="9" y="9" width="5" height="5" rx="1.3" />
  </svg>
);
const IconPanel = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
    <rect x="1.9" y="2.6" width="12.2" height="10.8" rx="2" />
    <path d="M10.4 2.6v10.8" />
  </svg>
);
const IconEye = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
    <path d="M1.6 8S4.2 3.4 8 3.4 14.4 8 14.4 8 11.8 12.6 8 12.6 1.6 8 1.6 8Z" />
    <circle cx="8" cy="8" r="1.9" />
  </svg>
);

function Level({ level, color }: { level: number; color: string }) {
  return (
    <span className="flex items-end gap-[2.5px] h-3" aria-hidden>
      {[0.55, 0.85, 1, 0.7, 0.45, 0.3].map((m, i) => (
        <span
          key={i}
          className="w-[2px] rounded-full transition-[height] duration-150"
          style={{ height: `${Math.max(3, level * 12 * m)}px`, background: color, opacity: 0.4 + level * 0.55 * m }}
        />
      ))}
    </span>
  );
}

const mmss = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

export default function TopChrome(props: Props) {
  const {
    theme,
    running,
    level,
    speed,
    elapsed,
    lines,
    speakers,
    confidence,
    scriptTitle,
    panelOpen,
    rightInset,
    themeIndex,
    themeCount,
    onToggle,
    onSpeed,
    onGallery,
    onTogglePanel,
    onImmersive,
    onPrev,
    onNext,
  } = props;

  const { chrome, fonts } = theme;
  const btn =
    "inline-flex items-center gap-2 rounded-full transition-colors duration-200 px-3 py-1.5 whitespace-nowrap";
  const btnStyle = (active?: boolean) => ({
    fontFamily: fonts.ui,
    fontSize: "0.62rem",
    letterSpacing: "0.16em",
    textTransform: "uppercase" as const,
    color: active ? "var(--text)" : "color-mix(in srgb, var(--text) 72%, transparent)",
    background: active ? "color-mix(in srgb, var(--accent) 20%, transparent)" : "var(--surface-2)",
    border: `1px solid ${active ? "color-mix(in srgb, var(--accent) 42%, transparent)" : "var(--line)"}`,
  });

  const Mark = (
    <div className="flex items-center gap-2.5 select-none">
      <span className="relative flex h-6 w-6 items-center justify-center">
        <span
          className="absolute inset-0 rounded-full"
          style={{ background: "color-mix(in srgb, var(--accent) 24%, transparent)", border: "1px solid color-mix(in srgb, var(--accent) 46%, transparent)" }}
        />
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--accent)" }} />
      </span>
      <span style={{ fontFamily: fonts.display, fontSize: "0.98rem", letterSpacing: "-0.01em", color: "var(--text)" }}>
        Mumble
      </span>
    </div>
  );

  const LivePill = (
    <button
      onClick={onToggle}
      className={`${btn} order-first`}
      style={{
        fontFamily: fonts.ui,
        fontSize: "0.62rem",
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: running ? "#0c1013" : "var(--text)",
        background: running ? "var(--live)" : "var(--surface-2)",
        border: `1px solid ${running ? "var(--live)" : "var(--line)"}`,
        boxShadow: running ? "0 10px 30px -14px var(--live)" : "none",
      }}
      title="Start / pause listening (Space)"
    >
      {running ? <IconPause /> : <IconPlay />}
      {running ? "Listening" : "Paused"}
    </button>
  );

  const statsText = `${speakers} ${speakers === 1 ? "speaker" : "speakers"} · ${lines} lines · ${Math.round(
    confidence * 100,
  )}% conf.`;

  const Switcher = (
    <div
      className="flex items-center overflow-hidden rounded-full"
      style={{ border: "1px solid var(--line)", background: "var(--surface-2)" }}
    >
      <button
        onClick={onPrev}
        title="Previous design (←)"
        className="px-2.5 py-1.5 transition-opacity hover:opacity-70"
        style={{ fontFamily: fonts.ui, fontSize: "0.78rem", color: "var(--text)", lineHeight: 1 }}
      >
        ‹
      </button>
      <button
        onClick={onGallery}
        title="All twenty designs (G)"
        className="px-1 py-1.5 whitespace-nowrap transition-opacity hover:opacity-80"
        style={{ fontFamily: fonts.ui, fontSize: "0.62rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--text)" }}
      >
        {theme.n} · <span className="hidden xl:inline">{theme.name}</span>
      </button>
      <button
        onClick={onNext}
        title="Next design (→)"
        className="px-2.5 py-1.5 transition-opacity hover:opacity-70"
        style={{ fontFamily: fonts.ui, fontSize: "0.78rem", color: "var(--text)", lineHeight: 1 }}
      >
        ›
      </button>
    </div>
  );

  /* ---------------- header bar ---------------- */
  if (chrome === "bar") {
    return (
      <header
        className="absolute top-0 left-0 z-30 flex h-[62px] items-center gap-5 px-5 sm:px-8 transition-[right] duration-500"
        style={{
          right: rightInset,
          background: "linear-gradient(180deg, color-mix(in srgb, var(--page) 88%, transparent), transparent)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
        }}
      >
        {Mark}
        <div className="hidden items-center gap-3 lg:flex">
          <span className="h-4 w-px" style={{ background: "var(--line)" }} />
          <div className="leading-tight">
            <div style={{ fontFamily: fonts.ui, fontSize: "0.78rem", color: "var(--text)" }}>{scriptTitle}</div>
            <div style={{ fontFamily: fonts.ui, fontSize: "0.6rem", letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--dim)" }}>
              {props.sessionLabel}
            </div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2.5">
          <span className="hidden xl:flex items-center gap-2.5 mr-1">
            <Level level={level} color={running ? "var(--live)" : "var(--dim)"} />
            <span style={{ fontFamily: fonts.ui, fontSize: "0.62rem", letterSpacing: "0.14em", color: "var(--dim)" }}>{mmss(elapsed)}</span>
            <span className="hidden 2xl:inline" style={{ fontFamily: fonts.ui, fontSize: "0.62rem", letterSpacing: "0.06em", color: "color-mix(in srgb, var(--dim) 110%, transparent)" }}>
              {statsText}
            </span>
          </span>
          {Switcher}
          {LivePill}
          <button className={btn} style={btnStyle()} onClick={onSpeed} title="Playback speed (S)">
            {speed}×
          </button>
          <button className={btn} style={btnStyle(false)} onClick={onGallery} title="Designs (G)">
            <IconGrid />
            <span className="hidden sm:inline">
              {String(themeIndex + 1).padStart(2, "0")}/{themeCount}
            </span>
          </button>
          <button className={btn} style={btnStyle(panelOpen)} onClick={onTogglePanel} title="Toggle history panel (H)">
            <IconPanel />
          </button>
          <button className={btn} style={btnStyle(false)} onClick={onImmersive} title="Immersive mode (I)">
            <IconEye />
          </button>
        </div>
      </header>
    );
  }

  /* ---------------- floating pill ---------------- */
  if (chrome === "float") {
    return (
      <>
        <div className="absolute top-4 left-4 z-30 hidden xl:block sm:top-6 sm:left-7" style={{ padding: 2 }}>
          <div
            className="flex items-center gap-3 rounded-full px-4 py-2.5"
            style={{
              background: "var(--surface)",
              backdropFilter: "blur(var(--blur))",
              WebkitBackdropFilter: "blur(var(--blur))",
              border: "1px solid var(--line)",
              boxShadow: "var(--shadow)",
            }}
          >
            {Mark}
            <span className="h-4 w-px" style={{ background: "var(--line)" }} />
            <span style={{ fontFamily: fonts.ui, fontSize: "0.62rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--dim)" }}>
              {scriptTitle}
            </span>
          </div>
        </div>

        <div className="absolute top-4 left-1/2 z-30 -translate-x-1/2 sm:top-6">
          <div
            className="flex items-center gap-2 rounded-full px-2.5 py-2"
            style={{
              background: "var(--surface)",
              backdropFilter: "blur(var(--blur))",
              WebkitBackdropFilter: "blur(var(--blur))",
              border: "1px solid var(--line)",
              boxShadow: "var(--shadow)",
            }}
          >
            {LivePill}
            <span className="hidden items-center gap-2.5 px-1.5 sm:flex">
              <Level level={level} color={running ? "var(--live)" : "var(--dim)"} />
              <span style={{ fontFamily: fonts.ui, fontSize: "0.62rem", letterSpacing: "0.14em", color: "var(--dim)" }}>{mmss(elapsed)}</span>
            </span>
            {Switcher}
            <button className={btn} style={btnStyle()} onClick={onSpeed} title="Playback speed (S)">
              {speed}×
            </button>
            <button className={btn} style={btnStyle(false)} onClick={onGallery} title="Designs (G)">
              <IconGrid />
            </button>
            <button className={btn} style={btnStyle(panelOpen)} onClick={onTogglePanel} title="Toggle history panel (H)">
              <IconPanel />
            </button>
            <button className={btn} style={btnStyle(false)} onClick={onImmersive} title="Immersive mode (I)">
              <IconEye />
            </button>
          </div>
        </div>

        <div
          className="absolute top-[74px] left-1/2 z-30 hidden -translate-x-1/2 sm:block"
          style={{ fontFamily: fonts.ui, fontSize: "0.6rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "color-mix(in srgb, var(--text) 52%, transparent)" }}
        >
          {statsText}
        </div>
      </>
    );
  }

  /* ---------------- panel heading (no top bar) ---------------- */
  return (
    <div className="absolute bottom-6 left-6 z-30 flex flex-col items-start gap-3">
      <div
        className="flex items-center gap-3 rounded-full px-4 py-2.5"
        style={{
          background: "var(--surface)",
          backdropFilter: "blur(var(--blur))",
          WebkitBackdropFilter: "blur(var(--blur))",
          border: "1px solid var(--line)",
          boxShadow: "var(--shadow)",
        }}
      >
        {Mark}
        <span className="h-4 w-px" style={{ background: "var(--line)" }} />
        <span style={{ fontFamily: fonts.ui, fontSize: "0.62rem", letterSpacing: "0.14em", color: "var(--dim)" }}>{mmss(elapsed)}</span>
      </div>
      <div className="flex items-center gap-2">
        {LivePill}
        {Switcher}
        <button className={btn} style={btnStyle()} onClick={onSpeed} title="Playback speed (S)">
          {speed}×
        </button>
        <button className={btn} style={btnStyle(false)} onClick={onGallery} title="Designs (G)">
          <IconGrid />
          <span className="hidden sm:inline">Designs</span>
        </button>
        <button className={btn} style={btnStyle(panelOpen)} onClick={onTogglePanel} title="Toggle history panel (H)">
          <IconPanel />
        </button>
        <button className={btn} style={btnStyle(false)} onClick={onImmersive} title="Immersive mode (I)">
          <IconEye />
        </button>
      </div>
      <div style={{ fontFamily: fonts.ui, fontSize: "0.6rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "color-mix(in srgb, var(--text) 46%, transparent)" }}>
        {scriptTitle} · {statsText}
      </div>
    </div>
  );
}
