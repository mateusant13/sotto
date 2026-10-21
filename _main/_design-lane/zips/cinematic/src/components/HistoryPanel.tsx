import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "../utils/cn";
import type { CommittedLine, Session } from "../data";
import { wordCount } from "../data";

interface HistoryPanelProps {
  sessions: Session[];
  activeSession: Session;
  committed: CommittedLine[];
  open: boolean;
  playing: boolean;
  onClose: () => void;
  onReplay: (id: string) => void;
  onCopy: (s: Session) => void;
  reduced: boolean;
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 12 12"
      fill="none"
      aria-hidden="true"
      className={cn("transition-transform duration-300", open && "rotate-180")}
    >
      <path d="m2.5 4.5 3.5 3.5 3.5-3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <circle cx="6" cy="6" r="4.2" stroke="currentColor" strokeWidth="1.3" />
      <path d="m9.5 9.5 3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg width="9" height="10" viewBox="0 0 9 10" fill="none" aria-hidden="true">
      <path d="M1 1.2v7.6c0 .5.55.8.98.55l6.1-3.8a.65.65 0 0 0 0-1.1L1.98.65A.65.65 0 0 0 1 1.2Z" fill="currentColor" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.4" stroke="currentColor" strokeWidth="1.2" />
      <path d="M8.5 3.5v-1A1.5 1.5 0 0 0 7 1H2.5A1.5 1.5 0 0 0 1 2.5V7a1.5 1.5 0 0 0 1.5 1.5h1" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function HistoryPanel({
  sessions,
  activeSession,
  committed,
  open,
  playing,
  onClose,
  onReplay,
  onCopy,
  reduced,
}: HistoryPanelProps) {
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const liveRef = useRef<HTMLDivElement>(null);

  // keep the live transcript pinned to its newest line
  useEffect(() => {
    const el = liveRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: reduced ? "auto" : "smooth" });
  }, [committed.length, reduced]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.tag.toLowerCase().includes(q) ||
        s.lines.some((l) => l.text.toLowerCase().includes(q))
    );
  }, [sessions, query]);

  return (
    <aside
      className={cn(
        "fixed top-0 right-0 z-30 h-full w-[min(92vw,360px)] border-l border-[var(--line)] bg-[var(--panel)] backdrop-blur-2xl transition-transform duration-500 ease-[cubic-bezier(0.2,0.7,0.3,1)]",
        !open && "translate-x-full"
      )}
      aria-label="Transcript history"
      aria-hidden={!open}
    >
      <div className="flex h-full flex-col">
        {/* header */}
        <div className="border-b border-[var(--line)] px-5 pt-5 pb-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="font-display text-[22px] leading-none font-medium text-[var(--ink)] italic">
                Transcripts
              </h2>
              <p className="mt-2 font-mono text-[8.5px] tracking-[0.3em] text-[var(--dim)] uppercase">
                everything the night said
              </p>
            </div>
            <button
              onClick={onClose}
              aria-label="Hide history panel"
              className="grid h-8 w-8 place-items-center rounded-full border border-[var(--line)] text-[var(--dim)] transition-all hover:border-[var(--accent)] hover:text-[var(--ink)] active:scale-90"
            >
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <path d="m4.5 2.5 3.5 3.5-3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>

        {/* live block */}
        <div className="border-b border-[var(--line)] px-5 py-4">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full bg-[var(--accent)]",
                  playing ? "pulse-dot" : "opacity-40"
                )}
              />
              <span className="font-mono text-[9px] tracking-[0.28em] text-[var(--accent)] uppercase">
                Now transcribing
              </span>
            </span>
            <span className="font-mono text-[9px] tracking-[0.14em] text-[var(--faint)] uppercase">
              {committed.length}/{activeSession.lines.length} lines
            </span>
          </div>

          <div className="mt-2.5 flex items-center gap-2">
            <h3 className="truncate font-display text-[15px] font-medium text-[var(--ink)]">
              {activeSession.title}
            </h3>
            <span className="shrink-0 rounded-full border border-[var(--line)] px-2 py-[2px] font-mono text-[8.5px] tracking-[0.16em] text-[var(--dim)] uppercase">
              {activeSession.tag}
            </span>
          </div>

          <div
            ref={liveRef}
            className="panel-scroll mt-3 flex max-h-[26vh] flex-col gap-2.5 overflow-y-auto pr-1"
          >
            {committed.length === 0 && (
              <p className="flex items-center py-2 text-[12px] text-[var(--dim)]">
                <span className="listening-dots mr-2.5 text-[var(--accent)]">
                  <span />
                  <span />
                  <span />
                </span>
                Listening… captions land here as they're spoken.
              </p>
            )}
            {committed.map((c, i) => (
              <div key={i} className="item-in text-[12.5px] leading-snug">
                <span className="mr-2 font-mono text-[9.5px] text-[var(--faint)] tabular-nums">
                  {c.t}
                </span>
                {c.speaker && (
                  <span className="mr-1.5 font-mono text-[9.5px] tracking-[0.08em] text-[var(--accent)] uppercase">
                    {c.speaker}
                  </span>
                )}
                <span
                  className={cn(
                    "transition-colors duration-500",
                    i === committed.length - 1 ? "text-[var(--ink)]" : "text-[var(--dim)]"
                  )}
                >
                  {c.text}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* library */}
        <div className="panel-scroll flex-1 overflow-y-auto px-5 py-4">
          <label className="flex items-center gap-2.5 rounded-lg border border-[var(--line)] bg-[var(--panel-2)] px-3 py-2 transition-colors focus-within:border-[var(--accent)]">
            <span className="text-[var(--faint)]">
              <SearchIcon />
            </span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search the night…"
              className="w-full bg-transparent text-[13px] text-[var(--ink)] outline-none placeholder:text-[var(--faint)]"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                aria-label="Clear search"
                className="text-[var(--faint)] hover:text-[var(--ink)]"
              >
                <svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true">
                  <path d="m1.5 1.5 7 7m0-7-7 7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                </svg>
              </button>
            )}
          </label>

          <p className="mt-4 mb-2 font-mono text-[8.5px] tracking-[0.3em] text-[var(--faint)] uppercase">
            Library · {filtered.length}
          </p>

          {filtered.length === 0 && (
            <p className="py-6 text-center text-[12px] text-[var(--dim)] italic">
              Nothing matches “{query}” — the night keeps its secrets.
            </p>
          )}

          <div className="flex flex-col gap-1.5">
            {filtered.map((s, idx) => {
              const isActive = s.id === activeSession.id;
              const isOpen = expanded === s.id;
              return (
                <div
                  key={s.id}
                  className={cn(
                    "item-in group relative rounded-lg border transition-all duration-300",
                    isActive
                      ? "border-[var(--line)] bg-[var(--panel-2)]"
                      : "border-transparent hover:border-[var(--line)] hover:bg-[var(--hover)]"
                  )}
                  style={{ animationDelay: reduced ? undefined : `${idx * 45}ms` }}
                >
                  {isActive && (
                    <span className="absolute top-3 bottom-3 left-0 w-[2px] rounded-full bg-[var(--accent)]" />
                  )}
                  <button
                    onClick={() => setExpanded(isOpen ? null : s.id)}
                    className="flex w-full items-start justify-between gap-2 p-3 text-left"
                    aria-expanded={isOpen}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-display text-[14.5px] leading-snug font-medium text-[var(--ink)]">
                        {s.title}
                      </span>
                      <span className="mt-1 block font-mono text-[9.5px] tracking-[0.06em] text-[var(--dim)]">
                        {s.date} · {s.duration} · {wordCount(s)} words
                      </span>
                    </span>
                    <span className="mt-1 flex shrink-0 items-center gap-1.5">
                      {isActive && (
                        <span className="eq h-[10px] text-[var(--accent)]" aria-hidden="true">
                          <span /><span /><span /><span /><span />
                        </span>
                      )}
                      <span className="text-[var(--faint)]">
                        <Chevron open={isOpen} />
                      </span>
                    </span>
                  </button>

                  {isOpen && (
                    <div className="item-in border-t border-[var(--line)] px-3 pt-2.5 pb-3">
                      {s.lines.slice(0, 2).map((l, i) => (
                        <p key={i} className="truncate text-[11.5px] text-[var(--dim)] italic">
                          {l.speaker && <span className="mr-1 not-italic text-[var(--accent)]">{l.speaker}:</span>}
                          “{l.text}”
                        </p>
                      ))}
                      <div className="mt-2.5 flex items-center gap-2">
                        <button
                          onClick={() => onReplay(s.id)}
                          className={cn(
                            "flex items-center gap-1.5 rounded-full border px-3 py-1.5 font-mono text-[9.5px] tracking-[0.14em] uppercase transition-all active:scale-95",
                            isActive
                              ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-ink)]"
                              : "border-[var(--accent)] text-[var(--accent)] hover:bg-[var(--hover)]"
                          )}
                        >
                          <PlayIcon /> {isActive ? "Restart" : "Replay live"}
                        </button>
                        <button
                          onClick={() => onCopy(s)}
                          className="flex items-center gap-1.5 rounded-full border border-[var(--line)] px-3 py-1.5 font-mono text-[9.5px] tracking-[0.14em] text-[var(--dim)] uppercase transition-all hover:border-[var(--accent)] hover:text-[var(--ink)] active:scale-95"
                        >
                          <CopyIcon /> Copy
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* footer */}
        <div className="flex items-center justify-between border-t border-[var(--line)] px-5 py-3">
          <span className="flex items-center gap-1.5 font-mono text-[8.5px] tracking-[0.2em] text-[var(--faint)] uppercase">
            <span className="h-1 w-1 rounded-full bg-[var(--accent)] opacity-70" />
            synced · just now
          </span>
          <span className="font-mono text-[8.5px] tracking-[0.2em] text-[var(--faint)] uppercase">
            {sessions.length} sessions tonight
          </span>
        </div>
      </div>
    </aside>
  );
}
