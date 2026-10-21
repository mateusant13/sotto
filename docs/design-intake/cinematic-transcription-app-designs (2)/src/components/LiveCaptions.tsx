import type { CSSProperties } from "react";
import type { Entry, Partial } from "../hooks/useTranscription";
import type { Theme } from "../themes";
import { speakerShort } from "../lib/scripts";

interface Props {
  theme: Theme;
  partial: Partial | null;
  previous: Entry | null;
  running: boolean;
  level: number;
  speakerColor: (name: string) => string;
}

const SPEAKER_SIZE = "0.66rem";

function LevelBars({ level, color }: { level: number; color: string }) {
  return (
    <span className="flex items-end gap-[3px] h-3.5" aria-hidden>
      {[0.5, 0.8, 1, 0.66, 0.4].map((mult, i) => (
        <span
          key={i}
          className="w-[2.5px] rounded-full transition-[height,opacity] duration-150"
          style={{
            height: `${Math.max(3, level * 13 * mult)}px`,
            background: color,
            opacity: 0.35 + level * 0.6 * mult,
          }}
        />
      ))}
    </span>
  );
}

function StatusBadge({
  running,
  level,
  align,
  plain,
}: {
  theme?: Theme;
  running: boolean;
  level: number;
  align: "left" | "center";
  plain?: boolean;
}) {
  const tint = running ? "var(--live)" : "var(--dim)";
  return (
    <div
      className={`flex items-center gap-2.5 ${align === "center" ? "justify-center" : ""} ${
        plain ? "" : "px-2.5 py-1"
      }`}
      style={
        plain
          ? undefined
          : {
              borderRadius: 999,
              background: "var(--cap-bg)",
              border: "1px solid var(--cap-edge)",
              backdropFilter: "blur(var(--blur))",
            }
      }
    >
      <span className="relative flex h-2 w-2 items-center justify-center">
        <span className="absolute h-2 w-2 rounded-full breathe" style={{ background: tint, opacity: running ? 0.5 : 0.2 }} />
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: tint }} />
      </span>
      <span
        className="uppercase"
        style={{ fontSize: "0.6rem", letterSpacing: "0.3em", color: running ? "var(--text)" : "var(--dim)" }}
      >
        {running ? "listening" : "paused"}
      </span>
      {running && <LevelBars level={level} color={tint} />}
    </div>
  );
}

function Meta({ note }: { theme?: Theme; note: string }) {
  return (
    <div
      className="flex items-center gap-3 text-[9.5px] uppercase"
      style={{ letterSpacing: "0.26em", color: "color-mix(in srgb, var(--text) 42%, transparent)" }}
    >
      <span>{note}</span>
      <span className="h-3 w-px" style={{ background: "color-mix(in srgb, var(--text) 20%, transparent)" }} />
      <span>on-device · 240 ms</span>
    </div>
  );
}

function WordRun({
  words,
  revealed,
  dim,
  bright,
}: {
  words: string[];
  revealed: number;
  dim?: CSSProperties;
  bright?: CSSProperties;
}) {
  return (
    <>
      {words.map((w, i) => (
        <span
          key={`${i}-${w}`}
          className={i === revealed - 1 ? "word-in" : undefined}
          style={{ ...(i < revealed ? bright : dim), display: "inline-block", whiteSpace: "pre" }}
        >
          {w}
          {i < words.length - 1 ? " " : ""}
        </span>
      ))}
    </>
  );
}

function Caret({ color }: { color: string }) {
  return (
    <span
      className="caret ml-1.5 inline-block align-baseline"
      style={{ width: "2px", height: "0.92em", background: color, borderRadius: 2, transform: "translateY(0.06em)" }}
    />
  );
}

