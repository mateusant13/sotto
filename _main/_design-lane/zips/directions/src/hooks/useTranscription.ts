import { useEffect, useRef, useState } from "react";
import { SCRIPT } from "../data/designs";

export interface ClosedLine {
  id: number;
  text: string;
  at: string;
  conf: number;
}

export type LineStatus = "forming" | "closing";

const pad = (n: number) => String(n).padStart(2, "0");

export function fmtClock(s: number) {
  return `${pad(Math.floor(s / 60))}:${pad(Math.floor(s % 60))}`;
}

export function fmtTC(s: number) {
  const f = Math.floor((s % 1) * 25);
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s / 60) % 60))}:${pad(Math.floor(s % 60))}:${pad(f)}`;
}

let uid = 1;

/**
 * Motor de transcrição simulada: palavras surgem uma a uma (fala em
 * formação) e, ao fim da frase, a linha "fecha" e entra no histórico.
 */
export function useTranscription(playing: boolean, speed: number) {
  const [history, setHistory] = useState<ClosedLine[]>([]);
  const [forming, setForming] = useState<string[]>([]);
  const [status, setStatus] = useState<LineStatus>("forming");
  const [tick, setTick] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  const lineRef = useRef(0);
  const wordRef = useRef(0);
  const elapsedRef = useRef(0);

  // relógio contínuo (timecode)
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const step = (t: number) => {
      elapsedRef.current += (t - last) / 1000;
      last = t;
      setElapsed(elapsedRef.current);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  // agendador de palavras / fechamento de frase
  useEffect(() => {
    if (!playing) return;
    const line = SCRIPT[lineRef.current % SCRIPT.length];
    let t: number;

    if (wordRef.current < line.length) {
      const delay = (235 + Math.random() * 175) / speed;
      t = window.setTimeout(() => {
        wordRef.current += 1;
        setForming(line.slice(0, wordRef.current));
        setTick((x) => x + 1);
        setStatus("forming");
      }, delay);
    } else {
      setStatus("closing");
      t = window.setTimeout(() => {
        setHistory((h) => [
          ...h.slice(-36),
          {
            id: uid++,
            text: line.join(" "),
            at: fmtClock(elapsedRef.current),
            conf: 0.88 + Math.random() * 0.11,
          },
        ]);
        lineRef.current += 1;
        wordRef.current = 0;
        setForming([]);
        setStatus("forming");
      }, 780 / speed);
    }
    return () => window.clearTimeout(t);
  }, [playing, speed, forming]);

  return { history, forming, status, tick, elapsed };
}
