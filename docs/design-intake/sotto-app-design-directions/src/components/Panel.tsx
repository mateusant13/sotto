import { useEffect, useRef, type CSSProperties } from "react";
import type { DesignId } from "../data/designs";
import { fmtTC, type ClosedLine, type LineStatus } from "../hooks/useTranscription";
import { LevelMeter } from "./bits";

interface Props {
  design: DesignId;
  history: ClosedLine[];
  forming: string[];
  status: LineStatus;
  tick: number;
  elapsed: number;
  playing: boolean;
}

const pad3 = (n: number) => String(n).padStart(3, "0");

export function Panel({ design, history, forming, status, tick, elapsed, playing }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history.length, forming.length, status]);

  const recent = history.slice(-14);
  const lastConf = history.length ? history[history.length - 1].conf : 0.93;

  const frame =
    "h-full flex flex-col overflow-hidden rounded-lg border shadow-[0_28px_90px_rgba(0,0,0,0.6)] backdrop-blur-md";

  const formingWords = (wordClass: string, wordStyle?: (i: number, len: number) => CSSProperties) =>
    forming.map((w, i) => (
      <span key={`${tick - forming.length + i}-${i}`} className={wordClass} style={wordStyle?.(i, forming.length)}>
        {w}{" "}
      </span>
    ));

  return (
    <div
      className={
        frame +
        " " +
        (design === "tele"
          ? "bg-[#0b0c0f]/55 border-white/10"
          : design === "bcast"
            ? "bg-[#090d10]/70 border-white/12"
            : design === "mano"
              ? "bg-paper/[0.06] border-white/14"
              : design === "cine"
                ? "bg-[#0d0c09]/60 border-gold/15"
                : "bg-[#090f0d]/65 border-led/15")
      }
    >
      {/* ---------- cabeçalho ---------- */}
      {design === "tele" && (
        <header className="flex items-center justify-between border-b border-white/8 px-4 py-3">
          <span className="font-tele text-[12px] font-semibold tracking-[0.42em] text-paper/60">SOTTO</span>
          <span className="flex items-center gap-1.5 font-tele text-[10px] tracking-[0.28em] text-paper/35">
            <span className={"inline-block h-1.5 w-1.5 rounded-full " + (playing ? "bg-paper/80" : "bg-paper/25")} />
            {playing ? "LENDO" : "PAUSA"}
          </span>
        </header>
      )}
      {design === "bcast" && (
        <header className="flex items-center gap-2.5 border-b border-white/10 px-3.5 py-2.5 font-bcast text-[9.5px] tracking-[0.18em]">
          <span className={"h-2 w-2 rounded-full bg-signal " + (playing ? "rec-dot" : "opacity-40")} />
          <span className="font-semibold text-signal">{playing ? "REC" : "STBY"}</span>
          <span className="ml-auto text-white/55">{fmtTC(elapsed)}</span>
          <span className="text-white/30">CH·01</span>
        </header>
      )}
      {design === "mano" && (
        <header className="flex items-baseline justify-between border-b border-white/10 px-4 py-3">
          <span className="font-mano text-[12.5px] italic text-bone/55">rascunho ao vivo</span>
          <span className="font-mano text-[11px] text-bone/35">pág. 1</span>
        </header>
      )}
      {design === "cine" && (
        <header className="flex items-baseline justify-between border-b border-gold/12 px-4 py-3">
          <span className="font-cine text-[11px] font-medium tracking-[0.34em] text-gold/75">SOTTO</span>
          <span className="font-cine text-[11px] italic text-bone/40">· ao vivo ·</span>
        </header>
      )}
      {design === "inst" && (
        <header className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
          <span className={"h-2 w-2 rounded-[2px] bg-led " + (playing ? "led-breathe" : "opacity-30")} />
          <span className="font-inst text-[11px] font-bold tracking-[0.3em] text-white/85">ON</span>
          <span className="ml-auto font-inst text-[9px] tracking-[0.22em] text-white/35">ALT+C</span>
        </header>
      )}

      {/* ---------- histórico ---------- */}
      <div ref={scrollRef} className="panel-scroll flex-1 overflow-y-auto px-4 py-3.5">
        {recent.length === 0 && forming.length === 0 && (
          <p className="font-bcast text-[10px] tracking-[0.2em] text-white/30">AGUARDANDO ÁUDIO…</p>
        )}

        {design === "tele" && (
          <div className="space-y-2.5">
            {recent.map((h, i) => (
              <p
                key={h.id}
                className={
                  "line-in font-tele text-[16.5px] font-semibold leading-[1.22] " +
                  (i === recent.length - 1 ? "text-white/50" : "text-white/25")
                }
              >
                {h.text}
              </p>
            ))}
            {forming.length > 0 && (
              <p className="glow-live pt-1 font-tele text-[18.5px] font-bold leading-[1.2] text-paper">
                {formingWords("w-tele")}
              </p>
            )}
          </div>
        )}

        {design === "bcast" && (
          <div className="space-y-2">
            {recent.map((h) => (
              <div key={h.id} className="line-in grid grid-cols-[24px_38px_1fr] gap-2 font-bcast text-[10.5px] leading-[1.55]">
                <span className="text-white/25">{pad3(h.id)}</span>
                <span className="text-white/40">{h.at}</span>
                <span className="text-white/60">{h.text}</span>
              </div>
            ))}
            {forming.length > 0 && (
              <div className="grid grid-cols-[24px_38px_1fr] gap-2 font-bcast text-[10.5px] leading-[1.55]">
                <span className="text-amberlite/60">{pad3(history.length + 1)}</span>
                <span className="text-amberlite/70">{fmtTC(elapsed).slice(3, 8)}</span>
                <span>
                  {forming.map((w, i) => (
                    <span key={i} className={"w-bcast " + (i === forming.length - 1 && status === "forming" ? "text-amberlite" : "text-white/85")}>
                      {w}{" "}
                    </span>
                  ))}
                  {status === "forming" && <span className="caret text-signal">▍</span>}
                </span>
              </div>
            )}
          </div>
        )}

        {design === "mano" && (
          <div>
            {recent.map((h) => (
              <p key={h.id} className="line-in mb-3 font-mano text-[14px] leading-[1.8] text-bone/80">
                {h.text}
              </p>
            ))}
            {forming.length > 0 && (
              <p className="border-b border-bone/30 pb-1 font-mano text-[14.5px] leading-[1.8] text-bone">
                {formingWords("w-mano", (i, len) => ({ "--ink-op": 0.45 + 0.55 * ((i + 1) / len) }) as CSSProperties)}
                <span className="caret ml-px inline-block h-[0.92em] w-[2px] translate-y-[0.12em] bg-bone/85" />
              </p>
            )}
          </div>
        )}

        {design === "cine" && (
          <div>
            {recent.map((h, i) => (
              <p
                key={h.id}
                className={
                  "line-in mb-3.5 font-cine text-[15px] font-light leading-[1.9] " +
                  (i === recent.length - 1 ? "text-white/70" : "text-white/38")
                }
              >
                {h.text}
              </p>
            ))}
            {forming.length > 0 && (
              <p className="border-l border-gold/50 pl-3 font-cine text-[15px] font-light italic leading-[1.9] text-white/45">
                {formingWords("w-cine")}
              </p>
            )}
          </div>
        )}

        {design === "inst" && (
          <div>
            {recent.map((h, i) => (
              <div key={h.id} className="line-in mb-2.5 flex items-start gap-2.5">
                <span className="mt-[7px] h-[5px] w-[5px] shrink-0 border border-white/25" />
                <p className={"font-inst text-[13.5px] font-medium leading-[1.45] " + (i === recent.length - 1 ? "text-white/90" : "text-white/60")}>
                  {h.text}
                </p>
              </div>
            ))}
            {forming.length > 0 && (
              <div className="flex items-stretch gap-2.5">
                <span className={"w-[3px] shrink-0 rounded-full bg-led " + (playing ? "led-breathe" : "opacity-40")} />
                <p className="font-inst text-[14.5px] font-bold leading-[1.4] text-white">{formingWords("w-inst")}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ---------- rodapé ---------- */}
      {design === "tele" && (
        <footer className="flex items-center justify-between border-t border-white/8 px-4 py-2.5 font-tele text-[10px] tracking-[0.3em] text-white/30">
          <span>HISTÓRICO</span>
          <span className="text-paper/50">▲ EM CURSO</span>
        </footer>
      )}
      {design === "bcast" && (
        <footer className="flex items-center gap-2 border-t border-white/10 px-3.5 py-2.5 font-bcast text-[9px] tracking-[0.14em] text-white/40">
          <span>PT-BR</span>
          <span className="text-white/20">·</span>
          <span>48K</span>
          <LevelMeter tick={tick} playing={playing} />
          <span className="ml-auto text-amberlite">CONF {lastConf.toFixed(2)}</span>
        </footer>
      )}
      {design === "mano" && (
        <footer className="border-t border-white/10 px-4 py-2.5">
          <span className="font-mano text-[11px] italic text-bone/40">— escrito ao ouvido</span>
        </footer>
      )}
      {design === "cine" && (
        <footer className="border-t border-gold/10 px-4 py-2 text-center">
          <span className="font-cine text-[12px] tracking-[0.5em] text-gold/40">· · ·</span>
        </footer>
      )}
      {design === "inst" && (
        <footer className="flex items-center gap-2.5 border-t border-white/10 px-4 py-2.5 font-inst text-[9px] tracking-[0.22em] text-white/45">
          <LevelMeter tick={tick} playing={playing} color="rgba(95,211,167,0.9)" />
          <span>{playing ? "OUVINDO" : "PAUSA"}</span>
          <span className="ml-auto text-white/30">380×900</span>
        </footer>
      )}
    </div>
  );
}
