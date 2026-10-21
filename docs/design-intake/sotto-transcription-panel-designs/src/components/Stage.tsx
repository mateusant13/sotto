import type { ReactNode } from "react";
import type { Scenario } from "../lib/scripts";
import { useMeasureHeight } from "../hooks/useMeasureHeight";
import { fmtTC } from "../lib/scripts";

interface StageProps {
  scenario: Scenario;
  onScenario: (id: Scenario["id"]) => void;
  scenarios: Scenario[];
  playing: boolean;
  onTogglePlay: () => void;
  speed: number;
  onCycleSpeed: () => void;
  ghost: boolean;
  onToggleGhost: () => void;
  hidden: boolean;
  onUnhide: () => void;
  panel: ReactNode;
  designKey: string;
  elapsed: number;
}

export function Stage({
  scenario,
  onScenario,
  scenarios,
  playing,
  onTogglePlay,
  speed,
  onCycleSpeed,
  ghost,
  onToggleGhost,
  hidden,
  onUnhide,
  panel,
  designKey,
  elapsed,
}: StageProps) {
  const [stageRef, stageH] = useMeasureHeight<HTMLDivElement>();

  const panelH = Math.max(Math.min(stageH - 40, 900), 320);
  const scale = panelH / 900;
  const panelW = 380 * scale;

  return (
    <div
      ref={stageRef}
      className="relative h-full w-full overflow-hidden bg-black"
    >
      {/* fundo com respiração lenta */}
      <div className="stage-kb absolute inset-0">
        <img
          key={scenario.id}
          src={scenario.image}
          alt=""
          className="fade-in h-full w-full object-cover"
          draggable={false}
        />
      </div>

      {/* vinheta + leitura do fundo */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 95% at 68% 42%, transparent 52%, rgba(0,0,0,0.58) 100%)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40"
        style={{
          background: "linear-gradient(to top, rgba(0,0,0,0.55), transparent)",
        }}
      />

      {/* crômio do cenário — o conteúdo que o painel sobrepõe */}
      <ScenarioChrome scenario={scenario} playing={playing} elapsed={elapsed} />

      {/* chip de contexto */}
      <div className="pointer-events-none absolute left-4 top-4 flex items-center gap-2 rounded-md border border-white/12 bg-black/45 px-3 py-1.5 backdrop-blur-sm">
        <span className="h-[6px] w-[6px] rounded-full bg-moss" />
        <span className="font-mono text-[10px] tracking-[0.14em] text-white/55 uppercase">
          fundo: {scenario.label} · {scenario.chrome}
        </span>
      </div>

      {/* o painel sotto — 380×900, à direita, sempre no topo */}
      <div
        className="absolute top-1/2 -translate-y-1/2 transition-all duration-300 ease-out"
        style={{
          right: 16,
          width: panelW,
          height: panelH,
          opacity: hidden ? 0 : 1,
          transform: hidden
            ? "translateY(-50%) translateX(28px)"
            : "translateY(-50%)",
          pointerEvents: ghost || hidden ? "none" : undefined,
        }}
      >
        <div
          key={designKey}
          className="panel-in relative"
          style={{
            width: 380,
            height: 900,
            transform: `scale(${scale})`,
            transformOrigin: "top left",
          }}
        >
          {panel}
        </div>
      </div>

      {/* aviso quando o painel está oculto */}
      {hidden && (
        <button
          onClick={onUnhide}
          className="rise absolute top-1/2 -translate-y-1/2 rounded-md border border-white/15 bg-black/70 px-3.5 py-2.5 backdrop-blur-md transition hover:border-accent/60 hover:bg-black/85"
          style={{ right: 16 }}
        >
          <span className="font-mono text-[11px] tracking-[0.1em] text-white/70">
            sotto oculto ·{" "}
            <span className="text-accent">
              Alt+C
            </span>{" "}
            traz de volta
          </span>
        </button>
      )}

      {/* controles do palco */}
      <div className="absolute bottom-4 left-4 flex flex-col items-start gap-2.5">
        <div className="flex overflow-hidden rounded-md border border-white/12 bg-black/55 backdrop-blur-md">
          {scenarios.map((s) => (
            <button
              key={s.id}
              onClick={() => onScenario(s.id)}
              className={`px-3.5 py-2 font-body text-[12px] font-medium transition-colors ${
                s.id === scenario.id
                  ? "bg-white/12 text-white"
                  : "text-white/45 hover:bg-white/[0.06] hover:text-white/75"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onTogglePlay}
            title={playing ? "pausar fala (espaço)" : "retomar fala (espaço)"}
            className="flex h-9 w-9 items-center justify-center rounded-md border border-white/12 bg-black/55 text-white/80 backdrop-blur-md transition hover:border-accent/50 hover:text-accent"
          >
            {playing ? (
              <svg width="11" height="12" viewBox="0 0 11 12" fill="currentColor">
                <rect x="0.5" width="3.4" height="12" rx="1" />
                <rect x="7" width="3.4" height="12" rx="1" />
              </svg>
            ) : (
              <svg width="11" height="12" viewBox="0 0 11 12" fill="currentColor">
                <path d="M0.8 1.1c0-.8.9-1.3 1.6-.9l8 4.9c.6.4.6 1.4 0 1.8l-8 4.9c-.7.4-1.6-.1-1.6-.9V1.1z" />
              </svg>
            )}
          </button>

          <button
            onClick={onCycleSpeed}
            title="velocidade da simulação"
            className="h-9 rounded-md border border-white/12 bg-black/55 px-3 font-mono text-[12px] text-white/70 tabular-nums backdrop-blur-md transition hover:border-white/25 hover:text-white"
          >
            {speed.toFixed(1).replace(".", ",")}×
          </button>

          <button
            onClick={onToggleGhost}
            title="modo fantasma: cliques atravessam o painel, como no app real"
            className={`h-9 rounded-md border px-3 font-body text-[12px] font-medium backdrop-blur-md transition ${
              ghost
                ? "border-amberx/60 bg-amberx/15 text-amberx"
                : "border-white/12 bg-black/55 text-white/55 hover:border-white/25 hover:text-white/85"
            }`}
          >
            fantasma
          </button>

          <span className="ml-1 hidden font-mono text-[10px] tracking-[0.08em] text-white/30 md:inline">
            espaço pausa · 1–5 troca direção · Alt+C oculta
          </span>
        </div>
      </div>

      {/* selo de escala */}
      <div className="pointer-events-none absolute bottom-4 right-4 hidden rounded border border-white/10 bg-black/40 px-2 py-1 font-mono text-[9.5px] tracking-[0.12em] text-white/30 lg:block">
        PAINEL 380×900 · ESCALA {(scale * 100).toFixed(0)}%
      </div>
    </div>
  );
}

/* ---------------- crômio por cenário ---------------- */

function ScenarioChrome({
  scenario,
  playing,
  elapsed,
}: {
  scenario: Scenario;
  playing: boolean;
  elapsed: number;
}) {
  if (scenario.id === "filme") {
    return (
      <div className="pointer-events-none absolute inset-x-0 bottom-0 hidden pb-14 sm:block">
        <div className="mx-auto w-[58%]">
          <div className="h-[3px] overflow-hidden rounded-full bg-white/15">
            <div className="film-progress h-full rounded-full bg-white/65" />
          </div>
          <div className="mt-2 flex items-center justify-between font-mono text-[10.5px] text-white/55">
            <span className="flex items-center gap-2">
              <svg width="9" height="10" viewBox="0 0 11 12" fill="currentColor">
                {playing ? (
                  <>
                    <rect x="0.5" width="3.4" height="12" rx="1" />
                    <rect x="7" width="3.4" height="12" rx="1" />
                  </>
                ) : (
                  <path d="M0.8 1.1c0-.8.9-1.3 1.6-.9l8 4.9c.6.4.6 1.4 0 1.8l-8 4.9c-.7.4-1.6-.1-1.6-.9V1.1z" />
                )}
              </svg>
              {fmtTC(1420 + elapsed)}
            </span>
            <span className="text-white/35">2:07:44</span>
          </div>
        </div>
      </div>
    );
  }

  if (scenario.id === "jogo") {
    return (
      <>
        <div className="pointer-events-none absolute right-5 top-5 hidden h-24 w-24 rounded-md border border-white/20 bg-black/30 p-2 backdrop-blur-[2px] lg:block">
          <div className="relative h-full w-full overflow-hidden rounded-sm border border-white/10">
            <span className="absolute left-1/2 top-1/2 h-[5px] w-[5px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/85" />
            <span className="absolute left-[26%] top-[30%] h-[4px] w-[4px] rounded-full bg-accent pulse-dot" />
            <span
              className="absolute left-[68%] top-[62%] h-[4px] w-[4px] rounded-full bg-accent pulse-dot"
              style={{ animationDelay: "0.6s" }}
            />
          </div>
          <p className="mt-1.5 text-center font-mono text-[8.5px] tracking-[0.2em] text-white/40">
            SETOR N-4
          </p>
        </div>
        <div className="pointer-events-none absolute bottom-16 right-6 hidden items-center gap-2.5 lg:flex">
          <span className="font-mono text-[10px] tracking-[0.18em] text-white/45">
            HP
          </span>
          <div className="h-[5px] w-28 overflow-hidden rounded-full bg-white/15">
            <div className="h-full w-[74%] rounded-full bg-white/70" />
          </div>
          <span className="font-mono text-[10px] text-white/45 tabular-nums">
            74
          </span>
        </div>
      </>
    );
  }

  // reunião
  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 hidden justify-center pt-4 sm:flex">
      <div className="flex items-center gap-3 rounded-lg border border-white/12 bg-black/45 px-4 py-2 backdrop-blur-md">
        <span className="flex items-center gap-1.5">
          <svg width="10" height="13" viewBox="0 0 10 14" fill="none" stroke="currentColor" strokeWidth="1.4" className="text-moss">
            <rect x="1.5" y="1" width="7" height="8" rx="3.5" />
            <path d="M0.5 7.5a4.5 4.5 0 0 0 9 0M5 12v1.5" />
          </svg>
          <span className="font-body text-[11.5px] font-medium text-white/70">
            Reunião semanal · 6 participantes
          </span>
        </span>
        <span className="h-3 w-px bg-white/15" />
        <span className="font-mono text-[10px] text-white/45 tabular-nums">
          {fmtTC(elapsed + 180)}
        </span>
        <span className="flex items-center gap-1 rounded bg-accent/20 px-1.5 py-0.5 font-mono text-[8.5px] font-semibold tracking-[0.14em] text-accent">
          <span className="pulse-dot h-[5px] w-[5px] rounded-full bg-accent" />
          GRAVANDO
        </span>
      </div>
    </div>
  );
}
