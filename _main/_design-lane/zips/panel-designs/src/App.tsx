import { useEffect, useMemo, useState } from "react";
import { DIRECTIONS, SCENARIOS, type Direction, type ScenarioId } from "./lib/scripts";
import { useTranscriber } from "./hooks/useTranscriber";
import { Stage } from "./components/Stage";
import {
  TeleprompterPanel,
  BroadcastPanel,
  ManuscriptPanel,
  CinemaPanel,
  InstrumentPanel,
  type PanelProps,
} from "./components/panels";

const PANELS: Record<Direction["key"], (p: PanelProps) => React.ReactNode> = {
  teleprompter: TeleprompterPanel,
  broadcast: BroadcastPanel,
  manuscript: ManuscriptPanel,
  cinema: CinemaPanel,
  instrument: InstrumentPanel,
};

export default function App() {
  const [designId, setDesignId] = useState(1);
  const [scenarioId, setScenarioId] = useState<ScenarioId>("filme");
  const [hidden, setHidden] = useState(false);
  const [ghost, setGhost] = useState(false);

  const scenario = useMemo(
    () => SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0],
    [scenarioId]
  );
  const direction = DIRECTIONS.find((d) => d.id === designId) ?? DIRECTIONS[0];
  const t = useTranscriber(scenario);

  const Panel = PANELS[direction.key];

  // atalhos: 1–5 direção · espaço pausa · Alt+C oculta o painel
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && e.code === "KeyC") {
        e.preventDefault();
        setHidden((h) => !h);
        return;
      }
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "BUTTON" || tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.code === "Space") {
        e.preventDefault();
        t.toggle();
        return;
      }
      if (!e.metaKey && !e.ctrlKey && !e.altKey && /^Digit[1-5]$/.test(e.code)) {
        setDesignId(Number(e.code.slice(5)));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [t.toggle]);

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden bg-ink font-body text-paper">
      {/* camadas ambiente */}
      <div className="glow-red pointer-events-none fixed inset-0" />
      <div className="glow-cold pointer-events-none fixed inset-0" />
      <div className="noise" />

      {/* cabeçalho */}
      <header className="rise relative z-10 flex h-14 shrink-0 items-center justify-between border-b border-white/[0.07] px-5">
        <div className="flex min-w-0 items-baseline gap-4">
          <span className="flex items-center gap-2.5">
            <span className="pulse-dot h-[8px] w-[8px] self-center rounded-full bg-accent shadow-[0_0_10px_rgba(232,87,79,0.8)]" />
            <span className="font-display text-[23px] font-bold tracking-tight text-paper">
              sotto
            </span>
          </span>
          <span className="hidden truncate text-[12.5px] text-white/35 md:inline">
            legendas ao vivo do áudio do PC — uma camada, não uma janela
          </span>
        </div>
        <div className="hidden shrink-0 items-center gap-1.5 sm:flex">
          {["380 × 900", "sempre no topo", "nunca rouba foco", "Alt+C"].map(
            (c) => (
              <span
                key={c}
                className="rounded border border-white/[0.12] px-2 py-1 font-mono text-[10px] tracking-[0.08em] text-white/50"
              >
                {c}
              </span>
            )
          )}
        </div>
      </header>

      {/* corpo */}
      <main className="relative z-10 flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* palco */}
        <section className="order-1 h-[54vh] shrink-0 lg:order-2 lg:h-auto lg:min-w-0 lg:flex-1">
          <Stage
            scenario={scenario}
            scenarios={SCENARIOS}
            onScenario={(id) => setScenarioId(id)}
            playing={t.playing}
            onTogglePlay={t.toggle}
            speed={t.speed}
            onCycleSpeed={t.cycleSpeed}
            ghost={ghost}
            onToggleGhost={() => setGhost((g) => !g)}
            hidden={hidden}
            onUnhide={() => setHidden(false)}
            designKey={direction.key}
            elapsed={t.elapsed}
            panel={
              <Panel
                history={t.history}
                current={t.current}
                speaking={t.speaking}
                playing={t.playing}
                elapsed={t.elapsed}
              />
            }
          />
        </section>

        {/* trilho de direções */}
        <aside className="rail-scroll order-2 min-h-0 flex-1 overflow-y-auto border-t border-white/[0.07] lg:order-1 lg:w-[408px] lg:flex-none lg:border-r lg:border-t-0 xl:w-[436px]">
          <div className="flex flex-col gap-7 px-5 py-6 xl:px-7">
            {/* seletor */}
            <div className="rise" style={{ animationDelay: "60ms" }}>
              <div className="mb-3 flex items-baseline justify-between">
                <h2 className="font-mono text-[10px] font-medium tracking-[0.28em] text-white/35 uppercase">
                  Direções de design
                </h2>
                <span className="font-mono text-[10px] text-white/25 tabular-nums">
                  05
                </span>
              </div>

              <div className="flex flex-col gap-1.5">
                {DIRECTIONS.map((d) => {
                  const active = d.id === designId;
                  return (
                    <button
                      key={d.id}
                      onClick={() => setDesignId(d.id)}
                      className={`group relative rounded-md border px-4 py-3 text-left transition-all duration-200 ${
                        active
                          ? "border-white/[0.14] bg-white/[0.05]"
                          : "border-transparent hover:translate-x-1 hover:bg-white/[0.03]"
                      }`}
                    >
                      {active && (
                        <span className="absolute top-3 bottom-3 left-0 w-[2.5px] rounded-full bg-accent" />
                      )}
                      <div className="flex items-center gap-3">
                        <span
                          className={`font-mono text-[10px] tabular-nums ${
                            active ? "text-accent" : "text-white/25"
                          }`}
                        >
                          {String(d.id).padStart(2, "0")}
                        </span>
                        <span
                          className={`font-display text-[17px] font-semibold tracking-tight ${
                            active ? "text-paper" : "text-white/75"
                          }`}
                        >
                          {d.name}
                        </span>
                        {d.tag && (
                          <span
                            className={`ml-auto rounded-full border px-2 py-[3px] text-[9.5px] font-medium tracking-[0.04em] ${
                              d.tag.tone === "accent"
                                ? "border-accent/40 bg-accent/10 text-accent"
                                : "border-amberx/40 bg-amberx/10 text-amberx"
                            }`}
                          >
                            {d.tag.text}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 pl-[26px] text-[12.5px] leading-snug text-white/40">
                        {d.model}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* notas da direção ativa */}
            <div
              key={direction.id}
              className="rise rounded-lg border border-white/[0.1] bg-white/[0.03] p-4.5"
            >
              <div className="mb-3.5 flex items-baseline justify-between">
                <h3 className="font-mono text-[10px] tracking-[0.24em] text-white/35 uppercase">
                  Notas — {direction.name}
                </h3>
                <span className="font-mono text-[10px] text-white/30">
                  {direction.font}
                </span>
              </div>
              <dl className="grid grid-cols-[104px_1fr] gap-x-3 gap-y-3 text-[12.5px] leading-relaxed">
                <dt className="flex items-start gap-2 pt-px font-medium text-moss">
                  <span className="mt-[6px] h-[6px] w-[6px] shrink-0 rounded-full bg-moss" />
                  Impacto
                </dt>
                <dd className="text-white/70">{direction.impacto}</dd>

                <dt className="flex items-start gap-2 pt-px font-medium text-amberx">
                  <span className="mt-[6px] h-[6px] w-[6px] shrink-0 rounded-full bg-amberx" />
                  Recomendação
                </dt>
                <dd className="text-white/70">{direction.recomendacao}</dd>

                <dt className="flex items-start gap-2 pt-px font-medium text-accent">
                  <span className="mt-[6px] h-[6px] w-[6px] shrink-0 rounded-full bg-accent" />
                  Risco
                </dt>
                <dd className="text-white/70">{direction.risco}</dd>
              </dl>
            </div>

            {/* a aposta */}
            <div className="rise border-l-2 border-accent pl-4" style={{ animationDelay: "120ms" }}>
              <h3 className="font-mono text-[10px] font-semibold tracking-[0.24em] text-accent uppercase">
                A aposta
              </h3>
              <p className="mt-2 text-[12.5px] leading-relaxed text-white/60">
                <strong className="font-semibold text-white/85">Teleprompter</strong>{" "}
                é a direção mais forte para o produto.{" "}
                <strong className="font-semibold text-white/85">Manuscrito</strong>{" "}
                é a mais interessante se a correção em tempo real for o
                diferencial que se quer tornar perceptível.
              </p>
            </div>

            {/* o que falta */}
            <div className="rise" style={{ animationDelay: "160ms" }}>
              <h3 className="mb-2.5 font-mono text-[10px] tracking-[0.24em] text-white/35 uppercase">
                O que ainda não dá pra saber
              </h3>
              <ul className="flex flex-col gap-2.5 text-[12.5px] leading-relaxed text-white/50">
                <li className="flex gap-2.5">
                  <span className="mt-[8px] h-px w-3 shrink-0 bg-white/25" />
                  Legibilidade real a ~1&nbsp;m, sobre imagem em movimento, só
                  se decide com teste visual — não estaticamente.
                </li>
                <li className="flex gap-2.5">
                  <span className="mt-[8px] h-px w-3 shrink-0 bg-white/25" />
                  O trade-off central: quanto mais evidente o estado
                  provisório, maior a disputa de atenção com o fundo.
                </li>
              </ul>
            </div>

            {/* atalhos */}
            <div
              className="rise flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-white/[0.07] pt-4"
              style={{ animationDelay: "200ms" }}
            >
              <span className="flex items-center gap-1.5 text-[11px] text-white/40">
                <span className="keycap">1</span>
                <span className="opacity-50">–</span>
                <span className="keycap">5</span>
                direção
              </span>
              <span className="flex items-center gap-1.5 text-[11px] text-white/40">
                <span className="keycap px-4">espaço</span>
                pausa a fala
              </span>
              <span className="flex items-center gap-1.5 text-[11px] text-white/40">
                <span className="keycap">Alt</span>
                <span className="opacity-50">+</span>
                <span className="keycap">C</span>
                oculta o painel
              </span>
            </div>

            <p className="rise pb-2 font-cinema text-[13px] italic text-white/25" style={{ animationDelay: "240ms" }}>
              sotto — do italiano: por baixo, em voz baixa.
            </p>
          </div>
        </aside>
      </main>
    </div>
  );
}
