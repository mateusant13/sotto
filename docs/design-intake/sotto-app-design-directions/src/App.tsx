import { useEffect, useState } from "react";
import { DESIGNS, type DesignId } from "./data/designs";
import { useTranscription } from "./hooks/useTranscription";
import { Stage } from "./components/Stage";
import { Ticker } from "./components/Ticker";
import { Directions } from "./components/Directions";
import { Verdict } from "./components/Verdict";
import { useReveal } from "./components/bits";

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="rounded border border-white/15 bg-ink3 px-1.5 py-0.5 font-bcast text-[9.5px] tracking-[0.1em] text-bone/80">
      {children}
    </kbd>
  );
}

export default function App() {
  const [design, setDesign] = useState<DesignId>("tele");
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);

  const engine = useTranscription(playing, speed);
  useReveal();

  // atalhos: 1–5 troca de direção, espaço pausa/retoma a simulação
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
      const idx = ["1", "2", "3", "4", "5"].indexOf(e.key);
      if (idx >= 0) setDesign(DESIGNS[idx].id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const pickAndScroll = (id: DesignId) => {
    setDesign(id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <main className="min-h-screen bg-ink">
      <Stage
        design={design}
        onDesign={setDesign}
        playing={playing}
        onTogglePlay={() => setPlaying((p) => !p)}
        speed={speed}
        onSpeed={setSpeed}
        engine={engine}
      />

      <Ticker history={engine.history} />

      <Directions onPick={pickAndScroll} />

      <Verdict />

      <footer className="border-t border-white/8 bg-ink py-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 md:flex-row md:items-center md:justify-between lg:px-8">
          <div>
            <p className="font-display text-[17px] font-extrabold tracking-tight text-bone">SOTTO</p>
            <p className="mt-1.5 max-w-sm text-[12px] leading-relaxed text-fog">
              Uma camada de percepção sobre o que você já está vendo — 380 × 900 px, sempre no topo, nunca rouba o
              foco.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2.5 text-[11px] text-fog">
            <span className="flex items-center gap-2">
              <Kbd>1–5</Kbd> direções
            </span>
            <span className="flex items-center gap-2">
              <Kbd>ESPAÇO</Kbd> pausa a demo
            </span>
            <span className="flex items-center gap-2">
              <Kbd>ALT C</Kbd> oculta o painel <span className="text-bone/30">(no app)</span>
            </span>
            <span className="flex items-center gap-2">
              <Kbd>ALT H</Kbd> histórico <span className="text-bone/30">(no app)</span>
            </span>
          </div>
        </div>
        <div className="mx-auto mt-8 max-w-6xl px-5 lg:px-8">
          <p className="font-bcast text-[9px] tracking-[0.22em] text-bone/30">
            SOTTO · ESTUDO DE DIREÇÃO · TRANSCRIÇÃO SIMULADA PARA FINS DE DESIGN
          </p>
        </div>
      </footer>
    </main>
  );
}
