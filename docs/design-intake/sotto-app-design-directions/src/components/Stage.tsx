import { useState } from "react";
import { DESIGNS, SCENES, type DesignId } from "../data/designs";
import type { ClosedLine, LineStatus } from "../hooks/useTranscription";
import { Caption } from "./Caption";
import { Panel } from "./Panel";
import { IconPause, IconPlay } from "./bits";

interface Engine {
  history: ClosedLine[];
  forming: string[];
  status: LineStatus;
  tick: number;
  elapsed: number;
}

interface Props {
  design: DesignId;
  onDesign: (id: DesignId) => void;
  playing: boolean;
  onTogglePlay: () => void;
  speed: number;
  onSpeed: (v: number) => void;
  engine: Engine;
}

const SPEEDS = [
  { v: 0.6, label: "0.6×" },
  { v: 1, label: "1×" },
  { v: 1.6, label: "1.6×" },
];

const H3_WEIGHT: Record<DesignId, string> = {
  tele: "font-semibold uppercase tracking-wide",
  bcast: "font-semibold",
  mano: "italic font-medium",
  cine: "font-light",
  inst: "font-bold",
};

export function Stage({ design, onDesign, playing, onTogglePlay, speed, onSpeed, engine }: Props) {
  const [scene, setScene] = useState("noir");
  const active = DESIGNS.find((d) => d.id === design)!;
  const lastClosed = engine.history.length ? engine.history[engine.history.length - 1] : undefined;

  return (
    <section id="palco" className="relative h-[100svh] min-h-[640px] overflow-hidden bg-black">
      {/* ---------- fundo: o filme que não é seu ---------- */}
      <div className="absolute inset-0 overflow-hidden">
        {SCENES.map((s, i) => (
          <img
            key={s.id}
            src={s.src}
            alt=""
            className={
              "kenburns absolute inset-0 h-full w-full object-cover transition-opacity duration-[1400ms] " +
              (scene === s.id ? "opacity-100" : "opacity-0")
            }
            style={{ animationDuration: `${26 + i * 7}s` }}
          />
        ))}
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-black/55" />
        <div
          className="absolute inset-0"
          style={{ background: "radial-gradient(125% 95% at 45% 40%, transparent 42%, rgba(0,0,0,0.58) 100%)" }}
        />
        <div className="grain" />
      </div>

      {/* ---------- header ---------- */}
      <header className="absolute inset-x-0 top-0 z-30 flex h-14 items-center justify-between px-4 lg:px-8">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-[20px] font-extrabold tracking-tight text-bone">SOTTO</span>
          <span className="hidden font-bcast text-[9.5px] tracking-[0.22em] text-bone/45 sm:inline">
            LEGENDAS AO VIVO DO ÁUDIO DO PC
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-white/15 bg-black/35 px-2.5 py-1 font-bcast text-[9.5px] tracking-[0.18em] text-bone/70 backdrop-blur-sm">
            380 × 900
          </span>
          <span className="hidden rounded-full border border-white/15 bg-black/35 px-2.5 py-1 font-bcast text-[9.5px] tracking-[0.18em] text-bone/50 backdrop-blur-sm md:inline">
            SEMPRE NO TOPO
          </span>
          <span className="hidden rounded-full border border-white/15 bg-black/35 px-2.5 py-1 font-bcast text-[9.5px] tracking-[0.18em] text-bone/50 backdrop-blur-sm lg:inline">
            NUNCA ROUBA FOCO
          </span>
        </div>
      </header>

      {/* ---------- seletor de direção ---------- */}
      <nav
        className="no-scrollbar absolute left-3 right-3 top-[62px] z-30 flex gap-2 overflow-x-auto pb-1 lg:left-8 lg:right-auto"
        aria-label="Direções de design"
      >
        {DESIGNS.map((d) => {
          const isActive = d.id === design;
          return (
            <button
              key={d.id}
              onClick={() => onDesign(d.id)}
              aria-pressed={isActive}
              className={
                "group shrink-0 rounded-md border px-3 py-1.5 backdrop-blur-sm transition-all duration-300 " +
                (isActive
                  ? "-translate-y-0.5 border-transparent bg-black/65 text-bone"
                  : "border-white/12 bg-black/30 text-white/45 hover:-translate-y-0.5 hover:border-white/25 hover:text-white/85")
              }
              style={isActive ? { borderColor: d.accent, boxShadow: `0 0 26px ${d.accent}26` } : undefined}
            >
              <span className="flex items-baseline gap-2">
                <span className="font-bcast text-[9px] tracking-[0.2em]" style={{ color: d.accent }}>
                  {d.num}
                </span>
                <span className={d.fontClass + " text-[15px] leading-none " + H3_WEIGHT[d.id]}>{d.name}</span>
              </span>
            </button>
          );
        })}
      </nav>

      {/* ---------- painel 380×900 (histórico) ---------- */}
      <div className="sotto-panel">
        <Panel
          design={design}
          history={engine.history}
          forming={engine.forming}
          status={engine.status}
          tick={engine.tick}
          elapsed={engine.elapsed}
          playing={playing}
        />
      </div>

      {/* ---------- legenda ao vivo, embaixo ao centro ---------- */}
      <div className="sotto-caption">
        <Caption
          design={design}
          forming={engine.forming}
          status={engine.status}
          elapsed={engine.elapsed}
          lastClosed={lastClosed}
        />
      </div>

      {/* ---------- controles ---------- */}
      <div className="absolute bottom-4 left-3 z-30 flex flex-wrap items-center gap-3 lg:bottom-6 lg:left-8">
        <button
          onClick={onTogglePlay}
          aria-label={playing ? "Pausar simulação" : "Retomar simulação"}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-black/55 text-bone backdrop-blur-sm transition-all duration-300 hover:scale-105 hover:border-white/45"
        >
          {playing ? <IconPause /> : <IconPlay />}
        </button>

        <div className="flex gap-1 rounded-full border border-white/12 bg-black/45 p-1 backdrop-blur-sm">
          {SPEEDS.map((s) => (
            <button
              key={s.v}
              onClick={() => onSpeed(s.v)}
              className={
                "rounded-full px-2.5 py-1 font-bcast text-[10.5px] transition-all duration-200 " +
                (speed === s.v ? "bg-bone font-semibold text-ink" : "text-white/50 hover:text-white/90")
              }
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="flex gap-1.5">
          {SCENES.map((s) => (
            <button
              key={s.id}
              onClick={() => setScene(s.id)}
              className={
                "flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.16em] backdrop-blur-sm transition-all duration-300 " +
                (scene === s.id
                  ? "border-gold/70 bg-black/55 text-gold"
                  : "border-white/12 bg-black/35 text-white/45 hover:text-white/85")
              }
            >
              <span className={"h-1.5 w-1.5 rounded-full " + (scene === s.id ? "bg-gold" : "bg-white/30")} />
              {s.label}
            </button>
          ))}
        </div>

        <span className="hidden font-bcast text-[9px] tracking-[0.16em] text-white/30 xl:inline">
          1–5 TROCA A DIREÇÃO · ESPAÇO PAUSA · CENA: {active.name.toUpperCase()}
        </span>
      </div>

      {/* ---------- régua da direção ativa ---------- */}
      <div className="pointer-events-none absolute bottom-4 right-3 z-20 hidden max-w-[240px] text-right lg:block lg:bottom-6">
        <p className="font-bcast text-[9px] leading-relaxed tracking-[0.14em] text-white/35">
          {active.num} · {active.model.toUpperCase()}
        </p>
      </div>
    </section>
  );
}
