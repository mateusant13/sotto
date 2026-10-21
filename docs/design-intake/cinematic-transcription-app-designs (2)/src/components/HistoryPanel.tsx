import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { fmtClock } from "../hooks/useTranscription";
import type { Entry, Partial } from "../hooks/useTranscription";
import type { Theme } from "../themes";
import { SPEAKER_INITIALS, speakerShort } from "../lib/scripts";

export interface PanelProps {
  theme: Theme;
  entries: Entry[];
  partial: Partial | null;
  running: boolean;
  speakerColor: (name: string) => string;
  onClear: () => void;
  onExport: () => void;
  autoScroll: boolean;
  setAutoScroll: (v: boolean) => void;
  sessionLabel: string;
  wpm: number;
  onCollapse: () => void;
}

function Highlight({ text, query, color }: { text: string; query: string; color: string }) {
  if (!query.trim()) return <>{text}</>;
  const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
  return (
    <>
      {parts.map((p, i) =>
        p.toLowerCase() === query.toLowerCase() ? (
          <mark
            key={i}
            style={{ background: `color-mix(in srgb, ${color} 30%, transparent)`, color: "inherit", borderRadius: 3, padding: "0 1px" }}
          >
            {p}
          </mark>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

export default function HistoryPanel(props: PanelProps) {
  const { theme, entries, partial, running, speakerColor, onClear, onExport, autoScroll, setAutoScroll, onCollapse } = props;
  const { panel, fonts, time24 } = theme;
  const [query, setQuery] = useState("");
  const [speaker, setSpeaker] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  const speakers = useMemo(() => [...new Set(entries.map((e) => e.speaker))], [entries]);

  const filtered = useMemo(
    () =>
      entries.filter(
        (e) =>
          (!speaker || e.speaker === speaker) &&
          (!query.trim() || e.text.toLowerCase().includes(query.toLowerCase())),
      ),
    [entries, query, speaker],
  );

  const grouped = useMemo(() => {
    const out: { session: string; items: Entry[] }[] = [];
    for (const e of filtered) {
      const last = out[out.length - 1];
      if (last && last.session === e.session) last.items.push(e);
      else out.push({ session: e.session, items: [e] });
    }
    return out;
  }, [filtered]);

  useEffect(() => {
    if (!autoScroll || query.trim() || speaker) return;
    const el = scroller.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [entries.length, partial?.revealed, autoScroll, query, speaker]);

  const copy = (id: string, text: string) => {
    navigator.clipboard?.writeText(text);
    setCopied(id);
    window.setTimeout(() => setCopied((c) => (c === id ? null : c)), 1300);
  };

  const varStyle: CSSProperties =
    panel.style === "rail" || panel.style === "cards"
      ? { background: "var(--surface)", backdropFilter: "blur(var(--blur))", WebkitBackdropFilter: "blur(var(--blur))", border: "1px solid var(--line)", borderRadius: "var(--radius)", boxShadow: "var(--shadow)" }
      : { background: "var(--surface)", backdropFilter: "blur(var(--blur))", WebkitBackdropFilter: "blur(var(--blur))", borderLeft: "1px solid var(--line)", boxShadow: "var(--shadow)" };

  const tagStyle: CSSProperties = { fontSize: "0.6rem", letterSpacing: "0.22em", textTransform: "uppercase" };
  const timeStyle: CSSProperties = {
    fontFamily: panel.style === "memo" ? "ui-monospace, SFMono-Regular, Menlo, monospace" : fonts.ui,
    fontSize: "0.655rem",
    letterSpacing: "0.06em",
    color: "color-mix(in srgb, var(--dim) 130%, transparent)",
  };

  const Header = (
    <div className="px-5 pt-5 pb-3" style={{ borderBottom: `1px solid var(--line)` }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: running ? "var(--live)" : "var(--dim)" }}
            />
            <span className="uppercase" style={{ ...tagStyle, color: "var(--dim)" }}>
              transcript history
            </span>
          </div>
          <h2
            className="mt-1.5"
            style={{
              fontFamily: panel.style === "memo" ? "ui-monospace, Menlo, monospace" : fonts.display,
              fontSize: panel.style === "list" || panel.style === "memo" ? "1.05rem" : "1.2rem",
              fontWeight: 400,
              letterSpacing: panel.style === "memo" ? "0.12em" : "-0.01em",
              color: "var(--text)",
              textTransform: panel.style === "memo" ? "uppercase" : "none",
            }}
          >
            {panel.style === "memo" ? "session log" : "The room, so far"}
          </h2>
        </div>
        <button
          onClick={onCollapse}
          title="Hide panel (H)"
          className="rounded-full px-2 py-1 transition-opacity hover:opacity-100"
          style={{ fontSize: "0.6rem", letterSpacing: "0.16em", color: "var(--dim)", border: "1px solid var(--line)", opacity: 0.85 }}
        >
          HIDE
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search this transcript…"
          className="w-full bg-transparent outline-none"
          style={{
            fontFamily: fonts.ui,
            fontSize: "0.76rem",
            color: "var(--text)",
            padding: panel.style === "list" || panel.style === "cards" ? "0.55rem 0.85rem" : "0.45rem 0",
            borderRadius: panel.style === "list" || panel.style === "cards" ? "999px" : 0,
            border: panel.style === "list" || panel.style === "cards" ? "1px solid var(--line)" : "none",
            borderBottom: panel.style === "list" || panel.style === "cards" ? undefined : "1px solid var(--line)",
            background: panel.style === "list" || panel.style === "cards" ? "var(--surface-2)" : "transparent",
          }}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {["All", ...speakers].map((s) => {
          const active = s === "All" ? speaker === null : speaker === s;
          const tone = s === "All" ? "var(--text)" : speakerColor(s);
          return (
            <button
              key={s}
              onClick={() => setSpeaker(s === "All" ? null : s)}
              className="rounded-full px-2.5 py-1 transition-colors"
              style={{
                fontFamily: fonts.ui,
                fontSize: "0.6rem",
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color: active ? tone : "color-mix(in srgb, var(--dim) 105%, transparent)",
                background: active ? `color-mix(in srgb, ${tone} 16%, transparent)` : "transparent",
                border: `1px solid ${active ? `color-mix(in srgb, ${tone} 38%, transparent)` : "var(--line)"}`,
                borderRadius: panel.style === "memo" ? 3 : 999,
              }}
            >
              {s === "All" ? "everyone" : speakerShort(s)}
            </button>
          );
        })}
      </div>
    </div>
  );

  const Row = ({ e, index }: { e: Entry; index: number }) => {
    const tone = speakerColor(e.speaker);
    const active = copied === e.id;
    const onCopy = () => copy(e.id, e.text);
    const common = { onClick: onCopy, title: active ? "Copied" : "Copy line" };

    if (panel.style === "sheet") {
      return (
        <div
          {...common}
          className="group grid cursor-pointer grid-cols-[74px_1fr] gap-3 px-5 py-3 transition-colors"
          style={{ borderBottom: `1px solid color-mix(in srgb, var(--line) 60%, transparent)` }}
          onMouseEnter={(ev) => (ev.currentTarget.style.background = "var(--surface-2)")}
          onMouseLeave={(ev) => (ev.currentTarget.style.background = "transparent")}
        >
          <span style={{ ...timeStyle, paddingTop: 2 }}>{fmtClock(e.at, time24)}</span>
          <div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: tone }} />
              <span style={{ ...tagStyle, color: tone }}>{speakerShort(e.speaker)}</span>
            </div>
            <p className="mt-1" style={{ fontFamily: fonts.caption, fontSize: "0.85rem", lineHeight: 1.55, color: "var(--text)" }}>
              <Highlight text={e.text} query={query} color={tone} />
            </p>
          </div>
        </div>
      );
    }

    if (panel.style === "rail") {
      return (
        <div {...common} className="group relative cursor-pointer pl-7 pr-4 py-2.5">
          <span className="absolute left-[18px] top-0 bottom-0 w-px" style={{ background: "color-mix(in srgb, var(--line) 70%, transparent)" }} />
          <span
            className="absolute left-[14px] top-[17px] h-[9px] w-[9px] rounded-full"
            style={{ background: groupDotBg(tone), border: `2px solid color-mix(in srgb, var(--surface) 100%, transparent)`, boxShadow: `0 0 0 1px ${tone}` }}
          />
          <div className="flex items-baseline gap-2.5">
            <span style={{ ...tagStyle, color: tone }}>{speakerShort(e.speaker)}</span>
            <span style={timeStyle}>{fmtClock(e.at, time24)}</span>
            <span className="ml-auto text-[0.6rem]" style={{ color: "var(--dim)", opacity: active ? 1 : 0 }}>
              copied
            </span>
          </div>
          <p className="mt-1" style={{ fontFamily: fonts.caption, fontSize: "0.84rem", lineHeight: 1.55, color: "var(--text)" }}>
            <Highlight text={e.text} query={query} color={tone} />
          </p>
        </div>
      );
    }

    if (panel.style === "list") {
      return (
        <div
          {...common}
          className="group flex cursor-pointer items-start gap-3.5 px-5 py-3.5 transition-colors"
          onMouseEnter={(ev) => (ev.currentTarget.style.background = "var(--surface-2)")}
          onMouseLeave={(ev) => (ev.currentTarget.style.background = "transparent")}
        >
          <span
            className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
            style={{ background: `color-mix(in srgb, ${tone} 18%, transparent)`, color: tone, fontSize: "0.58rem", letterSpacing: "0.06em", fontFamily: fonts.ui }}
          >
            {SPEAKER_INITIALS[e.speaker] ?? speakerShort(e.speaker).slice(0, 2).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-3">
              <span style={{ fontFamily: fonts.ui, fontSize: "0.74rem", color: tone, letterSpacing: "0.02em" }}>
                {speakerShort(e.speaker)}
              </span>
              <span style={timeStyle}>{active ? "copied" : fmtClock(e.at, time24)}</span>
            </div>
            <p className="mt-1" style={{ fontFamily: fonts.caption, fontSize: "0.85rem", lineHeight: 1.55, color: "var(--text)" }}>
              <Highlight text={e.text} query={query} color={tone} />
            </p>
          </div>
        </div>
      );
    }

    if (panel.style === "memo") {
      return (
        <div {...common} className="group cursor-pointer px-5 py-2.5">
          <div
            className="flex items-baseline gap-3"
            style={{ fontFamily: "ui-monospace, Menlo, monospace", fontSize: "0.63rem", letterSpacing: "0.08em", color: "var(--dim)" }}
          >
            <span>{String(index + 1).padStart(3, "0")}</span>
            <span>{fmtClock(e.at, true)}</span>
            <span style={{ color: tone, textTransform: "uppercase", letterSpacing: "0.16em" }}>{speakerShort(e.speaker)}</span>
            <span className="ml-auto">{active ? "copied ✓" : `${(e.confidence * 100).toFixed(0)}%`}</span>
          </div>
          <p
            className="mt-1.5"
            style={{ fontFamily: fonts.caption, fontSize: "0.85rem", lineHeight: 1.58, color: "var(--text)" }}
          >
            <Highlight text={e.text} query={query} color={tone} />
          </p>
        </div>
      );
    }

    /* cards */
    return (
      <div
        {...common}
        className="mx-4 mb-2.5 cursor-pointer px-4 py-3.5 transition-transform"
        style={{
          background: "var(--surface-2)",
          border: "1px solid var(--line)",
          borderLeft: `3px solid ${tone}`,
          borderRadius: "calc(var(--radius) * 0.8)",
          boxShadow: "0 12px 26px -22px rgba(0,0,0,.7)",
        }}
        onMouseEnter={(ev) => (ev.currentTarget.style.transform = "translateY(-1px)")}
        onMouseLeave={(ev) => (ev.currentTarget.style.transform = "translateY(0)")}
      >
        <div className="flex items-center justify-between gap-3">
          <span className="uppercase" style={{ ...tagStyle, color: tone }}>
            {speakerShort(e.speaker)}
          </span>
          <span style={timeStyle}>{active ? "copied ✓" : fmtClock(e.at, time24)}</span>
        </div>
        <p className="mt-1.5" style={{ fontFamily: fonts.caption, fontSize: "0.85rem", lineHeight: 1.55, color: "var(--text)" }}>
          <Highlight text={e.text} query={query} color={tone} />
        </p>
      </div>
    );
  };

  const LiveRow = partial ? (
    <div
      className="relative"
      style={{
        background: panel.style === "cards" ? "var(--surface-2)" : "color-mix(in srgb, var(--accent) 9%, transparent)",
        borderLeft: panel.style === "rail" ? undefined : `2px solid ${speakerColor(partial.speaker)}`,
        borderRadius: panel.style === "cards" ? "calc(var(--radius) * 0.8)" : 0,
        margin: panel.style === "cards" ? "0 16px 14px" : undefined,
        padding: panel.style === "cards" ? "12px 14px" : "12px 20px 14px",
      }}
    >
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full breathe" style={{ background: "var(--live)" }} />
        <span style={{ ...tagStyle, color: speakerColor(partial.speaker) }}>{speakerShort(partial.speaker)}</span>
        <span className="ml-auto" style={{ ...tagStyle, color: "var(--dim)", letterSpacing: "0.18em" }}>
          in progress
        </span>
      </div>
      <p
        className="mt-1"
        style={{ fontFamily: fonts.caption, fontSize: "0.85rem", lineHeight: 1.55, color: "var(--text)", fontStyle: "italic" }}
      >
        {partial.words.slice(0, partial.revealed).join(" ")}
        <span className="caret ml-0.5 inline-block" style={{ width: 1.5, height: "0.85em", background: "var(--accent)", verticalAlign: "baseline" }} />
      </p>
    </div>
  ) : null;

  const Footer = (
    <div className="shrink-0 px-5 py-3.5" style={{ borderTop: `1px solid var(--line)` }}>
      <div className="flex items-center justify-between gap-2">
        <button
          onClick={onExport}
          className="transition-opacity hover:opacity-70"
          style={{ fontFamily: fonts.ui, fontSize: "0.63rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--text)" }}
        >
          Export .txt
        </button>
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className="transition-opacity hover:opacity-70"
          style={{
            fontFamily: fonts.ui,
            fontSize: "0.63rem",
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: autoScroll ? "var(--accent)" : "var(--dim)",
          }}
        >
          Follow {autoScroll ? "on" : "off"}
        </button>
        <button
          onClick={onClear}
          className="transition-opacity hover:opacity-70"
          style={{ fontFamily: fonts.ui, fontSize: "0.63rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--dim)" }}
        >
          Clear
        </button>
      </div>
      <div
        className="mt-2 flex items-center justify-between"
        style={{ fontFamily: fonts.ui, fontSize: "0.6rem", letterSpacing: "0.1em", color: "var(--dim)" }}
      >
        <span>{props.sessionLabel}</span>
        <span>
          {entries.length} lines · {props.wpm} wpm
        </span>
      </div>
    </div>
  );

  return (
    <aside
      className={`absolute z-20 flex flex-col overflow-hidden ${
        panel.style === "rail" || panel.style === "cards" ? "right-3 top-3 bottom-3" : "right-0 top-0 bottom-0"
      }`}
      style={{ width: panel.width, maxWidth: "calc(100vw - 48px)", ...varStyle }}
    >
      {Header}
      <div ref={scroller} className="quiet-scroll min-h-0 flex-1 overflow-y-auto">
        {grouped.length === 0 && (
          <div className="px-5 py-10 text-center" style={{ color: "var(--dim)", fontFamily: fonts.ui, fontSize: "0.78rem", lineHeight: 1.7 }}>
            Nothing matches that. The room keeps talking either way.
          </div>
        )}
        {grouped.map((group) => (
          <div key={group.session + group.items[0]?.id}>
            <div
              className="sticky top-0 z-10 flex items-center gap-2 px-5 py-2"
              style={{
                background: "color-mix(in srgb, var(--surface) 92%, transparent)",
                backdropFilter: "blur(8px)",
                borderBottom: `1px solid color-mix(in srgb, var(--line) 60%, transparent)`,
              }}
            >
              <span style={{ fontFamily: fonts.ui, fontSize: "0.58rem", letterSpacing: "0.26em", textTransform: "uppercase", color: "var(--dim)" }}>
                {group.session}
              </span>
              <span className="h-px flex-1" style={{ background: "color-mix(in srgb, var(--line) 70%, transparent)" }} />
              <span style={{ fontFamily: fonts.ui, fontSize: "0.58rem", color: "var(--dim)" }}>{group.items.length}</span>
            </div>
            {group.items.map((e, i) => (
              <Row key={e.id} e={e} index={i} />
            ))}
          </div>
        ))}
        {LiveRow}
        <div className="h-2" />
      </div>
      {Footer}
    </aside>
  );
}

const groupDotBg = (tone: string) => `color-mix(in srgb, ${tone} 90%, transparent)`;
