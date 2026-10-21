import type { Scene } from "@/data/scenes";
import type { LiveLine, Segment } from "@/hooks/useTranscription";
import { StreamText } from "@/components/StreamText";
import { useLevel } from "@/hooks/useTranscription";

/**
 * The live caption strip. Deliberately unbacked — just type, a soft shadow,
 * and a whisper of a listening meter. It sits at the bottom of the frame,
 * centred in the space left of the history rail.
 */
export function CaptionStage({
  scene,
  live,
  last,
  paused,
  rightInset,
}: {
  scene: Scene;
  live: LiveLine | null;
  last: Segment | null;
  paused: boolean;
  rightInset: number;
}) {
  const c = scene.caption;
  const variant = scene.captionVariant;
  const levels = useLevel(16, !paused && !!live);
  const fontSize = `clamp(17px, 1.72vw, ${c.size}px)`;
  const prevSize = `clamp(13px, 1.14vw, ${Math.round(c.size * 0.66)}px)`;
  const speakerName = live ? scene.speakers[live.speaker]?.name : last ? scene.speakers[last.speaker]?.name : "";
  const speakerColor = live
    ? scene.panel.speaker[live.speaker]
    : last
      ? scene.panel.speaker[last.speaker]
      : c.accent;

  const italic = variant === "italic";
  const centered = variant !== "editorial";

  return (
    <div
      className="pointer-events-none absolute bottom-0 left-0 z-20 flex flex-col justify-end pb-[7vh] transition-[right] duration-700"
      style={{ right: rightInset }}
    >
      <div
        className="mx-auto flex w-full flex-col gap-2.5"
        style={{ maxWidth: c.maxWidth, paddingLeft: 32, paddingRight: 32 }}
      >
        {/* listening meta — text only, never a plate */}
        <div
          className="flex items-end gap-3 transition-opacity duration-700"
          style={{ opacity: live ? 0.62 : 0.34, color: c.dim }}
        >
          <span className="flex items-end gap-[2px]" style={{ height: 11 }} aria-hidden>
            {levels.map((v, i) => (
              <span
                key={i}
                style={{
                  width: 2,
                  height: "100%",
                  borderRadius: 999,
                  background: c.accent,
                  transformOrigin: "bottom",
                  transform: `scaleY(${live ? 0.2 + v * 0.8 : 0.14})`,
                  transition: "transform 210ms linear",
                }}
              />
            ))}
          </span>
          <span
            className="f-dm text-[10px] uppercase tracking-[0.3em]"
            style={{ textShadow: c.shadow }}
          >
            {paused ? "held" : live ? "captions · live" : last ? "captions · settled" : "listening to the room"}
          </span>
          <span className="ml-auto f-dm text-[10px] uppercase tracking-[0.24em]" style={{ textShadow: c.shadow }}>
            {scene.session.lang} · {scene.session.model}
          </span>
        </div>

        {/* previous, finished line — faint, still readable */}
        <p
          className="transition-all duration-700"
          style={{
            color: c.dim,
            fontFamily: scene.captionFont,
            fontSize: prevSize,
            lineHeight: 1.45,
            fontWeight: c.weight,
            textAlign: centered ? "center" : "left",
            textShadow: c.shadow,
            opacity: live ? 0.9 : 0,
            transform: live ? "translateY(0)" : "translateY(6px)",
            transformOrigin: "bottom",
            wordBreak: "break-word",
          }}
        >
          {live && last ? last.text : ""}
        </p>

        {/* the live line itself */}
        <div style={{ textAlign: centered ? "center" : "left" }}>
          {variant === "editorial" && speakerName && (
            <div className="mb-1.5 flex items-center gap-2.5">
              <span
                className="text-[10px] uppercase tracking-[0.32em]"
                style={{ color: speakerColor, textShadow: c.shadow, opacity: 0.9 }}
              >
                {speakerName}
              </span>
              <span className="h-[1px] w-8" style={{ background: speakerColor, opacity: 0.45 }} aria-hidden />
            </div>
          )}
          <p
            style={{
              color: c.color,
              fontFamily: scene.captionFont,
              fontSize,
              lineHeight: c.leading,
              fontWeight: c.weight,
              letterSpacing: c.tracking,
              textTransform: c.transform,
              fontStyle: italic ? "italic" : "normal",
              textShadow: c.shadow,
              textWrap: "balance",
              minHeight: "1.4em",
            }}
          >
            {live ? (
              <StreamText
                words={live.words}
                soft={variant !== "tight"}
                caret={variant === "mono" || variant === "tight" || variant === "italic"}
                caretColor={c.accent}
                caretClassName={variant === "mono" ? "h-[1.05em]" : undefined}
              />
            ) : last ? (
              <span key={last.id} className="anim-word-soft inline-block" style={{ opacity: 0.9 }}>
                {last.text}
              </span>
            ) : (
              <span
                className="anim-caret inline-block"
                style={{ width: "0.5ch", height: "1em", background: c.accent, opacity: 0.4, borderRadius: 2 }}
              />
            )}
          </p>
        </div>

        {/* speaker credits for the non-editorial takes */}
        {variant !== "editorial" && (
          <div
            className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] transition-opacity duration-700"
            style={{
              color: speakerColor,
              opacity: live ? 0.55 : last ? 0.4 : 0,
              textShadow: c.shadow,
              justifyContent: centered ? "center" : "flex-start",
            }}
          >
            <span className="h-[1px] w-6" style={{ background: speakerColor, opacity: 0.5 }} aria-hidden />
            {speakerName}
          </div>
        )}
      </div>
    </div>
  );
}
