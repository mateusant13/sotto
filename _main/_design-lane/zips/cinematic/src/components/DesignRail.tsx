import { cn } from "../utils/cn";
import type { Theme } from "../themes";

interface DesignRailProps {
  themes: Theme[];
  activeIndex: number;
  onSelect: (index: number) => void;
}

/**
 * Left-edge rail — the scene selector. Ten swatches, one per design.
 */
export function DesignRail({ themes, activeIndex, onSelect }: DesignRailProps) {
  return (
    <nav
      className="absolute top-1/2 left-4 z-20 hidden -translate-y-1/2 flex-col items-start gap-[7px] md:flex lg:left-6"
      aria-label="Caption scenes"
    >
      <span className="mb-2 font-mono text-[8.5px] tracking-[0.34em] text-[var(--dim)] uppercase">
        Scenes
      </span>

      {themes.map((t, i) => {
        const active = i === activeIndex;
        return (
          <button
            key={t.id}
            onClick={() => onSelect(i)}
            aria-label={`Scene ${i + 1}: ${t.name}`}
            aria-current={active}
            className="group flex items-center gap-2.5 rounded-full py-[3px] pr-2 pl-1 transition-colors hover:bg-[var(--hover)]"
          >
            <span
              className="h-2 w-2 rounded-full transition-all duration-300 group-hover:scale-125"
              style={{
                background: t.swatch,
                opacity: active ? 1 : 0.5,
                boxShadow: active ? `0 0 12px ${t.swatch}` : "none",
                transform: active ? "scale(1.35)" : undefined,
              }}
            />
            <span
              className={cn(
                "font-mono text-[10px] tabular-nums transition-all duration-300",
                active
                  ? "text-[var(--ink)]"
                  : "text-[var(--faint)] opacity-0 group-hover:opacity-100"
              )}
            >
              {String(i + 1).padStart(2, "0")}
            </span>
            {active && (
              <span className="name-in text-xs font-medium tracking-wide text-[var(--ink)]">
                {t.name}
              </span>
            )}
          </button>
        );
      })}

      <span className="mt-2 hidden font-mono text-[8.5px] tracking-[0.24em] text-[var(--faint)] lg:block">
        ← → to roam
      </span>
    </nav>
  );
}
