export function Verdict() {
  return (
    <section className="relative border-t border-white/8 bg-ink2 py-24 lg:py-28">
      <div className="mx-auto grid max-w-6xl gap-14 px-5 lg:grid-cols-[1.25fr_1fr] lg:gap-20 lg:px-8">
        <div className="reveal">
          <p className="font-bcast text-[10px] tracking-[0.32em] text-lagoon">A APOSTA</p>
          <blockquote className="mt-6 font-display text-[clamp(25px,3.2vw,42px)] font-semibold leading-[1.16] tracking-tight text-bone">
            Teleprompter é a direção mais forte.{" "}
            <em className="font-cine font-light italic text-gold">Manuscrito</em> é a mais interessante — se a
            correção em tempo real for o traço que o Sotto quer tornar visível.
          </blockquote>

          <div className="mt-9 flex flex-wrap items-center gap-5">
            <span className="-rotate-2 rounded-sm border border-dashed border-paper/50 px-3.5 py-2 font-bcast text-[10px] tracking-[0.24em] text-paper/80">
              APOSTA · TELEPROMPTER
            </span>
            <span className="rotate-1 rounded-sm border border-dashed border-pencil/50 px-3.5 py-2 font-bcast text-[10px] tracking-[0.24em] text-pencil/80">
              TESE · MANUSCRITO
            </span>
          </div>
        </div>

        <div className="reveal">
          <h3 className="font-display text-[22px] font-bold text-bone">Sem veredicto estático</h3>
          <ul className="mt-6 space-y-6">
            <li className="border-l-2 border-ember/70 pl-5">
              <p className="font-bcast text-[9.5px] tracking-[0.26em] text-ember">TESTE DE 1 METRO</p>
              <p className="mt-2 text-[14px] leading-relaxed text-bone/75">
                Qual direção se lê melhor a um metro de distância, por cima de imagem em movimento, não se decide no
                papel — exige teste visual real, com o filme rodando e o olho cansado.
              </p>
            </li>
            <li className="border-l-2 border-lagoon/70 pl-5">
              <p className="font-bcast text-[9.5px] tracking-[0.26em] text-lagoon">O TRADE-OFF CENTRAL</p>
              <p className="mt-2 text-[14px] leading-relaxed text-bone/75">
                Clareza de estado contra discrição: quanto mais evidente que “esta linha ainda está mudando”, maior a
                chance de o painel disputar atenção com o fundo.
              </p>
            </li>
          </ul>

          <p className="mt-9 inline-block rounded-full border border-white/12 bg-ink px-4 py-2 font-bcast text-[9.5px] tracking-[0.2em] text-fog">
            PRÓXIMO PASSO · A/B EM MOVIMENTO · 5 CENAS · 1 M
          </p>
        </div>
      </div>
    </section>
  );
}
