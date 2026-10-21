import { useCallback, useEffect, useState } from "react";
import { CaptionStage } from "@/components/CaptionStage";
import { TopBar, WallpaperLayer } from "@/components/Chrome";
import { DesignSwitcher } from "@/components/DesignSwitcher";
import { HistoryPanel } from "@/components/HistoryPanel";
import { scenes, type Scene } from "@/data/scenes";
import { useTranscription } from "@/hooks/useTranscription";

export default function App() {
  const [index, setIndex] = useState(0);
  const [previous, setPrevious] = useState<Scene | null>(null);
  const [quiet, setQuiet] = useState(false);
  const [switcherOpen, setSwitcherOpen] = useState(true);
  const [vw, setVw] = useState(() => (typeof window === "undefined" ? 1440 : window.innerWidth));

  const scene = scenes[index];
  const { segments, live, paused, elapsed, last, togglePause, clearSession } = useTranscription(scene);

  const select = useCallback(
    (next: number) => {
      const target = ((next % scenes.length) + scenes.length) % scenes.length;
      if (target === index) return;
      setPrevious(scene);
      setIndex(target);
    },
    [index, scene],
  );

  useEffect(() => {
    const onResize = () => setVw(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const k = event.key;
      if (k === "ArrowRight" || k === "ArrowDown") {
        event.preventDefault();
        select(index + 1);
      } else if (k === "ArrowLeft" || k === "ArrowUp") {
        event.preventDefault();
        select(index - 1);
      } else if (k >= "1" && k <= "9") {
        select(Number(k) - 1);
      } else if (k === "0") {
        select(9);
      } else if (event.code === "Space") {
        event.preventDefault();
        togglePause();
      } else if (k.toLowerCase() === "h") {
        setSwitcherOpen((open) => !open);
      } else if (k.toLowerCase() === "f") {
        setQuiet((q) => !q);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, select, togglePause]);

  const panelShown = vw >= 960 && !quiet;
  const panelInset = scene.panelWidth + 52;
  // Centre the caption strip like a film subtitle, then bias it toward the true
  // middle of the frame — while always leaving clear air in front of the rail.
  const captionWidth = Math.min(scene.caption.maxWidth + 64, vw - panelInset - 80);
  const slack = Math.max(0, vw - panelInset - captionWidth);
  const bias = Math.min(200, Math.max(0, slack / 2 - 28));
  const rightInset = panelShown ? Math.max(0, panelInset - bias) : 0;

  return (
    <main className="relative h-full w-full overflow-hidden" style={{ background: "#07080a", color: scene.panel.text }}>
      <WallpaperLayer scene={scene} previous={previous} />

      {/* film-frame bars, only while in quiet immersion */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 z-10 transition-opacity duration-1000"
        style={{ height: "7vh", background: "linear-gradient(180deg, rgba(0,0,0,0.5), transparent)", opacity: quiet ? 1 : 0 }}
      />
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 z-10 transition-opacity duration-1000"
        style={{ height: "11vh", background: "linear-gradient(0deg, rgba(0,0,0,0.5), transparent)", opacity: quiet ? 1 : 0 }}
      />

      {!quiet && (
        <TopBar key={scene.id} scene={scene} index={index} total={scenes.length} elapsed={elapsed} paused={paused} />
      )}

      {!quiet && (
        <DesignSwitcher
          scenes={scenes}
          index={index}
          onSelect={select}
          open={switcherOpen}
          onToggle={() => setSwitcherOpen((open) => !open)}
        />
      )}

      {panelShown && (
        <aside
          className="absolute right-0 top-0 z-30 flex h-full flex-col"
          style={{ width: scene.panelWidth + 52 }}
        >
          <div className="flex h-full flex-col px-[26px] py-6">
            <HistoryPanel
              key={scene.id}
              scene={scene}
              segments={segments}
              live={live}
              paused={paused}
              elapsed={elapsed}
              onToggle={togglePause}
              onClear={clearSession}
            />
          </div>
        </aside>
      )}

      <CaptionStage
        key={scene.id}
        scene={scene}
        live={live}
        last={last}
        paused={paused}
        rightInset={rightInset}
      />

      {quiet && (
        <p
          className="anim-chrome f-dm absolute bottom-5 right-6 z-30 text-[10px] uppercase tracking-[0.24em]"
          style={{ color: "rgba(244,242,238,0.34)" }}
        >
          press f to bring the panel back
        </p>
      )}

      {!quiet && !panelShown && (
        <p
          className="anim-chrome f-dm absolute bottom-5 right-6 z-30 text-[10px] uppercase tracking-[0.24em]"
          style={{ color: "rgba(244,242,238,0.4)" }}
        >
          history rail opens on a wider window
        </p>
      )}
    </main>
  );
}
