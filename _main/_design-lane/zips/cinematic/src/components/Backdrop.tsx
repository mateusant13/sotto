import type { Theme } from "../themes";

interface BackdropProps {
  theme: Theme;
  prevTheme: Theme | null;
}

/**
 * Full-bleed cinematic wallpaper with a slow Ken Burns drift,
 * crossfade between scenes, vignette, reading scrims and film grain.
 */
export function Backdrop({ theme, prevTheme }: BackdropProps) {
  return (
    <div className="fixed inset-0 overflow-hidden bg-[#05070c]" aria-hidden="true">
      {prevTheme && (
        <img
          src={prevTheme.wallpaper}
          alt=""
          draggable={false}
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}

      <div className="kb absolute inset-0">
        <img
          key={theme.id}
          src={theme.wallpaper}
          alt=""
          draggable={false}
          className="backdrop-in absolute inset-0 h-full w-full object-cover"
        />
      </div>

      {/* filmic framing */}
      <div className="vignette absolute inset-0" />
      <div className="scrim-top absolute inset-x-0 top-0 h-[170px]" />
      <div className="scrim-bottom absolute inset-x-0 bottom-0 h-[40vh]" />

      {/* living grain */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="grain" />
      </div>
    </div>
  );
}
