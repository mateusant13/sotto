import { useEffect, useState } from "react";
import type { Line } from "../hooks/useTranscriber";
import { fmtTC } from "../lib/scripts";

export interface PanelProps {
  history: Line[];
  current: string;
  speaking: boolean;
  playing: boolean;
  elapsed: number;
}

/* ------------------------------------------------------------------ */
/* 01 · TELEPROMPTER — fluxo contínuo de leitura                       */
/* ------------------------------------------------------------------ */

export function TeleprompterPanel({ history, current, speaking }: PanelProps) {
  const lines = history.slice(-9);
  const n = lines.length;

  return (
    <div
      className="absolute inset-0 flex flex-col font-cond"
      style={{
        background:
          "linear-gradient(to right, rgba(5,7,10,0.82) 0%, rgba(5,7,10,0.42) 62%, rgba(5,7,10,0.12) 100%)",
        backdropFilter: "blur(2px)",
      }}
    >
      <div className="flex items-center gap-2 px-7 pt-6">
        <span className="text-[11px] font-body font-semibold uppercase tracking-[0.34em] text-white/30">
          sotto
        </span>
        <span
          className={`h-[5px] w-[5px] rounded-full ${
            speaking ? "bg-accent pulse-dot" : "bg-white/20"
          }`}
        />
      </div>

      <div className="mask-fade-top flex flex-1 flex-col justify-end gap-[14px] overflow-hidden px-7 pb-14 pt-24">
        {lines.map((l, i) => (
          <p
            key={l.id}
            className="line-in text-[25px] leading-[1.12] font-medium text-white"
            style={{ opacity: Math.max(0.6 - (n - 1 - i) * 0.08, 0.14) }}
          >
            {l.text}
          </p>
        ))}

        {current && (
          <p className="tp-active ml-[7px] text-[32px] leading-[1.1] font-semibold text-white">
            {current}
          </p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 02 · BROADCAST — uma transmissão acontecendo agora                  */
/* ------------------------------------------------------------------ */

export function BroadcastPanel({
  history,
  current,
  speaking,
  playing,
  elapsed,
}: PanelProps) {
  const [buffer, setBuffer] = useState(38);
  const [conf, setConf] = useState("0.94");

  useEffect(() => {
    if (!playing) return;
    const iv = setInterval(() => {
      setBuffer(30 + Math.floor(Math.random() * 24));
      setConf((0.88 + Math.random() * 0.11).toFixed(2));
    }, 900);
    return () => clearInterval(iv);
  }, [playing]);

  const lines = history.slice(-11);

  return (
    <div className="absolute inset-0 flex flex-col border border-white/10 bg-[rgba(8,10,13,0.88)] font-mono backdrop-blur-[6px]">
      {/* cabeçalho técnico */}
      <div className="border-b border-white/10 px-4 pb-2.5 pt-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span
              className={`h-[7px] w-[7px] rounded-full ${
                playing ? "bg-accent pulse-dot" : "bg-white/25"
              }`}
            />
            <span className="text-[10px] font-semibold tracking-[0.18em] text-accent">
              REC
            </span>
            <span className="text-[10px] tracking-[0.18em] text-white/50">
              SOTTO / MONITOR 01
            </span>
          </div>
          <span className="text-[12px] font-medium text-white/85 tabular-nums">
            {fmtTC(elapsed)}
          </span>
        </div>
        <div className="mt-1.5 text-[9.5px] tracking-[0.14em] text-white/30">
          PT-BR · 48 kHz · LINK ESTÁVEL
        </div>
      </div>

      {/* corpo */}
      <div className="mask-fade-top flex flex-1 flex-col justify-end gap-[9px] overflow-hidden px-4 pb-3 pt-20">
        {lines.map((l) => (
          <p key={l.id} className="line-in text-[13.5px] leading-snug">
            <span className="mr-2 text-white/25 tabular-nums">
              [{fmtTC(l.at)}]
            </span>
            <span className="text-white/55">{l.text}</span>
          </p>
        ))}

        {current ? (
          <div className="line-in border-l-2 border-accent bg-[rgba(232,87,79,0.08)] py-1.5 pl-3 pr-2">
            <div className="mb-1 flex items-center gap-1.5">
              <span className="text-[8.5px] font-semibold tracking-[0.22em] text-accent">
                AO VIVO
              </span>
            </div>
            <p className="text-[13.5px] leading-snug text-white">
              {current}
              <span className="caret ml-0.5 text-accent">▍</span>
            </p>
          </div>
        ) : (
          <p className="text-[12px] tracking-[0.1em] text-white/25">
            · · · aguardando fala
          </p>
        )}
      </div>

      {/* rodapé técnico */}
      <div className="border-t border-white/10 px-4 py-2.5">
        <div className="flex items-center justify-between text-[10px]">
          <span
            className={`font-semibold tracking-[0.16em] ${
              speaking ? "text-accent" : "text-white/40"
            }`}
          >
            {speaking ? "● CAPTANDO" : playing ? "○ EM ESCUTA" : "‖ PAUSADO"}
          </span>
          <span className="tracking-[0.12em] text-white/45">
            ALT+C OCULTA
          </span>
        </div>
        <div className="mt-1 text-[9.5px] text-white/25 tabular-nums">
          buffer {buffer}ms · latência 240ms · conf {conf}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 03 · MANUSCRITO — a legenda nasce diante dos seus olhos             */
/* ------------------------------------------------------------------ */

export function ManuscriptPanel({ history, current }: PanelProps) {
  const lines = history.slice(-12);

  return (
    <div className="absolute inset-0 bg-[rgba(12,12,15,0.62)] backdrop-blur-[7px]">
      {/* margem de caderno */}
      <div className="absolute bottom-8 left-[27px] top-8 w-px bg-white/[0.07]" />

      <div className="absolute left-7 top-7 flex items-baseline gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-white/28">
          sotto
        </span>
        <span className="text-[10px] italic text-white/20">registro contínuo</span>
      </div>

      <div className="mask-fade-top absolute inset-x-0 bottom-0 top-20 flex flex-col justify-end gap-[15px] overflow-hidden py-8 pl-12 pr-8">
        {lines.map((l) => {
          const fresh = l.fresh;
          const stable = fresh ? l.text.slice(0, l.text.length - fresh.length) : l.text;
          return (
            <p
              key={l.id}
              className="line-in font-body text-[18px] leading-[1.6] font-[450] text-[rgba(235,232,225,0.88)]"
            >
              {stable}
              {fresh && <span className="settle-word">{fresh}</span>}
            </p>
          );
        })}

        {current ? (
          <p className="font-body text-[18px] leading-[1.6] italic text-[rgba(235,232,225,0.52)] underline decoration-white/25 decoration-[1px] underline-offset-[5px]">
            {current}
            <span className="caret not-italic">▍</span>
          </p>
        ) : (
          <p className="font-body text-[16px] italic text-white/28">
            ouvindo<span className="caret">▍</span>
          </p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 04 · CARTÃO DE CINEMA — presença editorial mínima                   */
/* ------------------------------------------------------------------ */

export function CinemaPanel({ history, current }: PanelProps) {
  const lines = history.slice(-6);
  const n = lines.length;

  return (
    <div
      className="absolute inset-0 backdrop-blur-[3px]"
      style={{
        background:
          "linear-gradient(to top, rgba(4,5,8,0.72) 0%, rgba(4,5,8,0.4) 55%, rgba(4,5,8,0.14) 100%)",
      }}
    >
      <div className="mask-fade-top absolute inset-x-0 bottom-0 top-0 flex flex-col justify-end gap-[26px] overflow-hidden px-9 pb-20 pt-32">
        {lines.map((l, i) => (
          <p
            key={l.id}
            className="line-in font-cinema text-[21px] leading-[1.55] font-medium text-[#f1ece2]"
            style={{ opacity: Math.max(0.92 - (n - 1 - i) * 0.13, 0.3) }}
          >
            <span className="mr-2.5 text-white/25">—</span>
            {l.text}
          </p>
        ))}

        {current && (
          <p
            className="border-l border-white/25 pl-4 font-cinema text-[21px] leading-[1.55] font-medium text-[#f1ece2]"
            style={{ opacity: 0.5, filter: "blur(0.45px)" }}
          >
            {current}
          </p>
        )}
      </div>

      <p className="absolute bottom-7 right-9 font-cinema text-[13px] italic text-white/25">
        sotto
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 05 · INSTRUMENTO — está ligado, não é uma janela aberta             */
/* ------------------------------------------------------------------ */

export function InstrumentPanel({
  history,
  current,
  speaking,
  playing,
  elapsed,
}: PanelProps) {
  const lines = history.slice(-8);
  const n = lines.length;
  const status = !playing ? "PAUSADO" : speaking ? "CAPTANDO" : "OUVINDO";

  const bars = [
    { cls: "eq-1", idle: "h-[5px]" },
    { cls: "eq-2", idle: "h-[8px]" },
    { cls: "eq-3", idle: "h-[4px]" },
  ];

  return (
    <div className="absolute inset-0 flex flex-col overflow-hidden rounded-[10px] border border-white/[0.08] bg-[rgba(10,12,15,0.92)] font-instr backdrop-blur-[8px]">
      {/* status */}
      <div className="flex items-center justify-between border-b border-white/[0.07] px-5 pb-3.5 pt-4">
        <div className="flex items-center gap-3">
          <div className="flex h-[18px] items-end gap-[3px]">
            {bars.map((b, i) =>
              speaking ? (
                <span
                  key={i}
                  className={`eq-bar ${b.cls} h-full w-[3px] rounded-sm bg-accent`}
                />
              ) : (
                <span
                  key={i}
                  className={`w-[3px] rounded-sm bg-white/25 ${b.idle}`}
                />
              )
            )}
          </div>
          <span className="text-[11px] font-medium tracking-[0.24em] text-white/70">
            {status}
          </span>
        </div>
        <span className="text-[12px] text-white/40 tabular-nums">
          {fmtTC(elapsed)}
        </span>
      </div>

      {/* corpo */}
      <div className="mask-fade-top flex flex-1 flex-col justify-end gap-[13px] overflow-hidden px-5 pb-6 pt-16">
        {lines.map((l, i) => (
          <p
            key={l.id}
            className="line-in ml-[16px] text-[18px] leading-[1.3] font-medium text-white"
            style={{ opacity: Math.max(0.5 - (n - 1 - i) * 0.06, 0.14) }}
          >
            {l.text}
          </p>
        ))}

        {current && (
          <div className="flex gap-[13px]">
            <span className="indicator-pulse w-[3px] shrink-0 self-stretch rounded-full bg-accent" />
            <p className="text-[23px] leading-[1.22] font-bold text-white">
              {current}
            </p>
          </div>
        )}
      </div>

      {/* operação */}
      <div className="flex items-center justify-between border-t border-white/[0.07] px-5 py-3">
        <div className="flex items-center gap-1.5">
          <span className="keycap">Alt</span>
          <span className="text-[10px] text-white/30">+</span>
          <span className="keycap">C</span>
          <span className="ml-2 text-[11px] text-white/40">ocultar painel</span>
        </div>
        <span className="text-[10px] tracking-[0.14em] text-white/30">
          PT-BR · 48 kHz
        </span>
      </div>
    </div>
  );
}
