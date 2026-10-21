import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "./utils/cn";
import { THEMES } from "./themes";
import { SESSIONS, fmtClock, type CommittedLine, type Session } from "./data";
import { usePrefersReducedMotion } from "./hooks/usePrefersReducedMotion";
import { useTranscriptPlayer } from "./hooks/useTranscriptPlayer";
import { Backdrop } from "./components/Backdrop";
import { TopBar } from "./components/TopBar";
import { DesignRail } from "./components/DesignRail";
import { HistoryPanel } from "./components/HistoryPanel";
import { LiveCaption } from "./components/LiveCaption";

const SPEEDS = [0.75, 1, 1.25, 1.5];

export default function App() {
  const reduced = usePrefersReducedMotion();

  const [themeIdx, setThemeIdx] = useState(0);
  const [prevThemeIdx, setPrevThemeIdx] = useState<number | null>(null);
  const [panelOpen, setPanelOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth >= 768
  );
  const [sessionIdx, setSessionIdx] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [elapsed, setElapsed] = useState(0);
  const [committed, setCommitted] = useState<CommittedLine[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [sceneFlash, setSceneFlash] = useState(true);

  const theme = THEMES[themeIdx];
  const session = SESSIONS[sessionIdx];

  const prevTimer = useRef<number | undefined>(undefined);
  const flashTimer = useRef<number | undefined>(undefined);
  const toastTimer = useRef<number | undefined>(undefined);

  /* ---------- ambience ---------- */

  // warm the cache so scene switches glide
  useEffect(() => {
    THEMES.forEach((t) => {
      const img = new Image();
      img.src = t.wallpaper;
    });
  }, []);

  // opening flourish: show the first scene title, then let it rest
  useEffect(() => {
    flashTimer.current = window.setTimeout(() => setSceneFlash(false), 3200);
    return () => window.clearTimeout(flashTimer.current);
  }, []);

  /* ---------- session clock ---------- */

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => window.clearInterval(id);
  }, [playing]);

  /* ---------- scene switching ---------- */

  const goTheme = useCallback(
    (target: number) => {
      const n = ((target % THEMES.length) + THEMES.length) % THEMES.length;
      if (n === themeIdx) return;
      setPrevThemeIdx(themeIdx);
      setThemeIdx(n);
      window.clearTimeout(prevTimer.current);
      prevTimer.current = window.setTimeout(() => setPrevThemeIdx(null), 1000);
      setSceneFlash(true);
      window.clearTimeout(flashTimer.current);
      flashTimer.current = window.setTimeout(() => setSceneFlash(false), 2600);
    },
    [themeIdx]
  );

  /* ---------- transcription engine ---------- */

  const mode = theme.caption.reveal === "type" || theme.caption.reveal === "blur" ? "chars" : "words";

  const handleCommit = useCallback(
    (lineIdx: number) => {
      const line = session.lines[lineIdx];
      if (!line) return;
      setCommitted((c) => [
        ...c,
        {
          speaker: line.speaker,
          text: line.text,
          t: fmtClock(session.startSec + c.length * 8 + 7),
        },
      ]);
    },
    [session]
  );

  const handleCycle = useCallback(() => setCommitted([]), []);

  const player = useTranscriptPlayer(session.lines, {
    playing,
    speed,
    mode,
    reduced,
    onCommit: handleCommit,
    onCycle: handleCycle,
  });

  const restart = useCallback(() => {
    setCommitted([]);
    player.restart();
  }, [player]);

  /* ---------- library actions ---------- */

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2200);
  }, []);

  const handleReplay = useCallback(
    (id: string) => {
      const idx = SESSIONS.findIndex((s) => s.id === id);
      if (idx < 0) return;
      setSessionIdx(idx);
      setCommitted([]);
      setPlaying(true);
      setElapsed(0);
      showToast(idx === sessionIdx ? "Restarting this take" : `Replaying “${SESSIONS[idx].title}”`);
    },
    [sessionIdx, showToast]
  );

  const handleCopy = useCallback(
    async (s: Session) => {
      const body = [
        s.title,
        `${s.date} · ${s.duration}`,
        "",
        ...s.lines.map((l) => (l.speaker ? `${l.speaker}: ${l.text}` : l.text)),
      ].join("\n");
      try {
        await navigator.clipboard.writeText(body);
        showToast("Transcript copied to clipboard");
      } catch {
        showToast("Couldn't copy — clipboard is blocked");
      }
    },
    [showToast]
  );

  /* ---------- keyboard ---------- */

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return;
      if (e.key === "ArrowRight") goTheme(themeIdx + 1);
      else if (e.key === "ArrowLeft") goTheme(themeIdx - 1);
      else if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goTheme, themeIdx]);

  /* ---------- render ---------- */

  const textShadow = (theme.vars as Record<string, string>)["--shadow"] ?? "0 2px 14px rgba(0,0,0,0.6)";

  return (
    <div className="relative h-full w-full overflow-hidden font-body" style={theme.vars}>
      <Backdrop theme={theme} prevTheme={prevThemeIdx !== null ? THEMES[prevThemeIdx] : null} />

      <TopBar
        themeIndex={themeIdx}
        themeCount={THEMES.length}
        themeName={theme.name}
        onNextTheme={() => goTheme(themeIdx + 1)}
        onPrevTheme={() => goTheme(themeIdx - 1)}
        panelOpen={panelOpen}
        onTogglePanel={() => setPanelOpen((o) => !o)}
        elapsed={elapsed}
        playing={playing}
      />

      <DesignRail themes={THEMES} activeIndex={themeIdx} onSelect={goTheme} />

      {/* scene title — a soft announcement whenever the design changes */}
      {sceneFlash && (
        <div key={theme.id} className="pointer-events-none absolute top-[86px] left-6 z-20 md:top-24 md:left-24">
          <p className="font-mono text-[9px] tracking-[0.4em] text-[var(--caption-ink)]/70 uppercase" style={{ textShadow: "0 1px 10px rgba(0,0,0,0.55)" }}>
            Scene {String(themeIdx + 1).padStart(2, "0")} — of {THEMES.length}
          </p>
          <h2
            className="name-in mt-1.5 font-display text-3xl font-medium text-[var(--caption-ink)] italic md:text-[42px] md:leading-tight"
            style={{ textShadow }}
          >
            {theme.name}
          </h2>
          <p className="mt-1 font-mono text-[10px] tracking-[0.22em] text-[var(--caption-ink)]/75" style={{ textShadow: "0 1px 10px rgba(0,0,0,0.55)" }}>
            {theme.mood}
          </p>
        </div>
      )}

      <LiveCaption
        line={player.line}
        words={player.words}
        pos={player.pos}
        phase={player.phase}
        caption={theme.caption}
        textShadow={textShadow}
        prevLine={committed.length > 0 ? committed[committed.length - 1] : null}
        panelOpen={panelOpen}
        playing={playing}
        speed={speed}
        onTogglePlay={() => setPlaying((p) => !p)}
        onRestart={restart}
        onCycleSpeed={() => {
          const next = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length];
          setSpeed(next);
          showToast(`Caption speed ${next}×`);
        }}
      />

      <HistoryPanel
        sessions={SESSIONS}
        activeSession={session}
        committed={committed}
        open={panelOpen}
        playing={playing}
        onClose={() => setPanelOpen(false)}
        onReplay={handleReplay}
        onCopy={handleCopy}
        reduced={reduced}
      />

      {/* reopen handle when the panel is tucked away */}
      {!panelOpen && (
        <button
          onClick={() => setPanelOpen(true)}
          className="toast-in fixed top-1/2 right-0 z-30 flex -translate-y-1/2 flex-col items-center gap-2.5 rounded-l-lg border border-r-0 border-[var(--line)] bg-[var(--panel)] px-1.5 py-4 backdrop-blur-xl transition-colors hover:bg-[var(--hover)]"
          aria-label="Show transcript history"
        >
          <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true" className="text-[var(--dim)]">
            <path d="M7.5 2.5 4 6l3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="font-mono text-[8px] tracking-[0.34em] text-[var(--dim)] uppercase [writing-mode:vertical-rl]">
            history
          </span>
        </button>
      )}

      {/* toast */}
      {toast && (
        <div className="toast-in fixed bottom-6 left-6 z-40 flex items-center gap-2.5 rounded-full border border-[var(--line)] bg-[var(--panel)] py-2.5 pr-4 pl-3 backdrop-blur-xl">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
          <span className="text-xs text-[var(--ink)]">{toast}</span>
        </div>
      )}

      {/* whisper of a hint, bottom right */}
      <p
        className={cn(
          "pointer-events-none absolute right-5 bottom-4 z-10 hidden font-mono text-[8.5px] tracking-[0.24em] text-[var(--caption-ink)]/50 uppercase md:block",
          panelOpen && "md:right-[380px]"
        )}
        style={{ textShadow: "0 1px 8px rgba(0,0,0,0.5)" }}
      >
        space — pause · ← → — scenes
      </p>
    </div>
  );
}
