import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TranscriptLine } from "../data";

export type PlayerPhase = "typing" | "hold" | "ended";

interface PlayerOpts {
  playing: boolean;
  speed: number;
  /** words = reveal word by word, chars = reveal character by character */
  mode: "words" | "chars";
  reduced: boolean;
  onCommit: (lineIdx: number) => void;
  /** called when the whole transcript finished and is about to loop */
  onCycle: () => void;
}

/**
 * Simulates a live transcription engine: the current line is "spoken"
 * word (or character) by word, held for a breath, then committed to the
 * history panel before the next line begins. Loops gently at the end.
 */
export function useTranscriptPlayer(lines: TranscriptLine[], opts: PlayerOpts) {
  const { playing, speed, mode, reduced } = opts;

  const [lineIdx, setLineIdx] = useState(0);
  const [pos, setPos] = useState(0);
  const [phase, setPhase] = useState<PlayerPhase>("typing");

  const commitRef = useRef(opts.onCommit);
  const cycleRef = useRef(opts.onCycle);
  commitRef.current = opts.onCommit;
  cycleRef.current = opts.onCycle;

  // reset whenever the transcript or the reveal mode changes
  useEffect(() => {
    setLineIdx(0);
    setPos(0);
    setPhase("typing");
  }, [lines, mode]);

  const line = lines[Math.min(lineIdx, lines.length - 1)];
  const words = useMemo(() => line.text.split(" "), [line.text]);
  const total = mode === "words" ? words.length : line.text.length;

  // typing tick
  useEffect(() => {
    if (phase !== "typing" || !playing) return;

    if (reduced) {
      setPos(total);
      setPhase("hold");
      return;
    }

    const step = mode === "words" ? 1 : 2;
    const next = Math.min(total, pos + step);
    // a touch of human unevenness on word reveals
    const base = mode === "words" ? 150 : 32;
    const jitter = mode === "words" && (pos + lineIdx) % 4 === 2 ? 110 : 0;
    const delay = (base + jitter) / speed;

    const t = window.setTimeout(() => {
      setPos(next);
      if (next >= total) setPhase("hold");
    }, delay);
    return () => window.clearTimeout(t);
  }, [phase, playing, pos, total, mode, speed, reduced, lineIdx]);

  // small breath at the end of a line, then commit it to history
  const holdMs = reduced ? 1500 : 950;
  useEffect(() => {
    if (phase !== "hold" || !playing) return;
    const t = window.setTimeout(() => {
      commitRef.current(lineIdx);
      if (lineIdx + 1 >= lines.length) {
        setPhase("ended");
      } else {
        setLineIdx((i) => i + 1);
        setPos(0);
        setPhase("typing");
      }
    }, holdMs / speed);
    return () => window.clearTimeout(t);
  }, [phase, playing, lineIdx, lines.length, speed, holdMs]);

  const restart = useCallback(() => {
    setLineIdx(0);
    setPos(0);
    setPhase("typing");
  }, []);

  // finished — wait a moment, then loop back around
  useEffect(() => {
    if (phase !== "ended" || !playing) return;
    const t = window.setTimeout(() => {
      cycleRef.current();
      restart();
    }, reduced ? 2400 : 3400 / speed);
    return () => window.clearTimeout(t);
  }, [phase, playing, restart, reduced, speed]);

  return { line, words, lineIdx, pos, total, phase, restart };
}
