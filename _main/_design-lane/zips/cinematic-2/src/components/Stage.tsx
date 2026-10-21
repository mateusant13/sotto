import { useEffect, useMemo, useState } from "react";
import type { Theme } from "../themes";

interface Props {
  theme: Theme;
  topInset: number;
}

/** Deterministic pseudo random so theme changes don't reshuffle wildly. */
const rnd = (seed: number) => {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
};

export default function Stage({ theme, topInset }: Props) {
  const [layers, setLayers] = useState<{ src: string; key: string }[]>([
    { src: theme.wall.src, key: theme.id },
  ]);

  useEffect(() => {
    setLayers((prev) => {
      if (prev[prev.length - 1]?.src === theme.wall.src) return prev;
      return [...prev, { src: theme.wall.src, key: `${theme.id}-${Date.now()}` }].slice(-2);
    });
  }, [theme.id, theme.wall.src]);

  const motes = useMemo(() => {
    const kind = theme.particle;
    const count = kind === "rain" ? 46 : kind === "snow" ? 60 : 26;
    const list = Array.from({ length: count }, (_, i) => {
      const r1 = rnd(i + 1);
      const r2 = rnd(i * 7.3 + 2);
      const r3 = rnd(i * 3.7 + 5);
      if (kind === "rain") {
        const h = 8 + r3 * 18;
        return {
          style: {
            left: `${r1 * 108 - 4}%`,
            height: `${h}vh`,
            width: r3 > 0.8 ? "1.6px" : "1px",
            opacity: 0.18 + r2 * 0.4,
            animationDuration: `${(0.9 + r3 * 1.3).toFixed(2)}s`,
            animationDelay: `${(-r2 * 3).toFixed(2)}s`,
            background: `linear-gradient(to bottom, transparent, ${theme.particleColor})`,
          } as React.CSSProperties,
        };
      }
      const size = kind === "snow" ? 2 + r3 * 4 : 1.5 + r3 * 3.5;
      return {
        style: {
          left: `${r1 * 100}%`,
          bottom: `${-4 - r2 * 10}%`,
          width: `${size}px`,
          height: `${size}px`,
          opacity: 0.15 + r2 * 0.5,
          background: theme.particleColor,
          animationDuration: `${(kind === "snow" ? 12 + r3 * 16 : 10 + r3 * 18).toFixed(1)}s`,
          animationDelay: `${(-r2 * 12).toFixed(1)}s`,
          boxShadow: `0 0 ${size * 2.4}px ${theme.particleColor}`,
        } as React.CSSProperties,
      };
    });
    return list;
  }, [theme.particle, theme.particleColor]);

  const particleClass = theme.particle === "rain" ? "rain-streak" : "drift-mote";

  return (
    <div className="absolute inset-0 overflow-hidden" style={{ background: "var(--page)" }}>
      {layers.map((l, i) => (
        <div
          key={l.key}
          className="absolute inset-0 bg-cover bg-center transition-opacity duration-[1100ms] ease-out"
          style={{
            backgroundImage: `url(${l.src})`,
            filter: theme.filter,
            transform: "scale(1.04)",
            opacity: i === layers.length - 1 ? 1 : 0,
          }}
        />
      ))}

      {/* grades / legibility scrims */}
      {theme.overlays.map((o, i) => (
        <div key={i} className="absolute inset-0 pointer-events-none" style={{ background: o }} />
      ))}

      {/* vignette */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(115% 90% at 50% 45%, transparent 42%, rgba(0,0,0,${theme.vignette}) 100%)`,
        }}
      />

      {/* ambient texture */}
      {theme.particle !== "none" && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {motes.map((m, i) => (
            <span key={i} className={particleClass} style={m.style} />
          ))}
        </div>
      )}

      {/* film grain */}
      <div
        className="absolute inset-0 pointer-events-none mix-blend-overlay grain-layer"
        style={{ opacity: theme.grain }}
      />

      {/* scene slate */}
      <div
        className="absolute left-6 sm:left-9 pointer-events-none select-none transition-all duration-500"
        style={{ top: topInset + 18, fontFamily: theme.fonts.ui }}
      >
        <div className="flex items-center gap-2.5">
          <span
            className="h-[7px] w-[7px] rounded-full"
            style={{ background: "var(--accent)", boxShadow: "0 0 14px var(--accent)" }}
          />
          <span
            className="text-[10px] tracking-[0.32em] uppercase"
            style={{ color: "color-mix(in srgb, var(--text) 78%, transparent)" }}
          >
            {theme.scene}
          </span>
        </div>
        <div
          className="mt-1.5 text-[10.5px] tracking-[0.18em] italic"
          style={{ color: "color-mix(in srgb, var(--text) 46%, transparent)" }}
        >
          {theme.sceneNote}
        </div>
      </div>

      {/* frame corners — reads as a film still without boxing anything in */}
      <div className="absolute inset-0 pointer-events-none">
        {[
          "top-4 left-4 border-t border-l",
          "top-4 right-4 border-t border-r",
          "bottom-4 left-4 border-b border-l",
          "bottom-4 right-4 border-b border-r",
        ].map((pos) => (
          <span
            key={pos}
            className={`absolute h-5 w-5 ${pos}`}
            style={{ borderColor: "color-mix(in srgb, var(--text) 22%, transparent)" }}
          />
        ))}
      </div>
    </div>
  );
}
