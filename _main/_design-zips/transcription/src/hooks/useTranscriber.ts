import { useCallback, useEffect, useRef, useState } from "react";
import type { Scenario } from "../lib/scripts";

export interface Line {
  id: number;
  text: string;
  /** trecho que mudou na última correção — usado pelo Manuscrito para "assentar" o texto */
  fresh: string | null;
  at: number; // timecode em segundos no momento da consolidação
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function commonPrefixLen(a: string, b: string): number {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return i;
}

export function useTranscriber(scenario: Scenario) {
  const [history, setHistory] = useState<Line[]>([]);
  const [current, setCurrent] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [gen, setGen] = useState(0);

  const playingRef = useRef(true);
  const speedRef = useRef(1);
  const elapsedRef = useRef(0);
  const idRef = useRef(1);

  useEffect(() => {
    playingRef.current = playing;
  }, [playing]);

  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  // reinicia ao trocar de cenário
  useEffect(() => {
    setHistory([]);
    setCurrent("");
    setElapsed(0);
    elapsedRef.current = 0;
    idRef.current = 1;
    setGen((g) => g + 1);
  }, [scenario]);

  // relógio de sessão
  useEffect(() => {
    const iv = setInterval(() => {
      if (playingRef.current) {
        elapsedRef.current += 1;
        setElapsed(elapsedRef.current);
      }
    }, 1000);
    return () => clearInterval(iv);
  }, []);

  // loop de transcrição
  useEffect(() => {
    let cancelled = false;

    const waitIfPaused = async () => {
      while (!playingRef.current && !cancelled) await sleep(150);
    };

    (async () => {
      await sleep(700); // lead-in: o painel "liga" antes da primeira fala
      while (!cancelled) {
        for (const utt of scenario.utterances) {
          if (cancelled) return;
          await waitIfPaused();
          if (cancelled) return;

          let prev = "";
          for (const partial of utt) {
            await waitIfPaused();
            if (cancelled) return;
            setCurrent(partial);
            prev = partial;
            const words = partial.split(/\s+/).length;
            await sleep(
              (230 + words * 55 + Math.random() * 220) / speedRef.current
            );
          }

          await waitIfPaused();
          if (cancelled) return;

          const finalText = utt[utt.length - 1];
          const cut = commonPrefixLen(prev, finalText);
          const fresh = finalText.slice(cut);

          setCurrent("");
          setHistory((h) => [
            ...h.slice(-13),
            {
              id: idRef.current++,
              text: finalText,
              fresh: fresh.length > 0 ? fresh : null,
              at: elapsedRef.current,
            },
          ]);
          await sleep(760 / speedRef.current);
        }
        await sleep(1500 / speedRef.current);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [gen, scenario]);

  const toggle = useCallback(() => setPlaying((p) => !p), []);
  const cycleSpeed = useCallback(
    () => setSpeed((s) => (s === 1 ? 1.5 : s === 1.5 ? 0.6 : 1)),
    []
  );

  return {
    history,
    current,
    playing,
    toggle,
    speed,
    cycleSpeed,
    elapsed,
    speaking: current.length > 0,
  };
}
