import { useCallback, useEffect, useRef, useState } from "react";
import type { Scene } from "@/data/scenes";

export interface Segment {
  id: number;
  speaker: string;
  text: string;
  /** simulated session offset, in ms, at the moment the segment was finalised */
  at: number;
}

export interface LiveLine {
  speaker: string;
  words: string[];
}

interface EngineRef {
  line: number;
  word: number;
  timer: number;
  paused: boolean;
  pending: boolean;
  nextId: number;
  elapsed: number;
  running: boolean;
}

const SPEECHY = /[.,?!…]["')\]]?$/;
const SOFT = /[,;:—–]["')\]]?$/;

/**
 * A gentle transcript simulator. Words arrive one at a time at roughly the
 * pace of slow, late-night speech, then the line settles into the history.
 */
export function useTranscription(scene: Scene) {
  const [segments, setSegments] = useState<Segment[]>([]);
  const [live, setLive] = useState<LiveLine | null>(null);
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const ref = useRef<EngineRef>({
    line: 0,
    word: 0,
    timer: 0,
    paused: false,
    pending: true,
    nextId: 0,
    elapsed: 0,
    running: false,
  });

  const sceneRef = useRef(scene);
  sceneRef.current = scene;

  const startLine = useCallback(() => {
    const r = ref.current;
    const lines = sceneRef.current.script;
    const line = lines[r.line % lines.length];
    r.pending = false;
    r.word = 0;
    setLive({ speaker: line.speaker, words: [] });
  }, []);

  useEffect(() => {
    const r = ref.current;

    const schedule = (ms: number) => {
      r.timer = window.setTimeout(step, ms);
    };

    const delayFor = (word: string, next?: string) => {
      let d = 185 + Math.random() * 155;
      if (SPEECHY.test(word)) d += 330;
      else if (SOFT.test(word)) d += 170;
      if (word.length > 9) d += 70;
      if (next && /^[A-Z"“(]/.test(next)) d += 40;
      return d;
    };

    const step = () => {
      if (!r.running) return;
      if (r.paused) {
        schedule(420);
        return;
      }
      const lines = sceneRef.current.script;

      if (r.pending) {
        r.elapsed += 700 + Math.random() * 500;
        startLine();
        schedule(160 + Math.random() * 140);
        return;
      }

      const line = lines[r.line % lines.length];
      const words = line.text.split(/\s+/);

      if (r.word >= words.length) {
        r.elapsed += 320;
        const done = {
          id: r.nextId++,
          speaker: line.speaker,
          text: line.text,
          at: r.elapsed,
        };
        setSegments((prev) => [...prev, done]);
        setLive(null);
        r.line += 1;
        r.pending = true;
        const next = lines[(r.line + 1) % lines.length];
        schedule(next.speaker === line.speaker ? 640 : 1000);
        return;
      }

      const word = words[r.word];
      r.word += 1;
      setLive((prev) =>
        prev && prev.speaker === line.speaker
          ? { speaker: line.speaker, words: [...prev.words, word] }
          : { speaker: line.speaker, words: [word] },
      );
      const delay = delayFor(word, words[r.word]);
      r.elapsed += delay;
      schedule(delay);
    };

    // session start
    r.line = 0;
    r.word = 0;
    r.pending = true;
    r.nextId = 0;
    r.elapsed = 0;
    r.paused = false;
    r.running = true;
    setSegments([]);
    setLive(null);
    setPaused(false);
    setElapsed(0);
    schedule(1150);

    const clock = window.setInterval(() => {
      if (!r.paused && r.running) setElapsed(r.elapsed);
    }, 480);

    return () => {
      r.running = false;
      window.clearTimeout(r.timer);
      window.clearInterval(clock);
    };
  }, [scene, startLine]);

  const togglePause = useCallback(() => {
    const r = ref.current;
    r.paused = !r.paused;
    setPaused(r.paused);
  }, []);

  const clearSession = useCallback(() => {
    const r = ref.current;
    r.line = 0;
    r.word = 0;
    r.pending = true;
    r.nextId = 0;
    r.elapsed = 0;
    setSegments([]);
    setLive(null);
    setElapsed(0);
  }, []);

  const last = segments.length ? segments[segments.length - 1] : null;

  return { segments, live, paused, elapsed, last, togglePause, clearSession };
}

/** Soft, never-jumpy input level, used by meters in the side panel. */
export function useLevel(bars: number, active: boolean) {
  const [levels, setLevels] = useState<number[]>(() => Array.from({ length: bars }, () => 0.3));

  useEffect(() => {
    const id = window.setInterval(() => {
      setLevels((prev) =>
        prev.map((v) => {
          const target = active ? 0.18 + Math.random() * 0.82 : 0.1 + Math.random() * 0.12;
          return v + (target - v) * 0.55;
        }),
      );
    }, 170);
    return () => window.clearInterval(id);
  }, [active]);

  return levels;
}
