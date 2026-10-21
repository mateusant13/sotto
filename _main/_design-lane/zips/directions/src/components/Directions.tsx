import type { CSSProperties, ReactNode } from "react";
import { DESIGNS, type DesignId } from "../data/designs";
import { IconArrowUp } from "./bits";

const H3_WEIGHT: Record<DesignId, string> = {
  tele: "font-semibold uppercase tracking-wide",
  bcast: "font-semibold",
  mano: "italic font-medium",
  cine: "font-light",
  inst: "font-bold",
};

function Meta({ label, tone, children }: { label: string; tone?: string; children: ReactNode }) {
  return (
    <div>
      <div className={"font-bcast text-[9.5px] tracking-[0.26em] " + (tone ?? "text-bone/45")}>{label}</div>
      <p className="mt-2 text-[13.5px] leading-relaxed text-bone/75">{children}</p>
    </div>
  );
}

export function Directions({ onPick }: { onPick: (id: DesignId) => void }) {
  return (
    <section className="relative overflow-hidden bg-ink py-24 lg:py-32">
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -right-10 -top-16 select-none font-display text-[24vw] font-extrabold leading-none text-white/[0.025]"
      >
        SOTTO
      </span>

      <div className="relative mx-auto max-w-6xl px-5 lg:px-8">
        <div className="reveal max-w-3xl">
          <p className="font-bcast text-[10px] tracking-[0.32em] text-ember">DIREÇÕES DE DESIGN · 05</p>
          <h2 className="mt-4 font-display text-[clamp(32px,4.6vw,60px)] font-bold leading-[1.03] tracking-tight text-bone">
            Cinco modelos mentais para a mesma legenda.
          </h2>
          <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-fog">
            O painel se comporta menos como um aplicativo e mais como uma camada de percepção: algo que se consulta
            sem deslocar a atenção do filme, do jogo ou da reunião. A diferença entre a fala em formação e a fala
            consolidada é o coração de cada linguagem.
          </p>
        </div>

        <div className="mt-14">
          {DESIGNS.map((d) => (
            <article
              key={d.id}
              className="reveal group -mx-2 grid gap-6 border-t border-white/10 px-2 py-10 transition-colors duration-500 hover:bg-white/[0.025] lg:-mx-4 lg:grid-cols-[120px_1fr] lg:gap-10 lg:px-4 lg:py-12"
            >
              <div
                className="num-outline font-display text-[64px] font-extrabold leading-[0.85] lg:text-[88px]"
                style={{ WebkitTextStroke: `1.5px ${d.accent}`, "--num-ac": d.accent } as CSSProperties}
              >
                {d.num}
              </div>

              <div className="grid gap-8 lg:grid-cols-[1.05fr_1.45fr] lg:gap-12">
                <div>
                  <p className="font-bcast text-[9.5px] tracking-[0.26em]" style={{ color: d.accent }}>
                    {d.model.toUpperCase()}
                  </p>
                  <h3 className={"mt-2.5 text-[30px] leading-tight text-bone lg:text-[36px] " + d.fontClass + " " + H3_WEIGHT[d.id]}>
                    {d.name}
                  </h3>
                  <p className="mt-3 font-bcast text-[10.5px] leading-relaxed tracking-[0.06em] text-fog">{d.spec}</p>
                  <button
                    onClick={() => onPick(d.id)}
                    className="mt-6 inline-flex items-center gap-2 rounded-full border border-white/18 px-4 py-2 text-[12px] font-medium text-bone/85 transition-all duration-300 hover:gap-3 hover:bg-bone hover:text-ink"
                  >
                    ver no palco <IconArrowUp />
                  </button>
                </div>

                <div className="grid gap-6 sm:grid-cols-3">
                  <Meta label="IMPACTO" tone="text-lagoon">
                    {d.impact}
                  </Meta>
                  <Meta label="RECOMENDAÇÃO">{d.reco}</Meta>
                  <Meta label="RISCO" tone="text-ember">
                    {d.risk}
                  </Meta>
                </div>
              </div>
            </article>
          ))}
          <div className="border-t border-white/10" />
        </div>
      </div>
    </section>
  );
}
