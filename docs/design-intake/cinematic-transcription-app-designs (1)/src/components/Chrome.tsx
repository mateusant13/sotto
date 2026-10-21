import { formatClock, type Scene } from "@/data/scenes";
import { LiveDot, LevelMeter } from "@/components/panels/shared";

/** Photographic stage: previous still, incoming still, grade, vignette, grain. */
export function WallpaperLayer({ scene, previous }: { scene: Scene; previous: Scene | null }) {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* tinted base so the frame stays cinematic before the still arrives */}
      <div
        className="absolute inset-0"
        style={{
          background: `radial-gradient(120% 90% at 46% 38%, ${scene.swatch[0]}2e 0%, transparent 62%), linear-gradient(180deg, ${scene.swatch[1]} 0%, #07080a 88%)`,
        }}
      />
      {previous && previous.id !== scene.id && (
        <img
          src={previous.wallpaper}
          alt=""
          aria-hidden
          className="absolute inset-0 h-full w-full object-cover"
          style={{ filter: previous.wallFilter }}
        />
      )}
      <div key={scene.id} className="anim-wall absolute inset-0">
        <img
          src={scene.wallpaper}
          alt=""
          aria-hidden
          className="anim-drift absolute inset-0 h-full w-full object-cover"
          style={{ filter: `${scene.wallFilter} brightness(1.08)` }}
        />
      </div>
      <div className="absolute inset-0" style={{ background: scene.wallOverlay }} />
      {/* projector glow: lifts the middle of the frame so the still reads */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(88% 66% at 46% 42%, rgba(255,255,255,0.075) 0%, rgba(255,255,255,0.02) 46%, transparent 72%)",
          mixBlendMode: "screen",
        }}
      />
      <div className="vignette absolute inset-0" />
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0"
        style={{ height: "34vh", background: "linear-gradient(0deg, rgba(0,0,0,0.34), transparent)" }}
      />
      <div className="grain absolute inset-0 opacity-[0.05] mix-blend-overlay" />
    </div>
  );
}

/** Quiet brand + session chrome in the top-left, away from the picture. */
export function TopBar({
  scene,
  index,
  total,
  elapsed,
  paused,
}: {
  scene: Scene;
  index: number;
  total: number;
  elapsed: number;
  paused: boolean;
}) {
  const accent = scene.panel.accent;
  return (
    <div className="anim-chrome pointer-events-none absolute left-7 top-6 z-30 max-w-[330px]">
      <div className="flex items-center gap-2.5" style={{ color: scene.panel.text }}>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={accent} strokeWidth="1.5" strokeLinecap="round">
          <path d="M3 12h2l1.7-4.6L9 16.4 11.3 9l1.9 5.2L15.1 10 17 13.5h4" />
        </svg>
        <span className="text-[13px] font-medium tracking-[0.28em] uppercase">murmur</span>
        <span
          className="f-dm rounded-full px-2 py-[2px] text-[9.5px] tracking-[0.14em]"
          style={{ background: scene.panel.soft, color: scene.panel.muted, border: `1px solid ${scene.panel.border}` }}
        >
          {String(index + 1).padStart(2, "0")}/{String(total).padStart(2, "0")}
        </span>
      </div>

      <div className="mt-3.5">
        <h1 className="text-[24px] leading-tight" style={{ color: scene.panel.text, fontFamily: scene.captionFont }}>
          {scene.name}
        </h1>
        <p className="mt-1 text-[11.5px] leading-relaxed" style={{ color: scene.panel.muted }}>
          {scene.place}
        </p>
      </div>

      <div className="mt-3 flex items-center gap-3" style={{ color: scene.panel.muted }}>
        <span
          className="inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.16em]"
          style={{ background: scene.panel.surface, border: `1px solid ${scene.panel.border}`, backdropFilter: "blur(14px)" }}
        >
          <LiveDot color={paused ? scene.panel.muted : accent} size={5} ring={!paused} active={!paused} />
          {paused ? "held" : "listening"}
          <span className="f-dm tabular-nums" style={{ color: scene.panel.text }}>
            {formatClock(elapsed)}
          </span>
        </span>
        <LevelMeter bars={10} active={!paused} color={accent} height={11} />
      </div>

      <p className="mt-3 text-[10.5px]" style={{ color: scene.panel.muted, opacity: 0.75 }}>
        {scene.mood} · {scene.hour}
      </p>
    </div>
  );
}
