import { useEffect } from "react";

/** Barras de nível que reagem a cada palavra emitida (tick). */
export function LevelMeter({
  tick,
  playing,
  color = "rgba(255,196,107,0.9)",
}: {
  tick: number;
  playing: boolean;
  color?: string;
}) {
  const heights = [7, 12, 16, 11, 8];
  return (
    <span className="flex h-4 items-end gap-[2.5px]" aria-hidden="true">
      {heights.map((h, i) => (
        <span
          key={playing ? `${tick}-${i}` : `idle-${i}`}
          className="level-bar w-[2.5px] rounded-sm"
          style={
            playing
              ? { height: h, background: color, animationDelay: `${i * 26}ms` }
              : {
                  height: h,
                  background: color,
                  animation: "none",
                  transform: "scaleY(0.22)",
                  transformOrigin: "bottom",
                  opacity: 0.5,
                }
          }
        />
      ))}
    </span>
  );
}

/** Observa elementos .reveal e aplica .is-in quando entram na viewport. */
export function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-in");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

export function IconPlay() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
      <path d="M3 1.6v10.8c0 .6.65.97 1.17.66l8.4-5.4a.78.78 0 0 0 0-1.32l-8.4-5.4A.78.78 0 0 0 3 1.6Z" />
    </svg>
  );
}

export function IconPause() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
      <rect x="2.6" y="1.8" width="3.4" height="10.4" rx="1" />
      <rect x="8" y="1.8" width="3.4" height="10.4" rx="1" />
    </svg>
  );
}

export function IconArrowUp() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 10V2M2.5 5.5 6 2l3.5 3.5" />
    </svg>
  );
}
