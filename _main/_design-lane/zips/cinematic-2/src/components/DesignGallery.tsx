import type { Theme } from "../themes";
import { CAPTION_LABELS, CHROME_LABELS, PANEL_LABELS } from "../themes";

interface Props {
  themes: Theme[];
  activeId: string;
  onPick: (id: string) => void;
  onClose: () => void;
}

export default function DesignGallery({ themes, activeId, onPick, onClose }: Props) {
  const active = themes.find((t) => t.id === activeId) ?? themes[0];

  return (
    <div
      className="fade-in absolute inset-0 z-50 flex items-center justify-center p-3 sm:p-6"
      style={{
        background: `radial-gradient(120% 100% at 50% 0%, color-mix(in srgb, var(--page) 82%, transparent), color-mix(in srgb, var(--page) 96%, transparent))`,
        backdropFilter: "blur(26px) saturate(1.1)",
        WebkitBackdropFilter: "blur(26px) saturate(1.1)",
      }}
      onClick={onClose}
    >
      <div
        className="quiet-scroll flex max-h-full w-full max-w-[1240px] flex-col overflow-hidden rounded-[26px]"
        style={{
          background: "color-mix(in srgb, var(--surface) 94%, transparent)",
          border: "1px solid var(--line)",
          boxShadow: "0 60px 140px -60px rgba(0,0,0,.85)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-wrap items-end justify-between gap-4 px-6 pt-6 pb-4 sm:px-8">
          <div>
            <div
              className="uppercase"
              style={{ fontSize: "0.6rem", letterSpacing: "0.32em", color: "var(--dim)" }}
            >
              twenty rooms, one room
            </div>
            <h2
              className="mt-1.5"
              style={{
                fontFamily: active.fonts.display,
                fontSize: "clamp(1.4rem, 2.4vw, 2rem)",
                fontWeight: 400,
                color: "var(--text)",
                letterSpacing: "-0.015em",
              }}
            >
              Designs
            </h2>
            <p style={{ marginTop: 6, maxWidth: "56ch", fontSize: "0.78rem", lineHeight: 1.6, color: "var(--dim)" }}>
              Same transcript engine underneath — only the light in the room changes. Slow, warm, low
              volume: nothing here shouts at you.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span style={{ fontSize: "0.6rem", letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--dim)" }}>
              ← → browse · 1–9 quick · esc close
            </span>
            <button
              onClick={onClose}
              className="rounded-full px-3.5 py-1.5 transition-colors"
              style={{
                fontSize: "0.62rem",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--text)",
                background: "var(--surface-2)",
                border: "1px solid var(--line)",
              }}
            >
              close
            </button>
          </div>
        </div>

        <div className="quiet-scroll min-h-0 flex-1 overflow-y-auto px-6 pb-6 sm:px-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {themes.map((t) => {
              const isActive = t.id === activeId;
              return (
                <button
                  key={t.id}
                  onClick={() => onPick(t.id)}
                  className="group relative overflow-hidden text-left transition-all duration-300"
                  style={{
                    borderRadius: 18,
                    border: `1px solid ${isActive ? "color-mix(in srgb, var(--accent) 60%, transparent)" : "var(--line)"}`,
                    background: "var(--surface-2)",
                    transform: "translateY(0)",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-3px)")}
                  onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
                >
                  <div
                    className="relative h-[132px] w-full bg-cover bg-center"
                    style={{ backgroundImage: `url(${t.wall.thumb})`, filter: t.filter }}
                  >
                    <div className="absolute inset-0" style={{ background: t.overlays[0] }} />
                    <div
                      className="absolute inset-x-0 bottom-0 h-2/3"
                      style={{ background: "linear-gradient(to top, rgba(6,8,10,.78), transparent)" }}
                    />
                    <div className="absolute left-3.5 bottom-2.5 right-3.5 flex items-end justify-between gap-3">
                      <div>
                        <div style={{ fontSize: "0.55rem", letterSpacing: "0.26em", color: "rgba(255,255,255,.62)" }}>
                          {t.n}
                        </div>
                        <div
                          style={{
                            fontFamily: t.fonts.display,
                            fontSize: "1.02rem",
                            color: "#fff",
                            letterSpacing: "-0.01em",
                            textShadow: "0 2px 12px rgba(0,0,0,.6)",
                          }}
                        >
                          {t.name}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 pb-1">
                        {[t.vars["--accent"], t.vars["--accent-2"], t.vars["--surface"]].map((c, i) => (
                          <span
                            key={i}
                            className="h-3 w-3 rounded-full"
                            style={{
                              background: c,
                              border: "1px solid rgba(255,255,255,.34)",
                              boxShadow: "0 2px 8px rgba(0,0,0,.4)",
                            }}
                          />
                        ))}
                      </div>
                    </div>
                    {isActive && (
                      <span
                        className="absolute top-3 right-3 rounded-full px-2.5 py-1"
                        style={{
                          fontSize: "0.55rem",
                          letterSpacing: "0.2em",
                          textTransform: "uppercase",
                          color: "#0d1114",
                          background: "rgba(255,255,255,.9)",
                        }}
                      >
                        sitting here
                      </span>
                    )}
                  </div>

                  <div className="px-4 pt-3 pb-4">
                    <p style={{ fontSize: "0.72rem", lineHeight: 1.55, color: "var(--dim)" }}>{t.mood}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-1.5">
                      {[CAPTION_LABELS[t.caption.style], PANEL_LABELS[t.panel.style], CHROME_LABELS[t.chrome], t.fonts.fontLabel].map(
                        (label) => (
                          <span
                            key={label}
                            className="rounded-full px-2 py-0.5"
                            style={{
                              fontSize: "0.55rem",
                              letterSpacing: "0.14em",
                              textTransform: "uppercase",
                              color: "color-mix(in srgb, var(--text) 72%, transparent)",
                              border: "1px solid var(--line)",
                            }}
                          >
                            {label}
                          </span>
                        ),
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
