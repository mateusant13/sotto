import type { Scene } from "@/data/scenes";
import { cn } from "@/utils/cn";

export function DesignSwitcher({
  scenes,
  index,
  onSelect,
  open,
  onToggle,
}: {
  scenes: Scene[];
  index: number;
  onSelect: (i: number) => void;
  open: boolean;
  onToggle: () => void;
}) {
  const active = scenes[index];

  return (
    <div className="anim-chrome pointer-events-auto absolute left-7 top-[240px] z-30 w-[272px]">
      <button
        type="button"
        onClick={onToggle}
        className="group flex w-full items-center gap-2 rounded-full px-3 py-2 text-left transition-all duration-500 hover:translate-y-[-1px]"
        style={{
          background: "rgba(10,11,14,0.62)",
          border: "1px solid rgba(255,255,255,0.09)",
          backdropFilter: "blur(18px)",
          WebkitBackdropFilter: "blur(18px)",
          boxShadow: "0 20px 50px -30px rgba(0,0,0,0.8)",
        }}
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="rgba(240,238,232,0.72)" strokeWidth="1.5" strokeLinecap="round">
          <path d="M4 4h16v16H4z" opacity="0.45" />
          <path d="M14 4v16" />
        </svg>
        <span className="text-[10px] uppercase tracking-[0.26em]" style={{ color: "rgba(240,238,232,0.62)" }}>
          designs
        </span>
        <span className="f-dm ml-auto text-[10px] tabular-nums" style={{ color: "rgba(240,238,232,0.5)" }}>
          {String(index + 1).padStart(2, "0")}/{String(scenes.length).padStart(2, "0")}
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="rgba(240,238,232,0.7)"
          strokeWidth="1.6"
          strokeLinecap="round"
          style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 400ms ease" }}
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      <div
        className="mt-2 overflow-hidden"
        style={{
          maxHeight: open ? "max(184px, calc(100vh - 590px))" : 0,
          opacity: open ? 1 : 0,
          transition: "max-height 520ms cubic-bezier(0.22,0.68,0.2,1), opacity 380ms ease",
          background: open ? "rgba(10,11,14,0.68)" : "transparent",
          border: open ? "1px solid rgba(255,255,255,0.08)" : "1px solid transparent",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          borderRadius: 18,
          boxShadow: open ? "0 30px 70px -34px rgba(0,0,0,0.9)" : "none",
        }}
      >
        <div
          className="scroll-quiet overflow-y-auto p-1.5"
          style={{ maxHeight: open ? "max(146px, calc(100vh - 628px))" : 0 }}
        >
          {scenes.map((s, i) => {
            const isActive = i === index;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => onSelect(i)}
                className={cn(
                  "group flex w-full items-center gap-2.5 rounded-[13px] px-2.5 py-2 text-left transition-all duration-400",
                  !isActive && "hover:translate-x-[2px] hover:bg-white/[0.05]",
                )}
                style={{ background: isActive ? "rgba(255,255,255,0.07)" : "transparent" }}
              >
                <span className="f-dm w-[16px] shrink-0 text-[10px] tabular-nums" style={{ color: "rgba(240,238,232,0.42)" }}>
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  className="relative h-[26px] w-[38px] shrink-0 overflow-hidden rounded-[6px] transition-all duration-500"
                  style={{
                    outline: `1px solid ${isActive ? `${s.swatch[0]}90` : "rgba(255,255,255,0.12)"}`,
                    opacity: isActive ? 1 : 0.62,
                    boxShadow: isActive ? `0 4px 16px -6px ${s.swatch[0]}90` : "none",
                  }}
                >
                  <img
                    src={s.wallpaper.replace("h=900&w=1600", "h=160&w=240")}
                    alt=""
                    aria-hidden
                    loading="lazy"
                    className="h-full w-full object-cover"
                    style={{ filter: s.wallFilter }}
                  />
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className="block truncate text-[12px] leading-tight"
                    style={{ color: isActive ? "#F4F2EE" : "rgba(240,238,232,0.78)" }}
                  >
                    {s.name}
                  </span>
                  <span className="mt-[2px] block truncate text-[10px] leading-tight" style={{ color: "rgba(240,238,232,0.44)" }}>
                    {s.mood}
                  </span>
                </span>
                <span
                  className="h-4 w-4 shrink-0 rounded-full opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                  style={{ background: `linear-gradient(135deg, ${s.swatch[0]}, ${s.swatch[1]})`, opacity: isActive ? 1 : undefined }}
                />
              </button>
            );
          })}
        </div>
        <div
          className="flex items-center justify-between border-t px-3.5 py-2.5 text-[9.5px] uppercase tracking-[0.2em]"
          style={{ borderColor: "rgba(255,255,255,0.07)", color: "rgba(240,238,232,0.4)" }}
        >
          <span>← → switch</span>
          <span>space hold</span>
          <span>f quiet</span>
        </div>
      </div>

      <p className="mt-3 pl-1 text-[10.5px] leading-relaxed" style={{ color: "rgba(240,238,232,0.34)" }}>
        now showing
        <br />
        <span style={{ color: active.swatch[0] }}>{active.name}</span>
        <span> · {active.captionVariant} captions · {active.panelVariant} log</span>
      </p>
    </div>
  );
}
