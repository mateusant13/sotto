import type { CSSProperties } from "react";
import type { DesignId } from "../data/designs";
import { fmtTC, type ClosedLine, type LineStatus } from "../hooks/useTranscription";

interface Props {
  design: DesignId;
  forming: string[];
  status: LineStatus;
  elapsed: number;
  lastClosed?: ClosedLine;
}

export function Caption({ design, forming, status, elapsed, lastClosed }: Props) {
  const empty = forming.length === 0;
  const conf = lastClosed?.conf ?? 0.93;

  if (design === "tele") {
    return (
      <div className="max-w-[760px]">
        {empty ? (
          <p className="font-tele text-[clamp(20px,3vw,34px)] font-semibold tracking-[0.4em] text-paper/30">· · ·</p>
        ) : (
          <p className="glow-live text-left font-tele text-[clamp(30px,4.6vw,54px)] font-bold uppercase leading-[1.06] text-paper">
            {forming.map((w, i) => (
              <span key={i} className={"w-tele " + (i === forming.length - 1 && status === "forming" ? "text-white" : "text-paper/82")}>
                {w}{" "}
              </span>
            ))}
          </p>
        )}
      </div>
    );
  }

  if (design === "bcast") {
    return (
      <div className="w-full max-w-[700px]">
        <div className="mb-2 flex items-center gap-4 font-bcast text-[10px] tracking-[0.28em]">
          <span className="flex items-center gap-1.5 text-signal">
            <span className={"inline-block h-1.5 w-1.5 rounded-full bg-signal " + (status === "forming" ? "rec-dot" : "")} />
            AO VIVO
          </span>
          <span className="text-white/45">TC {fmtTC(elapsed)}</span>
        </div>
        <p className="text-left font-bcast text-[clamp(18px,2.3vw,28px)] font-medium leading-[1.4] text-white/90">
          {empty ? (
            <span className="text-white/35">
              <span className="caret text-signal">▍</span> captando áudio…
            </span>
          ) : (
            forming.map((w, i) => (
              <span key={i} className={"w-bcast " + (i === forming.length - 1 && status === "forming" ? "text-amberlite" : "")}>
                {w}{" "}
              </span>
            ))
          )}
          {!empty && status === "forming" && <span className="caret text-signal">▍</span>}
        </p>
        <div className="mt-2.5 flex gap-5 font-bcast text-[9.5px] tracking-[0.2em] text-white/40">
          <span>PT-BR</span>
          <span>CONF {conf.toFixed(2)}</span>
          <span className={status === "closing" ? "text-amberlite" : ""}>{status === "closing" ? "FECHANDO FRASE" : "FORMANDO"}</span>
        </div>
      </div>
    );
  }

  if (design === "mano") {
    return (
      <div className="max-w-[720px]">
        <p className="text-left font-mano text-[clamp(21px,2.7vw,33px)] leading-[1.55] text-bone">
          {empty ? (
            <span className="inline-block border-b border-bone/25 pb-1 pr-8">
              <span className="caret inline-block h-[0.9em] w-[2px] translate-y-[0.1em] bg-bone/70" />
            </span>
          ) : (
            <span className="inline-block border-b border-bone/35 pb-1">
              {forming.map((w, i) => (
                <span
                  key={i}
                  className="w-mano"
                  style={{ "--ink-op": 0.45 + 0.55 * ((i + 1) / forming.length) } as CSSProperties}
                >
                  {w}{" "}
                </span>
              ))}
              {status === "forming" && (
                <span className="caret ml-px inline-block h-[0.88em] w-[2px] translate-y-[0.1em] bg-bone/80" />
              )}
            </span>
          )}
        </p>
      </div>
    );
  }

  if (design === "cine") {
    return (
      <div className="max-w-[780px] text-center">
        {lastClosed && !empty && (
          <p className="line-in mb-3 font-cine text-[clamp(13px,1.3vw,16px)] italic leading-relaxed text-white/65">
            {lastClosed.text}
          </p>
        )}
        {empty ? (
          <p className="font-cine text-[20px] tracking-[0.5em] text-gold/35">· ·</p>
        ) : (
          <p
            className={
              "font-cine text-[clamp(24px,3vw,42px)] font-light leading-[1.42] text-bone transition-all duration-700 " +
              (status === "forming" ? "tracking-[0.018em] opacity-50" : "opacity-100")
            }
          >
            {forming.map((w, i) => (
              <span key={i} className="w-cine">
                {w}{" "}
              </span>
            ))}
          </p>
        )}
      </div>
    );
  }

  // inst
  return (
    <div className="flex max-w-[720px] items-stretch gap-4">
      <span className={"w-[4px] shrink-0 rounded-full bg-led " + (status === "forming" || !empty ? "led-breathe" : "opacity-30")} />
      <div className="min-h-[2.4em]">
        {empty ? (
          <p className="font-inst text-[13px] font-medium tracking-[0.3em] text-white/30">OUVINDO…</p>
        ) : (
          <p className="text-left font-inst text-[clamp(24px,3.1vw,42px)] font-bold leading-[1.14] text-white">
            {forming.map((w, i) => (
              <span key={i} className="w-inst">
                {w}{" "}
              </span>
            ))}
          </p>
        )}
      </div>
    </div>
  );
}
