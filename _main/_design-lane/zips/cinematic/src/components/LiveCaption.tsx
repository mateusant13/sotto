import { cn } from "../utils/cn";
import type { CaptionStyle } from "../themes";
import type { PlayerPhase } from "../hooks/useTranscriptPlayer";
import type { CommittedLine, TranscriptLine } from "../data";

interface LiveCaptionProps {
  line: TranscriptLine;
  words: string[];
  pos: number;
  phase: PlayerPhase;
  caption: CaptionStyle;
  textShadow: string;
  prevLine: CommittedLine | null;
  panelOpen: boolean;
  playing: boolean;
  speed: number;
  onTogglePlay: () => void;
  onRestart: () => void;
  onCycleSpeed: () => void;
}

const controlBtn =
  "grid h-9 w-9 place-items-center rounded-full border border-white/15 bg-black/25 text-[#f2f4f8] backdrop-blur-sm transition-all duration-200 hover:border-white/40 hover:bg-black/40 active:scale-90";

function PlayGlyph() {
  return (
    <svg width="11" height="12" viewBox="0 0 11 12" fill="none" aria-hidden="true">
      <path d="M1.5 1.4v9.2c0 .6.66.97 1.17.66l7.4-4.6a.78.78 0 0 0 0-1.32L2.67.74A.78.78 0 0 0 1.5 1.4Z" fill="currentColor" />
    </svg>
  );
}

function PauseGlyph() {
  return (
    <svg width="10" height="12" viewBox="0 0 10 12" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="2.8" height="10" rx="1" fill="currentColor" />
      <rect x="6.2" y="1" width="2.8" height="10" rx="1" fill="currentColor" />
    </svg>
  );
}

function RestartGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M2.5 7a4.5 4.5 0 1 0 1.4-3.25" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M3.9 1.2v2.7h2.7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * The live caption itself — pure text, no background, floating at the
 * bottom-center of the frame like a film subtitle, with quiet controls above.
 */
export function LiveCaption({
  line,
  words,
  pos,
  phase,
  caption,
  textShadow,
  prevLine,
  panelOpen,
  playing,
  speed,
  onTogglePlay,
  onRestart,
  onCycleSpeed,
}: LiveCaptionProps) {
  const shownWords = words.slice(0, Math.min(pos, words.length));
  const shownChars = line.text.slice(0, pos);

  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-x-0 bottom-[5.5vh] z-10 flex flex-col items-center gap-4 px-6 transition-[right] duration-500 md:bottom-[6.5vh]",
        panelOpen && "md:right-[360px]"
      )}
    >
      {/* quiet controls */}
      <div className="pointer-events-auto flex items-center gap-2.5">
        <button
          onClick={onTogglePlay}
          className={controlBtn}
          aria-label={playing ? "Pause transcription" : "Resume transcription"}
          title={playing ? "Pause (space)" : "Play (space)"}
        >
          {playing ? <PauseGlyph /> : <PlayGlyph />}
        </button>
        <button onClick={onRestart} className={controlBtn} aria-label="Restart transcript" title="Restart transcript">
          <RestartGlyph />
        </button>
        <button
          onClick={onCycleSpeed}
          className="flex h-9 items-center rounded-full border border-white/15 bg-black/25 px-3 font-mono text-[10px] text-[#f2f4f8] backdrop-blur-sm transition-all duration-200 hover:border-white/40 hover:bg-black/40 active:scale-95"
          title="Playback speed"
        >
          {speed}×
        </button>

        <span className="mx-1 h-3.5 w-px bg-white/20" />

        <span className={cn("eq text-[var(--caption-accent)]", !playing && "paused")} aria-hidden="true">
          <span /><span /><span /><span /><span />
        </span>
        <span
          className="font-mono text-[9px] tracking-[0.34em] text-[#f2f4f8]/85 uppercase"
          style={{ textShadow: "0 1px 8px rgba(0,0,0,0.6)" }}
        >
          {playing ? "Live" : "Paused"}
        </span>
      </div>

      {/* ghost of the previous line */}
      {prevLine && phase === "typing" && (
        <p
          className={cn(
            "ghost-line max-w-[min(760px,90%)] text-center text-[13px] leading-snug text-[var(--caption-ink)] md:text-[14.5px]",
            caption.ghostClassName
          )}
          style={{ textShadow }}
        >
          {prevLine.text}
        </p>
      )}

      {/* speaker cue */}
      {line.speaker && (
        <span
          className="font-mono text-[9.5px] tracking-[0.4em] text-[var(--caption-accent)] uppercase"
          style={{ textShadow: "0 1px 10px rgba(0,0,0,0.55)" }}
        >
          {line.speaker}
        </span>
      )}

      {/* the caption — no background, ever */}
      <p className={cn("max-w-[min(880px,94%)] text-center", caption.className)} style={{ textShadow }}>
        {caption.reveal === "type" && (
          <>
            <span>{shownChars}</span>
            {phase === "typing" && <span className="caret" aria-hidden="true" />}
          </>
        )}

        {caption.reveal === "blur" &&
          shownChars.split("").map((c, i) => (
            <span key={i} className="cap-char">
              {c === " " ? "\u00A0" : c}
            </span>
          ))}

        {(caption.reveal === "fade" || caption.reveal === "rise") &&
          shownWords.map((w, i) => (
            <span key={`${line.text}-${i}`}>
              <span
                className={cn(
                  caption.reveal === "rise" ? "cap-word-rise" : "cap-word",
                  i === shownWords.length - 1 && phase === "typing" && "text-[var(--caption-accent)]"
                )}
              >
                {w}
              </span>
              {i < shownWords.length - 1 ? " " : ""}
            </span>
          ))}
      </p>
    </div>
  );
}
