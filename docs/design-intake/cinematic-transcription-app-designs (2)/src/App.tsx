import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import Stage from "./components/Stage";
import LiveCaptions from "./components/LiveCaptions";
import HistoryPanel from "./components/HistoryPanel";
import TopChrome from "./components/TopChrome";
import DesignGallery from "./components/DesignGallery";
import { useTranscription } from "./hooks/useTranscription";
import { THEMES, themeById } from "./themes";

const SPEEDS = [0.75, 1, 1.5, 2];

export default function App() {
  const [themeId, setThemeId] = useState(THEMES[2].id); // cellar rose — a warm, low-lit opener
  const [panelOpen, setPanelOpen] = useState(true);
  const [immersive, setImmersive] = useState(false);
  const [gallery, setGallery] = useState(false);
  const [uiHint, setUiHint] = useState(false);
  const hintTimer = useRef<number | null>(null);

  const t = useTranscription();
  const { entries, partial, running, speed, level, elapsed, stats, scriptMeta, sessionLabel, autoScroll, actions } = t;
  const theme = themeById(themeId);
  const index = THEMES.findIndex((x) => x.id === themeId);

  /* ---------------- speakers → tones ---------------- */
  const speakerColor = useCallback(
    (name: string) => {
      const names = [...new Set([...entries.map((e) => e.speaker), ...(partial ? [partial.speaker] : [])])];
      const i = names.indexOf(name);
      const palette = ["var(--text)", "var(--accent)", "var(--accent-2)"];
      return palette[(i < 0 ? 0 : i) % palette.length];
    },
    [entries, partial],
  );

  /* ---------------- actions ---------------- */
  const cycle = useCallback((dir: number) => {
    setThemeId((cur) => {
      const i = THEMES.findIndex((x) => x.id === cur);
      return THEMES[(i + dir + THEMES.length) % THEMES.length].id;
    });
  }, []);

  const cycleSpeed = useCallback(() => {
    actions.setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length]);
  }, [actions, speed]);

  const exportTxt = useCallback(() => {
    const header = `Mumble transcript · ${sessionLabel}\n${"=".repeat(46)}\n`;
    let session = "";
    const body = entries
      .map((e, i) => {
        let out = "";
        if (e.session !== session) {
          session = e.session;
          out += `\n— ${session.toUpperCase()} —\n`;
        }
        const time = new Date(e.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        return `${out}${String(i + 1).padStart(3, "0")}  ${time}  ${e.speaker}: ${e.text}`;
      })
      .join("\n");
    const blob = new Blob([`${header}${body}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mumble-transcript.txt";
    a.click();
    URL.revokeObjectURL(url);
  }, [entries, sessionLabel]);

  /* ---------------- keyboard ---------------- */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
        if (e.key === "Escape") (el as HTMLInputElement).blur();
        return;
      }
      if (e.key === " ") {
        e.preventDefault();
        actions.toggle();
      } else if (e.key === "ArrowRight") {
        cycle(1);
      } else if (e.key === "ArrowLeft") {
        cycle(-1);
      } else if (e.key.toLowerCase() === "g") {
        setGallery((v) => !v);
      } else if (e.key.toLowerCase() === "h") {
        setPanelOpen((v) => !v);
      } else if (e.key.toLowerCase() === "i") {
        setImmersive((v) => !v);
      } else if (e.key.toLowerCase() === "s") {
        cycleSpeed();
      } else if (e.key === "Escape") {
        setGallery(false);
      } else if (/^[1-9]$/.test(e.key)) {
        const i = Math.min(Number(e.key) - 1, THEMES.length - 1);
        setThemeId(THEMES[i].id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [actions, cycle, cycleSpeed]);

  /* in immersive mode, reveal a small way out when the mouse moves */
  useEffect(() => {
    if (!immersive) return;
    const onMove = () => {
      setUiHint(true);
      if (hintTimer.current) window.clearTimeout(hintTimer.current);
      hintTimer.current = window.setTimeout(() => setUiHint(false), 2600);
    };
    window.addEventListener("mousemove", onMove);
    onMove();
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (hintTimer.current) window.clearTimeout(hintTimer.current);
    };
  }, [immersive]);

  const chromeHidden = immersive;
  const panelVisible = panelOpen && !immersive;
  const topInset = chromeHidden ? 0 : theme.chrome === "sidebarHead" ? 0 : 64;
  const captionRight = panelVisible ? theme.panel.width + 34 : 0;

  const previous = entries[entries.length - 1] ?? null;

  return (
    <div className="relative h-full w-full overflow-hidden" style={theme.vars as CSSProperties}>
      <Stage theme={theme} topInset={topInset} />

      {!chromeHidden && (
        <TopChrome
          theme={theme}
          running={running}
          level={level}
          speed={speed}
          elapsed={elapsed}
          lines={entries.length}
          speakers={stats.speakers.length}
          confidence={stats.avgConf}
          scriptTitle={scriptMeta.title}
          sessionLabel={sessionLabel}
          panelOpen={panelOpen}
          rightInset={panelVisible ? theme.panel.width : 0}
          themeIndex={index}
          themeCount={THEMES.length}
          onToggle={actions.toggle}
          onSpeed={cycleSpeed}
          onGallery={() => setGallery(true)}
          onTogglePanel={() => setPanelOpen((v) => !v)}
          onImmersive={() => setImmersive(true)}
          onPrev={() => cycle(-1)}
          onNext={() => cycle(1)}
        />
      )}

      {/* ---------- live captions, centred in the middle of the room ---------- */}
      <div
        className="pointer-events-none absolute z-[25] transition-[right] duration-500"
        style={{ left: 0, right: captionRight, bottom: theme.caption.bottom }}
      >
        <div
          className="px-5 sm:px-10"
          style={{
            width: "100%",
            maxWidth: theme.caption.maxw,
            marginLeft: theme.caption.align === "center" ? "auto" : "4vw",
            marginRight: theme.caption.align === "center" ? "auto" : undefined,
          }}
        >
          <div className="pointer-events-auto">
            <LiveCaptions
              theme={theme}
              partial={partial}
              previous={previous}
              running={running}
              level={level}
              speakerColor={speakerColor}
            />
          </div>
        </div>
      </div>

      {panelVisible && (
        <HistoryPanel
          theme={theme}
          entries={entries}
          partial={partial}
          running={running}
          speakerColor={speakerColor}
          onClear={actions.clearHistory}
          onExport={exportTxt}
          autoScroll={autoScroll}
          setAutoScroll={actions.setAutoScroll}
          sessionLabel={sessionLabel}
          wpm={stats.wpm}
          onCollapse={() => setPanelOpen(false)}
        />
      )}

      {/* ---------- quiet nudge when the panel is out of the way ---------- */}
      {!panelOpen && !immersive && (
        <button
          onClick={() => {
            setPanelOpen(true);
            setImmersive(false);
          }}
          className="absolute bottom-6 right-6 z-30 rounded-full px-3.5 py-2 transition-all duration-500"
          style={{
            fontFamily: theme.fonts.ui,
            fontSize: "0.6rem",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: "var(--text)",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            backdropFilter: "blur(var(--blur))",
            WebkitBackdropFilter: "blur(var(--blur))",
            opacity: 0.92,
          }}
          title="Bring the history panel back (H)"
        >
          history · H
        </button>
      )}

      {immersive && (
        <button
          onClick={() => setImmersive(false)}
          className="absolute top-6 right-6 z-30 rounded-full px-4 py-2 transition-opacity duration-500"
          style={{
            fontSize: "0.6rem",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: "var(--text)",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            backdropFilter: "blur(var(--blur))",
            opacity: uiHint ? 0.95 : 0,
            pointerEvents: uiHint ? "auto" : "none",
          }}
        >
          leave immersive · I
        </button>
      )}

      {gallery && (
        <DesignGallery themes={THEMES} activeId={themeId} onPick={(id) => setThemeId(id)} onClose={() => setGallery(false)} />
      )}

    </div>
  );
}
