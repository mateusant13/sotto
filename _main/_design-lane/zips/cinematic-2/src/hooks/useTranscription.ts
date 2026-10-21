import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { INTERJECTIONS, SCRIPTS, SEED_ENTRIES, type Script } from "../lib/scripts";

export interface Entry {
  id: string;
  speaker: string;
  text: string;
  session: string;
  at: number;
  confidence: number;
  duration: number;
  marker: number;
}

export interface Partial {
  speaker: string;
  words: string[];
  revealed: number;
  lineKey: number;
  live: boolean;
}

const rid = () => Math.random().toString(36).slice(2, 9);
const rand = (a: number, b: number) => a + Math.random() * (b - a);

const sessionStamp = (d: Date) => {
  const h = d.getHours();
  const m = d.getMinutes().toString().padStart(2, "0");
  const ap = h < 12 ? "AM" : "PM";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh}:${m} ${ap}`;
};

const seededHistory = (): Entry[] => {
  const sessionTimes: Record<string, number> = {
    "Late morning": 4 * 3600e3,
    "This afternoon": 2.1 * 3600e3,
    "Earlier tonight": 42 * 60e3,
  };
  return SEED_ENTRIES.map((s, i) => ({
    id: `seed-${i}`,
    speaker: s.speaker,
    text: s.text,
    session: s.session,
    at: Date.now() - (sessionTimes[s.session] ?? 3600e3) + s.offset * 1000,
    confidence: s.confidence,
    duration: s.duration,
    marker: 0,
  }));
};

export function useTranscription() {
  const [entries, setEntries] = useState<Entry[]>(() => seededHistory());
  const [partial, setPartial] = useState<Partial | null>(null);
  const [running, setRunning] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [level, setLevel] = useState(0.18);
  const [elapsed, setElapsed] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);

  const sessionLabel = useMemo(() => `Tonight · ${sessionStamp(new Date())}`, []);

  const engine = useRef({
    scriptIdx: 0,
    lineIdx: 0,
    wordIdx: 0,
    phase: "gap" as "gap" | "speaking",
    nextAt: performance.now() + 900,
    lineStart: 0,
    lineKey: 0,
    wordCount: 0,
    curSpeaker: "",
    curWords: [] as string[],
  });
  const [scriptMeta, setScriptMeta] = useState<Script>(SCRIPTS[0]);

  const runningRef = useRef(running);
  runningRef.current = running;
  const speedRef = useRef(speed);
  speedRef.current = speed;

  const pushEntry = useCallback(
    (speaker: string, text: string, at: number, duration: number, words: number) => {
      const confidence = Math.min(0.995, 0.86 + Math.min(words, 14) * 0.008 + Math.random() * 0.05);
      setEntries((prev) => [
        ...prev,
        { id: rid(), speaker, text, session: sessionLabel, at, confidence, duration, marker: words },
      ]);
    },
    [sessionLabel],
  );

  /* ---------------- caption engine ---------------- */
  useEffect(() => {
    const tick = window.setInterval(() => {
      const e = engine.current;
      if (!runningRef.current) return;
      const now = performance.now() * 1;
      if (now < e.nextAt) return;

      const script = SCRIPTS[e.scriptIdx];
      const spd = speedRef.current;

      if (e.phase === "speaking") {
        e.wordIdx += 1;
        const words = e.curWords;
        if (e.wordIdx >= words.length) {
          const duration = (now - e.lineStart) / 1000;
          pushEntry(e.curSpeaker, words.join(" "), Date.now(), duration, words.length);
          e.wordCount += words.length;
          setPartial(null);
          e.lineIdx += 1;
          if (e.lineIdx >= script.lines.length) {
            e.lineIdx = 0;
            e.scriptIdx = (e.scriptIdx + 1) % SCRIPTS.length;
            setScriptMeta(SCRIPTS[e.scriptIdx]);
          }
          e.phase = "gap";
          e.nextAt = now + rand(620, 1750) / spd;
        } else {
          const last = words[e.wordIdx - 1];
          const punct = /[,;:!?]$/.test(last) ? 190 : /\.$/.test(last) ? 260 : 0;
          const long = last.length > 8 ? 55 : 0;
          e.nextAt = now + (rand(115, 205) + punct + long) / spd;
          setPartial({
            speaker: e.curSpeaker,
            words,
            revealed: e.wordIdx,
            lineKey: e.lineKey,
            live: true,
          });
        }
        return;
      }

      /* phase === "gap" -> start the next line (or a small interjection) */
      const script2 = SCRIPTS[e.scriptIdx];
      const interject = Math.random() < 0.14;
      const next = interject
        ? INTERJECTIONS[Math.floor(Math.random() * INTERJECTIONS.length)]
        : script2.lines[Math.min(e.lineIdx, script2.lines.length - 1)];

      e.curSpeaker = next.speaker;
      e.curWords = next.text.split(" ");
      e.lineStart = now;
      e.wordIdx = 0;
      e.lineKey += 1;
      e.phase = "speaking";
      e.nextAt = now + rand(200, 420) / spd;
      setPartial({ speaker: next.speaker, words: e.curWords, revealed: 0, lineKey: e.lineKey, live: true });
    }, 55);
    return () => window.clearInterval(tick);
  }, [pushEntry]);

  /* ---------------- input level meter ---------------- */
  useEffect(() => {
    let lvl = 0.18;
    const iv = window.setInterval(() => {
      const speaking = engine.current.phase === "speaking" && runningRef.current;
      const target = speaking ? rand(0.4, 0.94) : rand(0.03, 0.16);
      lvl += (target - lvl) * (speaking ? 0.42 : 0.22);
      setLevel(Math.max(0.02, Math.min(1, lvl)));
    }, 90);
    return () => window.clearInterval(iv);
  }, []);

  /* ---------------- session clock ---------------- */
  useEffect(() => {
    const iv = window.setInterval(() => {
      if (runningRef.current) setElapsed((v) => v + 1);
    }, 1000);
    return () => window.clearInterval(iv);
  }, []);

  const stats = useMemo(() => {
    const words = entries.reduce((sum, e) => sum + (e.marker || e.text.split(" ").length), 0);
    const mins = Math.max(1, elapsed / 60);
    const speakers = new Set(entries.map((e) => e.speaker));
    const avgConf = entries.length
      ? entries.slice(-30).reduce((s, e) => s + e.confidence, 0) / Math.min(30, entries.length)
      : 0;
    return {
      entries: entries.length,
      words,
      wpm: Math.round(words / Math.max(1, entries.length ? 3 + mins : mins)),
      speakers: [...speakers],
      avgConf,
      minutes: Math.floor(elapsed / 60),
      seconds: elapsed % 60,
    };
  }, [entries, elapsed]);

  const actions = {
    toggle: () => setRunning((v) => !v),
    setSpeed: (n: number) => setSpeed(n),
    clearHistory: () => setEntries([]),
    restoreSeed: () => setEntries(seededHistory()),
    setAutoScroll,
  };

  return { entries, partial, running, speed, level, elapsed, sessionLabel, stats, scriptMeta, autoScroll, actions };
}

export type Transcription = ReturnType<typeof useTranscription>;

export const fmtClock = (t: number, use24: boolean) => {
  const d = new Date(t);
  const s = d.getSeconds().toString().padStart(2, "0");
  if (use24) {
    return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${s}`;
  }
  const h = d.getHours();
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh}:${d.getMinutes().toString().padStart(2, "0")}:${s} ${h < 12 ? "am" : "pm"}`;
};

export const fmtDuration = (secs: number) => {
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
};