export default function LiveCaptions({ theme, partial, previous, running, level, speakerColor }: Props) {
  const { caption, fonts } = theme;
  const base: CSSProperties = {
    fontFamily: fonts.caption,
    fontSize: `clamp(1.02rem, ${caption.size}, 2.3rem)`,
    fontWeight: caption.weight,
    letterSpacing: caption.tracking,
    lineHeight: caption.leading,
    fontStyle: caption.italic ? "italic" : "normal",
    textTransform: caption.upper ? "uppercase" : "none",
  };

  const words = partial?.words ?? previous?.text.split(" ") ?? [];
  const revealed = partial ? partial.revealed : words.length;
  const speaker = partial?.speaker ?? previous?.speaker ?? "";
  const tone = speaker ? speakerColor(speaker) : "var(--text)";
  const capText = "var(--cap-text)";
  const align = caption.align;
  const isLive = Boolean(partial) && running;
  const note = partial ? `transcribing ${speakerShort(partial.speaker)}` : "last line";

  const shadow = "0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)";

  /** ---------- variant 1: floating type ---------- */
  if (caption.style === "bare") {
    return (
      <div className="flex flex-col gap-3.5">
        <div className={align === "center" ? "text-center" : ""}>
          <span className="inline-flex">
            <StatusBadge theme={theme} running={running} level={level} align={align} />
          </span>
        </div>
        <div style={{ ...base, color: capText, textShadow: shadow }}>
          {speaker && (
            <span
              className="mr-3 align-middle"
              style={{
                fontSize: `calc(${SPEAKER_SIZE} * 1.15)`,
                letterSpacing: "0.3em",
                textTransform: "uppercase",
                color: tone,
                textShadow: "none",
              }}
            >
              {speakerShort(speaker)}
            </span>
          )}
          {words.length === 0 ? (
            <span style={{ opacity: 0.4, fontStyle: "italic" }}>the room is quiet…</span>
          ) : (
            <WordRun words={words} revealed={revealed} />
          )}
          {isLive && <Caret color={tone} />}
        </div>
        <div className={align === "center" ? "flex justify-center" : ""}>
          <Meta theme={theme} note={note} />
        </div>
      </div>
    );
  }

  /** ---------- variant 2: frosted glass ---------- */
  if (caption.style === "glass") {
    return (
      <div
        className="soft-in px-6 py-4 sm:px-8 sm:py-5"
        style={{
          ...base,
          background: "var(--cap-bg)",
          border: "1px solid var(--cap-edge)",
          borderRadius: "var(--radius)",
          backdropFilter: "blur(var(--blur)) saturate(1.15)",
          WebkitBackdropFilter: "blur(var(--blur)) saturate(1.15)",
          boxShadow: "0 30px 80px -40px rgba(0,0,0,.9), inset 0 1px 0 rgba(255,255,255,.06)",
        }}
      >
        <div className="mb-2.5 flex items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: tone, boxShadow: `0 0 10px ${tone}` }} />
            <span
              className="uppercase"
              style={{ fontSize: SPEAKER_SIZE, letterSpacing: "0.26em", color: tone, fontFamily: fonts.ui }}
            >
              {speaker ? speakerShort(speaker) : "—"}
            </span>
          </div>
          <span className={running ? "" : "opacity-0"}>
            <LevelBars level={level} color="color-mix(in srgb, var(--cap-text) 55%, transparent)" />
          </span>
        </div>
        <div style={{ color: capText }}>
          {words.length === 0 ? (
            <span style={{ opacity: 0.45, fontStyle: "italic" }}>waiting for the first line…</span>
          ) : (
            <WordRun words={words} revealed={revealed} />
          )}
          {isLive && <Caret color={tone} />}
        </div>
        <div className="mt-2.5 flex items-center justify-between gap-4" style={{ fontFamily: fonts.ui }}>
          <Meta theme={theme} note={note} />
          <span
            className="text-[9.5px] uppercase"
            style={{ letterSpacing: "0.24em", color: "color-mix(in srgb, var(--cap-text) 38%, transparent)" }}
          >
            {running ? "live track" : "hold"}
          </span>
        </div>
      </div>
    );
  }

  /** ---------- variant 3: solid plate ---------- */
  if (caption.style === "plate") {
    return (
      <div
        className="soft-in"
        style={{
          ...base,
          background: "var(--cap-bg)",
          border: "1px solid var(--cap-edge)",
          borderRadius: "var(--radius)",
          padding: "1.05rem 1.6rem 0.95rem",
          boxShadow: "0 26px 70px -36px rgba(0,0,0,.85)",
        }}
      >
        <div className="flex items-start gap-4">
          <div className="flex flex-col items-center gap-2 pt-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: running ? "var(--live)" : "var(--dim)" }}
            />
            <span className="w-px flex-1" style={{ background: "color-mix(in srgb, var(--cap-text) 18%, transparent)" }} />
          </div>
          <div className="flex-1">
            <div
              className="mb-1.5 flex items-center gap-3"
              style={{ fontFamily: fonts.ui, fontSize: SPEAKER_SIZE, letterSpacing: "0.28em" }}
            >
              <span className="uppercase" style={{ color: tone }}>
                {speaker ? speakerShort(speaker) : "—"}
              </span>
              <span style={{ color: "color-mix(in srgb, var(--cap-text) 40%, transparent)" }}>
                {running ? "speaking now" : "paused"}
              </span>
            </div>
            <div style={{ color: capText }}>
              {words.length === 0 ? (
                <span style={{ opacity: 0.4 }}>…</span>
              ) : (
                <WordRun words={words} revealed={revealed} />
              )}
              {isLive && <Caret color={tone} />}
            </div>
          </div>
        </div>
      </div>
    );
  }

  /** ---------- variant 4: speaker chip ---------- */
  if (caption.style === "chip") {
    return (
      <div
        className="soft-in flex flex-col gap-2.5 px-5 py-4 sm:px-6"
        style={{
          ...base,
          background: "var(--cap-bg)",
          border: "1px solid var(--cap-edge)",
          borderRadius: "calc(var(--radius) * 0.9)",
          backdropFilter: "blur(calc(var(--blur) * 0.8))",
          WebkitBackdropFilter: "blur(calc(var(--blur) * 0.8))",
          boxShadow: "0 24px 60px -34px rgba(0,0,0,.78)",
        }}
      >
        <div className="flex items-center gap-3" style={{ fontFamily: fonts.ui }}>
          <span
            className="inline-flex items-center gap-2 rounded-full px-3 py-1"
            style={{
              background: `color-mix(in srgb, ${tone} 18%, transparent)`,
              border: `1px solid color-mix(in srgb, ${tone} 34%, transparent)`,
            }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: tone }} />
            <span className="uppercase" style={{ fontSize: SPEAKER_SIZE, letterSpacing: "0.24em", color: tone }}>
              {speaker ? speakerShort(speaker) : "—"}
            </span>
          </span>
          <span
            className="uppercase"
            style={{
              fontSize: "0.58rem",
              letterSpacing: "0.26em",
              color: "color-mix(in srgb, var(--cap-text) 40%, transparent)",
            }}
          >
            {running ? "capturing" : "paused"}
          </span>
          <span className="ml-auto">
            <LevelBars level={level} color="color-mix(in srgb, var(--cap-text) 50%, transparent)" />
          </span>
        </div>
        <div style={{ color: capText }}>
          {words.length === 0 ? (
            <span style={{ opacity: 0.42, fontStyle: "italic" }}>nothing said yet, that's alright…</span>
          ) : (
            <WordRun words={words} revealed={revealed} />
          )}
          {isLive && <Caret color={tone} />}
        </div>
      </div>
    );
  }

  /** ---------- variant 5: two-line roll ---------- */
  if (caption.style === "stack") {
    const prevText = previous ? previous.text : "";
    const showPrev = Boolean(partial) && prevText && prevText !== words.join(" ");
    return (
      <div
        className="soft-in px-5 py-4 sm:px-7"
        style={{
          ...base,
          background: "var(--cap-bg)",
          borderLeft: `2px solid ${tone}`,
          borderRadius: "calc(var(--radius) * 0.55)",
          backdropFilter: "blur(calc(var(--blur) * 0.7))",
          WebkitBackdropFilter: "blur(calc(var(--blur) * 0.7))",
          boxShadow: "0 24px 60px -34px rgba(0,0,0,.8)",
        }}
      >
        <div className="mb-2 flex items-center gap-3" style={{ fontFamily: fonts.ui }}>
          <StatusBadge theme={theme} running={running} level={level} align="left" plain />
          <span
            className="ml-auto uppercase"
            style={{
              fontSize: "0.56rem",
              letterSpacing: "0.26em",
              color: "color-mix(in srgb, var(--cap-text) 34%, transparent)",
            }}
          >
            rolling
          </span>
        </div>
        {showPrev && (
          <div
            className="mb-2 truncate"
            style={{
              color: "color-mix(in srgb, var(--cap-text) 34%, transparent)",
              fontSize: `calc(${caption.size} * 0.66)`,
              fontFamily: fonts.caption,
              letterSpacing: caption.tracking,
            }}
          >
            {prevText}
          </div>
        )}
        <div style={{ color: capText }}>
          {words.length === 0 ? (
            <span style={{ opacity: 0.42, fontStyle: "italic" }}>rolling…</span>
          ) : (
            <WordRun words={words} revealed={revealed} />
          )}
          {isLive && <Caret color={tone} />}
        </div>
      </div>
    );
  }

  /** ---------- variant 6: read-along (karaoke) ---------- */
  return (
    <div
      className="soft-in px-6 py-4 sm:px-8 sm:py-5"
      style={{
        ...base,
        background: "var(--cap-bg)",
        border: "1px solid var(--cap-edge)",
        borderRadius: "var(--radius)",
        backdropFilter: "blur(var(--blur))",
        WebkitBackdropFilter: "blur(var(--blur))",
        boxShadow: "0 28px 74px -38px rgba(0,0,0,.85)",
      }}
    >
      <div className="mb-2.5 flex items-center gap-3" style={{ fontFamily: fonts.ui }}>
        <span className="uppercase" style={{ fontSize: SPEAKER_SIZE, letterSpacing: "0.26em", color: tone }}>
          {speaker ? speakerShort(speaker) : "—"}
        </span>
        <span className="h-3 w-px" style={{ background: "color-mix(in srgb, var(--cap-text) 22%, transparent)" }} />
        <span className={running ? "" : "opacity-40"}>
          <LevelBars level={level} color={tone} />
        </span>
        <span
          className="ml-auto uppercase"
          style={{
            fontSize: "0.56rem",
            letterSpacing: "0.26em",
            color: "color-mix(in srgb, var(--cap-text) 34%, transparent)",
          }}
        >
          read-along
        </span>
      </div>
      <div style={{ color: capText }}>
        {words.length === 0 ? (
          <span style={{ opacity: 0.42, fontStyle: "italic" }}>waiting…</span>
        ) : (
          <WordRun
            words={words}
            revealed={revealed}
            bright={{ color: capText, filter: "blur(0px)", transition: "color .3s ease, filter .3s ease" }}
            dim={{ color: "color-mix(in srgb, var(--cap-text) 30%, transparent)", filter: "blur(1.1px)", transition: "color .3s ease, filter .3s ease" }}
          />
        )}
        {isLive && <Caret color={tone} />}
      </div>
      <div className="mt-2.5">
        <Meta theme={theme} note={note} />
      </div>
    </div>
  );
}
