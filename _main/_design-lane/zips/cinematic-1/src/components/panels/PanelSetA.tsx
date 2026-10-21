import { formatClock, formatShort } from "@/data/scenes";
import type { Segment } from "@/hooks/useTranscription";
import { StreamText } from "@/components/StreamText";
import {
  GhostButton,
  IconBroom,
  IconExport,
  IconPause,
  IconPlay,
  IconWaves,
  LevelMeter,
  LiveDot,
  initials,
  useAutoScroll,
  wordsOf,
  type PanelProps,
} from "./shared";

/* ------------------------------------------------------------------ 01 ---
   Midnight Café — frosted glass cards floating over the room.
------------------------------------------------------------------------- */
export function GlassCards(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));

  const surface = (extra?: string) =>
    ({ background: p.surface, border: `1px solid ${extra ?? p.border}`, backdropFilter: `blur(${p.blur}px)`, WebkitBackdropFilter: `blur(${p.blur}px)` }) as const;

  return (
    <div className="flex h-full flex-col gap-3" style={{ fontFamily: scene.panelFont }}>
      <div className="anim-panel p-4" style={{ ...surface(), borderRadius: p.radius, boxShadow: p.shadow }}>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-[10.5px] uppercase tracking-[0.22em]" style={{ color: p.muted }}>
            <LiveDot color={p.accent} active={!paused} />
            {paused ? "paused" : "live transcript"}
          </span>
          <span className="f-dm text-[11px] tabular-nums" style={{ color: p.muted }}>
            {formatClock(elapsed)}
          </span>
        </div>
        <h2 className="mt-3 text-[15px] font-medium leading-snug" style={{ color: p.text }}>
          {scene.session.title}
        </h2>
        <p className="mt-1 text-[11.5px] leading-relaxed" style={{ color: p.muted }}>
          {scene.session.note}
        </p>
        <div className="mt-3.5 flex items-center gap-2.5 border-t pt-3" style={{ borderColor: p.border }}>
          <div className="flex -space-x-2">
            {Object.entries(scene.speakers).map(([id, sp]) => (
              <span
                key={id}
                className="grid h-6 w-6 place-items-center rounded-full text-[9.5px] font-medium"
                style={{ background: `${scene.panel.speaker[id]}26`, color: scene.panel.speaker[id], border: `1px solid ${scene.panel.speaker[id]}33` }}
              >
                {initials(sp.name)}
              </span>
            ))}
          </div>
          <span className="flex-1 text-[10.5px]" style={{ color: p.muted }}>
            {scene.session.lang} · {scene.session.device}
          </span>
          <LevelMeter bars={12} active={!paused} color={p.accent} />
        </div>
      </div>

      <div ref={scroller} className="scroll-quiet flex-1 space-y-2.5 overflow-y-auto pr-1.5" style={{ paddingBottom: 4 }}>
        {segments.map((s: Segment, i) => {
          const isLast = i === segments.length - 1;
          const color = p.speaker[s.speaker] ?? p.accent;
          return (
            <div
              key={s.id}
              className="anim-seg flex gap-3 p-3"
              style={{ ...surface(isLast ? `${color}30` : undefined), borderRadius: Math.max(12, p.radius - 6) }}
            >
              <span
                className="mt-[2px] grid h-7 w-7 shrink-0 place-items-center rounded-full text-[10px] font-medium"
                style={{ background: `${color}22`, color }}
              >
                {initials(scene.speakers[s.speaker]?.name ?? "??")}
              </span>
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="text-[11.5px] font-medium" style={{ color }}>
                    {scene.speakers[s.speaker]?.name}
                  </span>
                  <span className="f-dm text-[10px] tabular-nums" style={{ color: p.muted }}>
                    {formatShort(s.at)}
                  </span>
                </div>
                <p className="mt-1 text-[13px] leading-relaxed" style={{ color: p.text, opacity: 0.94 }}>
                  {s.text}
                </p>
              </div>
            </div>
          );
        })}

        {live && (
          <div
            className="flex gap-3 p-3"
            style={{ ...surface(`${p.accent}3d`), borderRadius: Math.max(12, p.radius - 6) }}
          >
            <span
              className="mt-[2px] grid h-7 w-7 shrink-0 place-items-center rounded-full text-[10px] font-medium"
              style={{ background: `${p.speaker[live.speaker]}22`, color: p.speaker[live.speaker] }}
            >
              {initials(scene.speakers[live.speaker]?.name ?? "??")}
            </span>
            <div className="min-w-0">
              <span className="text-[11.5px] font-medium" style={{ color: p.speaker[live.speaker] }}>
                {scene.speakers[live.speaker]?.name}
              </span>
              <p className="mt-1 text-[13px] leading-relaxed" style={{ color: p.text }}>
                <StreamText words={live.words} caretColor={p.accent} />
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-1" style={{ color: p.muted }}>
        <span className="f-dm text-[10.5px]">
          {wordsOf(segments)} words · {segments.length} segments
        </span>
        <span className="flex items-center gap-1">
          <GhostButton onClick={onToggle} className="hover:bg-white/10" style={{ color: p.text }}>
            {paused ? <IconPlay size={12} /> : <IconPause size={12} />}
            {paused ? "resume" : "pause"}
          </GhostButton>
          <GhostButton onClick={onClear} className="hover:bg-white/10" style={{ color: p.muted }} title="Clear session">
            <IconBroom size={12} />
          </GhostButton>
          <GhostButton className="hover:bg-white/10" style={{ color: p.muted }} title="Export transcript">
            <IconExport size={12} />
          </GhostButton>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 02 ---
   Rainglass — near-invisible panel, hairlines only.
------------------------------------------------------------------------- */
export function Hairline(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));

  return (
    <div className="flex h-full flex-col" style={{ fontFamily: scene.panelFont }}>
      <div className="anim-panel pb-3">
        <div className="flex items-end justify-between">
          <span className="text-[9.5px] uppercase tracking-[0.3em]" style={{ color: p.muted }}>
            transcript
          </span>
          <span className="f-dm text-[10.5px] tabular-nums" style={{ color: p.muted }}>
            {formatClock(elapsed)}
          </span>
        </div>
        <div className="mt-2 flex items-center gap-4 border-b pb-2 text-[11px]" style={{ borderColor: p.border }}>
          {["transcript", "speakers", "notes"].map((tab, i) => (
            <span
              key={tab}
              className="relative pb-1 transition-colors duration-300"
              style={{ color: i === 0 ? p.text : p.muted }}
            >
              {tab}
              {i === 0 && <span className="absolute -bottom-[2px] left-0 h-[1px] w-full" style={{ background: p.accent }} />}
            </span>
          ))}
          <span className="ml-auto flex items-center gap-2 text-[10.5px]" style={{ color: paused ? p.muted : p.accent }}>
            <LiveDot color={p.accent} size={5} ring={false} active={!paused} />
            {paused ? "paused" : "streaming"}
          </span>
        </div>
      </div>

      <div ref={scroller} className="scroll-quiet mask-fade-top flex-1 overflow-y-auto pr-1">
        {segments.map((s) => (
          <div
            key={s.id}
            className="anim-seg grid grid-cols-[44px_1fr] gap-3 border-b py-3 transition-colors duration-500 hover:bg-white/[0.04]"
            style={{ borderColor: p.border }}
          >
            <span className="f-dm pt-[2px] text-[10px] tabular-nums" style={{ color: p.muted }}>
              {formatShort(s.at)}
            </span>
            <div>
              <span
                className="flex items-center gap-1.5 text-[9.5px] uppercase tracking-[0.2em]"
                style={{ color: p.speaker[s.speaker] }}
              >
                <span className="h-[4px] w-[4px] rounded-full" style={{ background: p.speaker[s.speaker] }} />
                {scene.speakers[s.speaker]?.name}
              </span>
              <p className="mt-[5px] text-[13px] font-light leading-[1.65]" style={{ color: p.text }}>
                {s.text}
              </p>
            </div>
          </div>
        ))}

        {live && (
          <div className="grid grid-cols-[44px_1fr] gap-3 py-3">
            <span className="f-dm pt-[2px] text-[10px] tabular-nums" style={{ color: p.accent }}>
              now
            </span>
            <div>
              <span
                className="flex items-center gap-1.5 text-[9.5px] uppercase tracking-[0.2em]"
                style={{ color: p.speaker[live.speaker] }}
              >
                <span className="h-[4px] w-[4px] rounded-full" style={{ background: p.speaker[live.speaker] }} />
                {scene.speakers[live.speaker]?.name}
              </span>
              <p className="mt-[5px] text-[13px] font-light leading-[1.65]" style={{ color: p.text }}>
                <StreamText words={live.words} caretColor={p.accent} />
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-3 text-[10.5px]" style={{ color: p.muted }}>
        <span className="f-dm">
          {wordsOf(segments)} w · {segments.length} seg
        </span>
        <span className="flex items-center gap-3">
          <button type="button" onClick={onToggle} className="transition-colors hover:opacity-100" style={{ opacity: 0.85 }}>
            {paused ? "resume" : "pause"}
          </button>
          <button type="button" onClick={onClear} className="transition-colors hover:opacity-100" style={{ opacity: 0.85 }}>
            clear
          </button>
          <button type="button" className="transition-colors hover:opacity-100" style={{ opacity: 0.85 }}>
            export .txt
          </button>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 03 ---
   Dustlight — a typewritten page from a road log.
------------------------------------------------------------------------- */
export function Paper(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));

  return (
    <div
      className="anim-panel relative flex h-full flex-col overflow-hidden"
      style={{ background: p.surface, borderRadius: p.radius, boxShadow: p.shadow, border: `1px solid ${p.border}` }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.5]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(180deg, transparent 0 27px, rgba(60,40,26,0.075) 27px 28px)",
        }}
      />
      <div className="pointer-events-none absolute inset-y-0 left-[52px] w-[1.5px]" style={{ background: `${p.accent}59` }} />

      <div className="relative px-5 pb-3 pt-4" style={{ fontFamily: "Newsreader, Georgia, serif" }}>
        <div className="flex items-start justify-between">
          <div>
            <span className="f-dm text-[9.5px] uppercase tracking-[0.28em]" style={{ color: p.accent }}>
              tape 04 — {scene.hour}
            </span>
            <h2 className="mt-1 text-[19px] leading-tight" style={{ color: p.text }}>
              {scene.session.title}
            </h2>
          </div>
          <span className="f-dm text-[10px]" style={{ color: p.muted }}>
            p.1/1
          </span>
        </div>
        <p className="f-dm mt-1.5 text-[10.5px]" style={{ color: p.muted }}>
          {scene.session.device} · {paused ? "held" : formatClock(elapsed)}
        </p>
      </div>

      <div ref={scroller} className="scroll-light scroll-quiet relative flex-1 overflow-y-auto px-5 pb-3" style={{ fontFamily: scene.panelFont }}>
        {segments.map((s, i) => (
          <div key={s.id} className="anim-seg grid grid-cols-[52px_1fr] gap-3 py-[7px]">
            <span className="pt-[3px] text-right text-[9.5px] tabular-nums" style={{ color: p.muted }}>
              {formatShort(s.at)}
            </span>
            <p className="text-[12.5px] leading-[27px]" style={{ color: p.text }}>
              <span className="mr-1.5 text-[10px] uppercase tracking-[0.16em]" style={{ color: p.speaker[s.speaker] }}>
                {scene.speakers[s.speaker]?.name}
              </span>
              {s.text}
              {i === segments.length - 1 && !live && (
                <span className="ml-2 align-middle text-[9px] uppercase tracking-[0.2em]" style={{ color: p.accent }}>
                  filed
                </span>
              )}
            </p>
          </div>
        ))}

        {live && (
          <div className="grid grid-cols-[52px_1fr] gap-3 py-[7px]">
            <span className="pt-[3px] text-right text-[9.5px] tabular-nums" style={{ color: p.accent }}>
              .....
            </span>
            <p className="text-[12.5px] leading-[27px]" style={{ color: p.text }}>
              <span className="mr-1.5 text-[10px] uppercase tracking-[0.16em]" style={{ color: p.speaker[live.speaker] }}>
                {scene.speakers[live.speaker]?.name}
              </span>
              <StreamText words={live.words} caretColor={p.accent} caretClassName="h-[0.9em]" />
            </p>
          </div>
        )}
        <div className="py-4 text-center text-[10px] italic" style={{ color: p.muted, fontFamily: "Newsreader, Georgia, serif" }}>
          — continued, please don't brake on the gravel —
        </div>
      </div>

      <div className="relative flex items-center justify-between border-t px-5 py-2.5" style={{ borderColor: p.border }}>
        <span className="f-dm text-[10px]" style={{ color: p.muted }}>
          {wordsOf(segments)} words
        </span>
        <span className="flex items-center gap-3">
          <button type="button" onClick={onToggle} className="f-dm text-[10px] transition-opacity hover:opacity-60" style={{ color: p.text }}>
            {paused ? "resume" : "pause"}
          </button>
          <button type="button" onClick={onClear} className="f-dm text-[10px] transition-opacity hover:opacity-60" style={{ color: p.muted }}>
            new page
          </button>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 04 ---
   Analog — sleeve notes on cocoa paper, one quote per card.
------------------------------------------------------------------------- */
export function Quotes(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));

  return (
    <div className="flex h-full flex-col gap-3.5" style={{ fontFamily: scene.panelFont }}>
      <div className="anim-panel px-4 py-3.5" style={{ background: p.surface, border: `1px solid ${p.border}`, borderRadius: p.radius, backdropFilter: `blur(${p.blur}px)`, boxShadow: p.shadow }}>
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-[16px] leading-snug" style={{ color: p.text }}>
            {scene.session.title}
          </h2>
          <span className="shrink-0 text-[10px] uppercase tracking-[0.18em]" style={{ color: p.accent }}>
            side A
          </span>
        </div>
        <p className="mt-1 text-[11.5px] italic" style={{ color: p.muted }}>
          {scene.session.note}
        </p>
        <div className="mt-3 flex items-center gap-3 text-[10.5px]" style={{ color: p.muted }}>
          <span className="flex items-center gap-1.5">
            <LiveDot color={p.accent} size={5} active={!paused} />
            {paused ? "held" : "needle down"}
          </span>
          <span className="f-dm tabular-nums">{formatClock(elapsed)}</span>
          <LevelMeter bars={10} active={!paused} color={p.accent} className="ml-auto" />
        </div>
      </div>

      <div ref={scroller} className="scroll-quiet mask-fade-top flex-1 space-y-3 overflow-y-auto pr-1.5">
        {segments.map((s, i) => {
          const isLast = i === segments.length - 1;
          const color = p.speaker[s.speaker] ?? p.accent;
          return (
            <div
              key={s.id}
              className="anim-seg relative px-4 py-3.5 pl-5"
              style={{
                background: isLast ? `${color}14` : p.surface,
                border: `1px solid ${isLast ? `${color}33` : p.border}`,
                borderLeft: `2px solid ${isLast ? color : "transparent"}`,
                borderRadius: p.radius - 4,
                backdropFilter: `blur(${p.blur}px)`,
              }}
            >
              <span
                className="pointer-events-none absolute -top-1 left-3 text-[34px] leading-none"
                style={{ color: `${color}2e`, fontFamily: "Instrument Serif, Georgia, serif" }}
              >
                “
              </span>
              <p className="relative text-[13.5px] leading-[1.6]" style={{ color: p.text }}>
                {s.text}
              </p>
              <div className="mt-2.5 flex items-baseline gap-2 text-[10.5px]" style={{ color: p.muted }}>
                <span className="h-[1px] w-5 translate-y-[-3px]" style={{ background: color, opacity: 0.6 }} />
                <span style={{ color }}>{scene.speakers[s.speaker]?.name}</span>
                <span className="f-dm">{formatShort(s.at)}</span>
              </div>
            </div>
          );
        })}

        {live && (
          <div
            className="px-4 py-3.5 pl-5"
            style={{
              background: `${p.accent}12`,
              border: `1px solid ${p.accent}30`,
              borderLeft: `2px solid ${p.accent}`,
              borderRadius: p.radius - 4,
              backdropFilter: `blur(${p.blur}px)`,
            }}
          >
            <p className="text-[13.5px] leading-[1.6]" style={{ color: p.text }}>
              <StreamText words={live.words} caretColor={p.accent} />
            </p>
            <div className="mt-2.5 flex items-baseline gap-2 text-[10.5px]" style={{ color: p.muted }}>
              <span className="h-[1px] w-5 translate-y-[-3px]" style={{ background: p.accent, opacity: 0.6 }} />
              <span style={{ color: p.speaker[live.speaker] }}>{scene.speakers[live.speaker]?.name}</span>
              <span className="f-dm">writing…</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-1 text-[10.5px]" style={{ color: p.muted }}>
        <span>{wordsOf(segments)} words across {segments.length} takes</span>
        <span className="flex items-center gap-1">
          <GhostButton onClick={onToggle} className="hover:bg-white/10" style={{ color: p.text }}>
            {paused ? <IconPlay size={11} /> : <IconPause size={11} />}
            {paused ? "resume" : "hold"}
          </GhostButton>
          <GhostButton onClick={onClear} className="hover:bg-white/10" title="Flip the record">
            <IconWaves size={12} />
          </GhostButton>
          <GhostButton className="hover:bg-white/10" title="Export">
            <IconExport size={12} />
          </GhostButton>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 05 ---
   Quiet Shelves — a quiet ledger: time · speaker · transcript.
------------------------------------------------------------------------- */
export function Ledger(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));

  return (
    <div className="flex h-full flex-col" style={{ fontFamily: scene.panelFont }}>
      <div className="anim-panel flex items-end justify-between gap-4 pb-3">
        <div>
          <span className="text-[9px] uppercase tracking-[0.34em]" style={{ color: p.muted }}>
            closed hours log
          </span>
          <h2 className="mt-1.5 text-[15px] font-light leading-snug tracking-tight" style={{ color: p.text }}>
            {scene.session.title}
          </h2>
        </div>
        <div className="text-right">
          <div className="f-dm text-[13px] tabular-nums" style={{ color: p.accent }}>
            {formatClock(elapsed)}
          </div>
          <div className="text-[10px]" style={{ color: p.muted }}>
            {paused ? "paused" : scene.session.model}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-[46px_58px_1fr] gap-2 border-y px-3 py-2 text-[9px] uppercase tracking-[0.2em]" style={{ borderColor: p.border, color: p.muted }}>
        <span>time</span>
        <span>voice</span>
        <span>transcript</span>
      </div>

      <div ref={scroller} className="scroll-quiet flex-1 overflow-y-auto">
        {segments.map((s, i) => (
          <div
            key={s.id}
            className="anim-seg grid grid-cols-[46px_58px_1fr] items-baseline gap-2 border-b px-3 py-2.5 transition-colors duration-500"
            style={{ borderColor: p.border, background: i % 2 ? p.soft : "transparent" }}
          >
            <span className="f-dm text-[10px] tabular-nums" style={{ color: p.muted }}>
              {formatShort(s.at)}
            </span>
            <span className="text-[10.5px] uppercase tracking-[0.12em]" style={{ color: p.speaker[s.speaker] }}>
              {scene.speakers[s.speaker]?.name}
            </span>
            <p className="text-[12.5px] font-light leading-relaxed" style={{ color: p.text }}>
              {s.text}
            </p>
          </div>
        ))}

        {live && (
          <div className="grid grid-cols-[46px_58px_1fr] items-baseline gap-2 border-b px-3 py-2.5" style={{ borderColor: `${p.accent}40`, background: p.soft }}>
            <span className="f-dm flex items-center gap-1.5 text-[10px]" style={{ color: p.accent }}>
              <LiveDot color={p.accent} size={5} ring={false} active={!paused} />
            </span>
            <span className="text-[10.5px] uppercase tracking-[0.12em]" style={{ color: p.speaker[live.speaker] }}>
              {scene.speakers[live.speaker]?.name}
            </span>
            <p className="text-[12.5px] font-light leading-relaxed" style={{ color: p.text }}>
              <StreamText words={live.words} caretColor={p.accent} />
            </p>
          </div>
        )}
      </div>

      <div className="mt-1 flex items-center justify-between border-t px-3 pt-2.5 text-[10px] uppercase tracking-[0.16em]" style={{ borderColor: p.border, color: p.muted }}>
        <span className="flex items-center gap-3">
          <span>seg {segments.length}</span>
          <span>words {wordsOf(segments)}</span>
          <span>{scene.session.lang}</span>
        </span>
        <span className="flex items-center gap-3 normal-case tracking-normal">
          <button type="button" onClick={onToggle} className="transition-opacity hover:opacity-60">
            {paused ? "resume" : "hold"}
          </button>
          <button type="button" onClick={onClear} className="transition-opacity hover:opacity-60">
            new log
          </button>
        </span>
      </div>
    </div>
  );
}

export const panelSetA = {
  glassCards: GlassCards,
  hairline: Hairline,
  paper: Paper,
  quotes: Quotes,
  ledger: Ledger,
};
