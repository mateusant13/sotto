import type { ClosedLine } from "../hooks/useTranscription";

const FALLBACK = [
  "o som chega antes da imagem",
  "a legenda nasce enquanto a frase está em formação",
  "o painel escuta tudo, mas não interrompe nada",
  "o que era hipótese, vira registro",
];

export function Ticker({ history }: { history: ClosedLine[] }) {
  const row = (history.length ? history.map((h) => h.text.toLowerCase()) : FALLBACK).slice(-10);

  return (
    <div className="ticker relative overflow-hidden border-y border-white/8 bg-ink2 py-3.5">
      <span className="absolute inset-y-0 left-0 z-10 flex items-center bg-gradient-to-r from-ink2 via-ink2/95 to-transparent pl-5 pr-8 font-bcast text-[9px] tracking-[0.3em] text-ember">
        JÁ DITO
      </span>
      <div className="ticker-track flex items-center">
        {[0, 1].map((k) => (
          <div key={k} className="flex shrink-0 items-center">
            {row.map((t, i) => (
              <span key={i} className="flex items-center whitespace-nowrap">
                <span className="font-mano text-[14.5px] italic text-bone/55">{t}</span>
                <span className="mx-8 font-bcast text-[10px] text-ember/70">·</span>
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
