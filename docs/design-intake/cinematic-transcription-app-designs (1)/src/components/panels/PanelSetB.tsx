import { formatClock, formatShort } from "@/data/scenes";
import { StreamText } from "@/components/StreamText";
import {
  GhostButton,
  IconBroom,
  IconExport,
  IconPause,
  IconPlay,
  IconSearch,
  LevelMeter,
  LiveDot,
  initials,
  useAutoScroll,
  wordsOf,
  type PanelProps,
} from "./shared";

/* ------------------------------------------------------------------ 06 ---
   Lamp Black — an ambient event log for a room that never sleeps.
------------------------------------------------------------------------- */
export function Feed(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));
  const total = segments.length;

  return (
    <div
      className="anim-panel flex h-full flex-col overflow-hidden"
      style={{ background: p.surface, border: `1px solid ${p.border}`, borderRadius: p.radius, backdropFilter: `blur(${p.blur}px)`, boxShadow: p.shadow, fontFamily: scene.panelFont }}
    >
      <div className="relative border-b px-4 py-3" style={{ borderColor: p.border }}>
        <div className="flex items-center gap-2 text-[10.5px]" style={{ color: p.text }}>
          <LiveDot color={paused ? p.muted : p.accent} size={6} active={!paused} ring={false} />
          <span className="uppercase tracking-[0.18em]">{paused ? "held" : "rec"}</span>
          <span className="tabular-nums" style={{ color: p.muted }}>
            {formatClock(elapsed)}
          </span>
          <span className="ml-auto truncate text-[10px]" style={{ color: p.muted }}>
            {scene.session.device}
          </span>
        </div>
        <div className="mt-2.5 h-[1px] w-full overflow-hidden" style={{ background: p.border }}>
          <span
            className="anim-sheen block h-full w-1/3"
            style={{ background: `linear-gradient(90deg, transparent, ${p.accent}, transparent)` }}
          />
        </div>
      </div>

      <div ref={scroller} className="scroll-quiet mask-fade-top flex-1 overflow-y-auto px-4 py-3 text-[11.5px] leading-[1.75]">
        {segments.map((s, i) => {
          const distance = total - 1 - i;
          const fade = Math.max(0.14, 1 - distance * 0.075);
          const color = p.speaker[s.speaker] ?? p.accent;
          return (
            <div key={s.id} className="anim-seg flex gap-2 transition-opacity duration-700" style={{ opacity: fade }}>
              <span className="shrink-0 tabular-nums" style={{ color: `${p.accent}${distance === 0 ? "" : "99"}` }}>
                {formatShort(s.at)}
              </span>
              <span className="shrink-0" style={{ color }}>
                {scene.speakers[s.speaker]?.name.toLowerCase()}
              </span>
              <span style={{ color: p.text }}>{s.text}</span>
            </div>
          );
        })}

        {live && (
          <div className="flex gap-2" style={{ color: p.text }}>
            <span className="anim-caret shrink-0" style={{ color: p.accent }}>
              &gt;
            </span>
            <span className="shrink-0" style={{ color: p.speaker[live.speaker] }}>
              {scene.speakers[live.speaker]?.name.toLowerCase()}
            </span>
            <span>
              <StreamText words={live.words} caretColor={p.accent} />
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t px-4 py-2.5 text-[10.5px]" style={{ borderColor: p.border, color: p.muted }}>
        <span className="flex items-center gap-3">
          <span className="tabular-nums">{wordsOf(segments)}w</span>
          <span>{scene.session.lang}</span>
          <LevelMeter bars={9} active={!paused} color={p.accent} height={10} width={2} />
        </span>
        <span className="flex items-center gap-2">
          <button type="button" onClick={onToggle} className="inline-flex items-center gap-1 transition-opacity hover:opacity-60">
            {paused ? <IconPlay size={11} /> : <IconPause size={11} />}
            {paused ? "resume" : "hold"}
          </button>
          <button type="button" onClick={onClear} className="transition-opacity hover:opacity-60">
            <IconBroom size={11} />
          </button>
          <button type="button" className="transition-opacity hover:opacity-60">
            <IconExport size={11} />
          </button>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 07 ---
   Rooftop Dusk — a two-voice conversation in soft bubbles.
------------------------------------------------------------------------- */
export function Bubbles(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));
  const speakerIds = Object.keys(scene.speakers);
  const rightId = speakerIds[1] ?? speakerIds[0];

  return (
    <div className="flex h-full flex-col gap-3" style={{ fontFamily: scene.panelFont }}>
      <div className="anim-panel rounded-3xl px-4 py-3.5" style={{ background: p.surface, border: `1px solid ${p.border}`, backdropFilter: `blur(${p.blur}px)`, boxShadow: p.shadow }}>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[13.5px] font-medium" style={{ color: p.text }}>
            {scene.session.title}
          </h2>
          <span className="f-dm text-[10.5px] tabular-nums" style={{ color: p.muted }}>
            {formatClock(elapsed)}
          </span>
        </div>
        <div className="mt-2.5 flex items-center gap-2">
          {speakerIds.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[10.5px]"
              style={{ background: `${p.speaker[id]}1a`, color: p.speaker[id] }}
            >
              <span className="h-[5px] w-[5px] rounded-full" style={{ background: p.speaker[id] }} />
              {scene.speakers[id].name}
            </span>
          ))}
          <span className="ml-auto text-[10px]" style={{ color: paused ? p.muted : p.accent }}>
            {paused ? "paused" : "on air"}
          </span>
        </div>
      </div>

      <div ref={scroller} className="scroll-quiet flex-1 space-y-2.5 overflow-y-auto pr-1.5">
        {segments.map((s) => {
          const isRight = s.speaker === rightId;
          const color = p.speaker[s.speaker] ?? p.accent;
          return (
            <div key={s.id} className={`anim-seg flex ${isRight ? "justify-end" : "justify-start"}`}>
              <div
                className="max-w-[86%] px-3.5 py-2.5"
                style={{
                  background: isRight ? `${color}1a` : p.surface,
                  border: `1px solid ${isRight ? `${color}2e` : p.border}`,
                  borderRadius: 16,
                  borderBottomRightRadius: isRight ? 5 : 16,
                  borderBottomLeftRadius: isRight ? 16 : 5,
                  backdropFilter: `blur(${p.blur}px)`,
                }}
              >
                <p className="text-[12.5px] leading-[1.6]" style={{ color: p.text }}>
                  {s.text}
                </p>
                <div className={`mt-1.5 flex items-center gap-2 text-[9.5px] ${isRight ? "justify-end" : ""}`} style={{ color: p.muted }}>
                  <span style={{ color }}>{scene.speakers[s.speaker]?.name}</span>
                  <span className="f-dm">{formatShort(s.at)}</span>
                </div>
              </div>
            </div>
          );
        })}

        {live && (
          <div className={`flex ${live.speaker === rightId ? "justify-end" : "justify-start"}`}>
            <div
              className="max-w-[86%] px-3.5 py-2.5"
              style={{
                background: `${p.accent}16`,
                border: `1px solid ${p.accent}33`,
                borderRadius: 16,
                borderBottomRightRadius: live.speaker === rightId ? 5 : 16,
                borderBottomLeftRadius: live.speaker === rightId ? 16 : 5,
                backdropFilter: `blur(${p.blur}px)`,
              }}
            >
              <p className="text-[12.5px] leading-[1.6]" style={{ color: p.text }}>
                <StreamText words={live.words} caretColor={p.accent} />
              </p>
              <div className="mt-1.5 flex items-center gap-2 text-[9.5px]" style={{ color: p.muted }}>
                <span className="flex gap-[3px]">
                  {[0, 1, 2].map((d) => (
                    <span
                      key={d}
                      className="anim-dot block h-[3px] w-[3px] rounded-full"
                      style={{ background: p.speaker[live.speaker], animationDelay: `${d * 220}ms` }}
                    />
                  ))}
                </span>
                <span style={{ color: p.speaker[live.speaker] }}>{scene.speakers[live.speaker]?.name} is speaking</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-1 text-[10.5px]" style={{ color: p.muted }}>
        <span>{segments.length} turns transcribed</span>
        <span className="flex items-center gap-1">
          <GhostButton onClick={onToggle} className="hover:bg-white/10" style={{ color: p.text }}>
            {paused ? <IconPlay size={11} /> : <IconPause size={11} />}
            {paused ? "resume" : "pause"}
          </GhostButton>
          <GhostButton onClick={onClear} className="hover:bg-white/10" title="Clear">
            <IconBroom size={12} />
          </GhostButton>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 08 ---
   Tideline — a shoreline timeline of the take.
------------------------------------------------------------------------- */
export function Timeline(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));

  return (
    <div className="flex h-full flex-col" style={{ fontFamily: scene.panelFont }}>
      <div className="anim-panel pb-4">
        <div className="flex items-end justify-between">
          <div>
            <span className="text-[9.5px] uppercase tracking-[0.3em]" style={{ color: p.muted }}>
              field take
            </span>
            <h2 className="mt-1.5 text-[14.5px] font-light leading-snug" style={{ color: p.text }}>
              {scene.session.title}
            </h2>
          </div>
          <span className="text-right">
            <span className="f-dm block text-[13px] tabular-nums" style={{ color: p.accent }}>
              {formatClock(elapsed)}
            </span>
            <span className="block text-[9.5px] uppercase tracking-[0.16em]" style={{ color: p.muted }}>
              {paused ? "on hold" : "rolling"}
            </span>
          </span>
        </div>
      </div>

      <div ref={scroller} className="scroll-quiet mask-fade-top relative flex-1 overflow-y-auto pl-1 pr-1">
        <div className="absolute bottom-0 left-[26px] top-1 w-[1px]" style={{ background: `linear-gradient(180deg, transparent, ${p.border} 8%, ${p.border} 92%, transparent)` }} aria-hidden />
        {segments.map((s, i) => {
          const color = p.speaker[s.speaker] ?? p.accent;
          const isLast = i === segments.length - 1;
          return (
            <div key={s.id} className="anim-seg relative grid grid-cols-[52px_1fr] gap-4 pb-4">
              <span className="f-dm pt-[1px] text-right text-[10px] tabular-nums" style={{ color: p.muted }}>
                {formatShort(s.at)}
              </span>
              <div className="relative">
                <span
                  className="absolute -left-[24px] top-[7px] h-[7px] w-[7px] rounded-full transition-all duration-500"
                  style={{ background: isLast ? color : p.surface, boxShadow: `0 0 0 2px ${isLast ? `${color}40` : p.border}` }}
                  aria-hidden
                />
                <span className="text-[9.5px] uppercase tracking-[0.2em]" style={{ color }}>
                  {scene.speakers[s.speaker]?.name}
                </span>
                <p className="mt-1 text-[12.5px] font-light leading-[1.65]" style={{ color: p.text, opacity: 0.92 }}>
                  {s.text}
                </p>
              </div>
            </div>
          );
        })}

        {live && (
          <div className="relative grid grid-cols-[52px_1fr] gap-4 pb-4">
            <span className="f-dm flex justify-end pt-[1px] text-[10px]" style={{ color: p.accent }}>
              <LiveDot color={p.accent} size={6} ring={false} active={!paused} />
            </span>
            <div className="relative">
              <span
                className="absolute -left-[24px] top-[7px] h-[7px] w-[7px] rounded-full"
                style={{ background: p.accent, boxShadow: `0 0 0 4px ${p.accent}26` }}
                aria-hidden
              />
              <span className="text-[9.5px] uppercase tracking-[0.2em]" style={{ color: p.speaker[live.speaker] }}>
                {scene.speakers[live.speaker]?.name}
              </span>
              <p className="mt-1 text-[12.5px] font-light leading-[1.65]" style={{ color: p.text }}>
                <StreamText words={live.words} caretColor={p.accent} />
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t pt-2.5 text-[10.5px]" style={{ borderColor: p.border, color: p.muted }}>
        <span className="f-dm">{wordsOf(segments)} words · {scene.session.device}</span>
        <span className="flex items-center gap-2">
          <button type="button" onClick={onToggle} className="transition-opacity hover:opacity-60">
            {paused ? "resume" : "hold"}
          </button>
          <button type="button" onClick={onClear} className="transition-opacity hover:opacity-60">
            reset
          </button>
          <button type="button" className="transition-opacity hover:opacity-60">
            export
          </button>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 09 ---
   Ember — chapters of short, warm chip-rows by the stove.
------------------------------------------------------------------------- */
export function Chips(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));
  const chapters: { label: string; items: typeof segments }[] = [];
  segments.forEach((s, i) => {
    const idx = Math.floor(i / 4);
    if (!chapters[idx]) chapters[idx] = { label: `chapter ${String(idx + 1).padStart(2, "0")}`, items: [] };
    chapters[idx].items.push(s);
  });

  return (
    <div className="flex h-full flex-col gap-3" style={{ fontFamily: scene.panelFont }}>
      <div className="anim-panel px-4 py-3.5" style={{ background: p.surface, border: `1px solid ${p.border}`, borderRadius: p.radius, backdropFilter: `blur(${p.blur}px)`, boxShadow: p.shadow }}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-[14px] font-medium" style={{ color: p.text }}>
              {scene.session.title}
            </h2>
            <p className="mt-1 text-[11px]" style={{ color: p.muted }}>
              {scene.session.note}
            </p>
          </div>
          <span
            className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[10px]"
            style={{ background: paused ? p.soft : `${p.accent}1f`, color: paused ? p.muted : p.accent }}
          >
            <LiveDot color={paused ? p.muted : p.accent} size={5} ring={false} active={!paused} />
            {paused ? "paused" : "live"}
          </span>
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-full px-3 py-1.5" style={{ background: p.soft, border: `1px solid ${p.border}` }}>
          <IconSearch size={12} className="shrink-0" />
          <span className="text-[10.5px]" style={{ color: p.muted }}>
            search this session…
          </span>
          <span className="f-dm ml-auto text-[10.5px] tabular-nums" style={{ color: p.muted }}>
            {formatClock(elapsed)}
          </span>
        </div>
      </div>

      <div ref={scroller} className="scroll-quiet flex-1 overflow-y-auto pr-1.5">
        {chapters.map((ch, ci) => (
          <div key={ch.label} className="mb-3">
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[9px] uppercase tracking-[0.24em]" style={{ color: p.muted }}>
                {ch.label}
              </span>
              <span className="h-[1px] flex-1" style={{ background: p.border }} />
              <span className="f-dm text-[9px] tabular-nums" style={{ color: p.muted }}>
                {formatShort(ch.items[0]?.at ?? 0)}
              </span>
            </div>
            <div className="space-y-1.5">
              {ch.items.map((s) => {
                const color = p.speaker[s.speaker] ?? p.accent;
                const isLast = ci === chapters.length - 1 && s.id === segments[segments.length - 1]?.id;
                return (
                  <div
                    key={s.id}
                    className="anim-seg flex items-start gap-2.5 px-3 py-2.5 transition-colors duration-500"
                    style={{
                      background: isLast ? p.soft : "transparent",
                      border: `1px solid ${isLast ? p.border : "transparent"}`,
                      borderLeft: `2px solid ${isLast ? p.accent : "transparent"}`,
                      borderRadius: p.radius - 6,
                    }}
                  >
                    <span
                      className="mt-[1px] shrink-0 rounded-full px-2 py-[2px] text-[9.5px] uppercase tracking-[0.1em]"
                      style={{ background: `${color}1c`, color }}
                    >
                      {scene.speakers[s.speaker]?.name}
                    </span>
                    <p className="text-[12.5px] leading-[1.6]" style={{ color: p.text }}>
                      {s.text}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {live && (
          <div className="mb-3">
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[9px] uppercase tracking-[0.24em]" style={{ color: p.accent }}>
                speaking now
              </span>
              <span className="h-[1px] flex-1" style={{ background: `${p.accent}40` }} />
            </div>
            <div
              className="flex items-start gap-2.5 px-3 py-2.5"
              style={{ background: `${p.accent}12`, border: `1px solid ${p.accent}2e`, borderRadius: p.radius - 6 }}
            >
              <span
                className="mt-[1px] shrink-0 rounded-full px-2 py-[2px] text-[9.5px] uppercase tracking-[0.1em]"
                style={{ background: `${p.speaker[live.speaker]}1c`, color: p.speaker[live.speaker] }}
              >
                {scene.speakers[live.speaker]?.name}
              </span>
              <p className="text-[12.5px] leading-[1.6]" style={{ color: p.text }}>
                <StreamText words={live.words} caretColor={p.accent} />
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-1" style={{ color: p.muted }}>
        <span className="flex items-center gap-3 text-[10px]">
          <span>{wordsOf(segments)} words</span>
          <LevelMeter bars={8} active={!paused} color={p.accent} height={10} width={2} />
        </span>
        <span className="flex items-center gap-1">
          <GhostButton onClick={onToggle} className="hover:bg-white/10" style={{ color: p.text }}>
            {paused ? <IconPlay size={11} /> : <IconPause size={11} />}
            {paused ? "resume" : "hold"}
          </GhostButton>
          <GhostButton onClick={onClear} className="hover:bg-white/10" title="Clear">
            <IconBroom size={12} />
          </GhostButton>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 10 ---
   Field Notes — a light page with a margin gutter, morning after the storm.
------------------------------------------------------------------------- */
export function Gutter(props: PanelProps) {
  const { scene, segments, live, paused, elapsed, onToggle, onClear } = props;
  const p = scene.panel;
  const scroller = useAutoScroll<HTMLDivElement>(segments.length + (live?.words.length ?? 0));

  return (
    <div
      className="anim-panel flex h-full flex-col overflow-hidden"
      style={{ background: p.surface, border: `1px solid ${p.border}`, borderRadius: p.radius, boxShadow: p.shadow, color: p.text }}
    >
      <div className="border-b px-5 pb-4 pt-4" style={{ borderColor: p.border }}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <span className="f-dm text-[9.5px] uppercase tracking-[0.26em]" style={{ color: p.accent }}>
              notes · {scene.hour}
            </span>
            <h2 className="mt-1.5 text-[19px] leading-tight" style={{ color: p.text, fontFamily: scene.panelFont }}>
              {scene.session.title}
            </h2>
            <p className="f-dm mt-1 text-[10.5px]" style={{ color: p.muted }}>
              {scene.session.note} · {paused ? "paused" : formatClock(elapsed)}
            </p>
          </div>
          <span className="f-dm flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[9.5px] uppercase tracking-[0.14em]" style={{ background: p.soft, color: p.accent }}>
            <LiveDot color={p.accent} size={5} ring={false} active={!paused} />
            {paused ? "held" : "rec"}
          </span>
        </div>
      </div>

      <div ref={scroller} className="scroll-light scroll-quiet mask-fade-top flex-1 overflow-y-auto px-4 py-3">
        {segments.map((s) => {
          const color = p.speaker[s.speaker] ?? p.accent;
          return (
            <div
              key={s.id}
              className="anim-seg grid grid-cols-[54px_1fr] gap-4 rounded-xl px-1 py-3 transition-colors duration-500"
              style={{ borderBottom: `1px solid ${p.border}` }}
            >
              <div className="flex flex-col items-start gap-1.5">
                <span className="f-dm text-[10px] tabular-nums" style={{ color: p.muted }}>
                  {formatShort(s.at)}
                </span>
                <span
                  className="grid h-6 w-6 place-items-center rounded-full text-[9px] font-medium"
                  style={{ background: `${color}22`, color }}
                >
                  {initials(scene.speakers[s.speaker]?.name ?? "?")}
                </span>
              </div>
              <div>
                <span className="f-dm text-[9.5px] uppercase tracking-[0.2em]" style={{ color }}>
                  {scene.speakers[s.speaker]?.name} · {scene.speakers[s.speaker]?.role}
                </span>
                <p className="mt-1.5 text-[13.5px] leading-[1.62]" style={{ color: p.text, fontFamily: scene.panelFont }}>
                  {s.text}
                </p>
              </div>
            </div>
          );
        })}

        {live && (
          <div
            className="grid grid-cols-[54px_1fr] gap-4 rounded-xl px-1 py-3"
            style={{ background: p.soft, borderBottom: `1px solid ${p.border}` }}
          >
            <div className="flex flex-col items-start gap-1.5">
              <span className="f-dm text-[10px]" style={{ color: p.accent }}>
                now
              </span>
              <span
                className="grid h-6 w-6 place-items-center rounded-full text-[9px] font-medium"
                style={{ background: `${p.speaker[live.speaker]}22`, color: p.speaker[live.speaker] }}
              >
                {initials(scene.speakers[live.speaker]?.name ?? "?")}
              </span>
            </div>
            <div>
              <span className="f-dm text-[9.5px] uppercase tracking-[0.2em]" style={{ color: p.speaker[live.speaker] }}>
                {scene.speakers[live.speaker]?.name} · speaking
              </span>
              <p className="mt-1.5 text-[13.5px] leading-[1.62]" style={{ color: p.text, fontFamily: scene.panelFont }}>
                <StreamText words={live.words} caretColor={p.accent} />
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t px-5 py-3 text-[10.5px]" style={{ borderColor: p.border, color: p.muted }}>
        <span className="f-dm">auto-saved · {wordsOf(segments)} words</span>
        <span className="flex items-center gap-3">
          <button type="button" onClick={onToggle} className="uppercase tracking-[0.14em] transition-opacity hover:opacity-60">
            {paused ? "resume" : "pause"}
          </button>
          <button type="button" onClick={onClear} className="uppercase tracking-[0.14em] transition-opacity hover:opacity-60">
            new sheet
          </button>
          <button type="button" className="uppercase tracking-[0.14em] transition-opacity hover:opacity-60">
            export
          </button>
        </span>
      </div>
    </div>
  );
}

export const panelSetB = {
  feed: Feed,
  bubbles: Bubbles,
  timeline: Timeline,
  chips: Chips,
  gutter: Gutter,
};
