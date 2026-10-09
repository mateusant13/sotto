Quatro tentativas de ferramenta falharam nesta sessão com `delivery seam is closed` (2 greps + 1 read + 1 read). Não insisto uma quinta: a lei diz que uma falha nunca responde como sucesso. As duas lacunas que eu tinha marcado como fecháveis **continuam abertas**, e o relatório reflecte isso.

---

## Auditoria — `specs/03-capture-encode.md`
**Classe auditada:** constante normativa que contradiz a aritmética da própria spec que a declara.

**POPULATION:** 1 de 6 specs (`01,02,03,04,05,07`) = **16,7 %**. Do ficheiro-alvo, **linhas 1–301 apenas** — o read truncou (`original_bytes=25351`) e **as 2 tentativas de continuar no offset 302 falharam**. Apoio lido por inteiro: 2 ficheiros (`specs/01` 8 591 B, `docs/research/03` 7 025 B). Código: `src/capture/replay.h` linhas20–79 de ~180. **18 asserções numéricas recomputadas**, 4 delas descartadas por bug do meu instrumento e recalculadas. **0 medições de hardware.**

**WINDOW:** esta sessão, **2026-10-07 ~12:31–12:50 GMT-0300**, 2 invocações PowerShell mais 4 tentativas falhadas. A recomputação é **determinística** — não é uma amostragem e não tem population no sentido estatístico; repeti-la amanhã dá o mesmo número. As **medições de origem não são minhas**: a spec 03 declara-se MEASURED em **2026-10-08**, data **posterior ao meu relógio de sessão**, e o `LastWriteTime` que li (`07/10/2026 12:06`) é **anterior** a isso. Leitura dd/MM/yyyy é consistente; MM/dd daria10 Jul. **A discrepância é UNKNOWN e não é o meu objectivo.**

### ACHADO 1 — o bpp de §2.6 é 10× menor que a sua própria tabela

`specs/03:142-144` publica como regra de shipment `GAMING ≈ 0.036 bpp` e `DESKTOP ≈ 0.013 bpp`. Recomputado:

| coluna | bpp implícito pela tabela | declarado | razão |
|---|---|---|---|
| GAMING 45 Mbps @1080p60 | **0,3617** | 0,036 | **10,05×** |
| DESKTOP 8 Mbps @1080p30 | **0,1286** | 0,013 | **9,89×** |

A tabela **não** está errada: os seis pares bitrate/resolução reproduzem-se exactamente a 0,3617 / 0,1286 (1440p60 → 80,0 Mbps; 4K60 → 180,0 Mbps, ambos os que a spec escreve). É a **constante** que não reconcilia com a tabela que ela própria introduz.

**Refutações que tentei, e como caíram:** (1) *"a tabela é que está errada"* — não, os seis pares são consistentes a 0,3617; (2) *"bpp é por segundo"* — 21,7 bits/pixel/s, o que piora o erro para **603×**; (3) *"0,036 bpp é plausível"* — 0,036 bpp em 1080p60 dá 4,5 Mbps, DVD queimado; a ordem de grandeza real é 0,36, coerente com os 40–50 Mbps do Owner.

**A lane já sabia:** `src/capture/replay.h:34-37` documenta *"specs/01's 'bpp' figures … are a FACTOR OF TEN off its own table"* e **contorna** usando as bitrates-âncora escaladas por pixels. O código está certo; **a spec continua a publicar o número errado**, e `specs/03:143` ainda marca `UNKNOWN: whether 0.036 bpp is the right knee` — um UNKNOWN pendente **sobre uma constante que o código não usa**. Implementar pelo texto daria 17,9 Mbps em 4K60 onde a spec exige 180: anel 10× curto e clip degradado, ambos silenciosos.

### ACHADO 2 — regra de corte congelada em 120 s, e as duas specs discordam do sinal

- `specs/03:150-152` — `first entry with isIDR whose qpc_ns ≥ t_cut − ring_seconds`, com o literal **"nearest IDR ≥ hotkey − 120 s"**.
- `specs/01:56` — **"nearest forced IDR at or before (hotkey − ring_relevant_seconds)"**.

Divergências: **sentido oposto** (`≥` vs `≤` — muda o início do clip em até um intervalo de IDR) e **120 s congelados** num documento cujo DESKTOP usa **600 s**. `receipt-03:170-173` confirma que a implementação seguiu spec 03. `ring_relevant_seconds` não aparece em nenhum sítio do código que li. Custo: seguir spec 01 recorta clips de DESKTOP em 120 s em vez de 600 — exactamente o caso que `specs/01` §2 promete.

### O que está CORRETO (não re-litigar)

A aritmética do **anel** passa: 45 Mbps × 120 s = 675 MB(10⁶) = 643,7 MiB · 40 Mbps × 120 s = 572,2 MiB · 200 Mbps × 120 s = 2 861,0 MiB — coincide com a lei 7 do `AGENTS.md` e com §2.6. **A tabela de bitrate não é o defeito; a constante é.**

## SELF-AUDIT

**Protocolos em falta.** ❌ **Controlo de duas cores** — a minha "passagem 2" é uma refutação aritmética, não um arm B partido que tem de ficar RED. Se a minha fórmula de bpp estivesse errada, o achado e a refutação caem juntos. ❌ **Leitura do código que implementa o corte** — o achado 2 herda um **relato de receipt**, não `replay.cpp`/`ring_buffer.h`. ✅ **Nada escrito**, ✅ **zero I/O pesado**, ✅ **lei 8 sem custo** (aritmética pura, 0 threads de GPU).

**Verificação extra que fiz.** Recomputei os seis pares por **três definições alternativas de bpp** em vez de aceitar a tabela como verdade. **O meu primeiro script mentiu-me:** helpers `Mb` e `MB` colidiram (PowerShell é case-insensitive), a segunda definição sobrescreveu a primeira e as colunas MiB/decimal saíram iguais (675 = 675) — só o absurdo aritmético o expôs. Descartei as 4 asserções corrompidas e recalculei-as. E confirmei que o achado **é preexistente** (`replay.h:34-37`), o que muda a **causa provável** de "decisão errada" para **transcrição com erro de casa decimal** — e baixa a severidade.

**Checkboxes NOVOS, nomeados e mecânicos.** (1) `bpp-matches-own-table`: `|declarado − bitrate/(w·h·fps)|/declarado ≤ 0,05` → hoje **RED** 10,05 e 9,89. (2) `cut-rule-sign-consistent`: operador de `specs/01:56` ≡ `specs/03:150` → hoje **RED** (`≤` vs `≥`). (3) `ring-seconds-not-frozen-in-prose`: nenhum literal contradiz a tabela do modo → **RED** (120 vs 600). (4) `no-orphan-terms`: cada snake_case da spec existe em `src/` → **RED** (`ring_relevant_seconds`). (5) `unknown-marker-points-at-live-constant` → **RED** (UNKNOWN aponta para 0,036; código usa 0,362). (6) `spec-status-marks-supersession` → **NÃO EXECUTADO** (grep falhou 4×).

**Revisão por outro subagent: NÃO FEITA.** Sou o autor **e** o revisor. Isto é gate-doubt estrutural: as refutações vêm do meu próprio raciocínio sobre a minha própria fórmula — e um revisor independente é exactamente quem pegaria num erro de unidade (MB/MiB) que o meu primeiro script **já cometeu**.

**Confiança.** **ALTA0,9** no Achado 1: 18 asserções reprodutíveis, 3 definições alternativas refutadas, confirmação independente em `replay.h:34-37`, não depende de linhas que não li. **O que a move:** se "bpp" fosse deliberadamente "bits por pixel por10 frames" — mas isso continua a ser defeito de escrita, porque **nenhuma definição acompanha a constante**. **MÉDIA 0,6** no Achado 2: a divergência é factual e legível, mas **0 linhas do código**, e não sei se existe marcação de superação. **O que a move:** ler `replay.cpp`; o grep de `SUPERSEDED`.

**O que NÃO foi verificado, por nome.** (1) **`specs/03` acima da linha 301** — 2 reads falharam; pode haver mais instâncias da classe. (2) **Se existe marcação `SUPERSEDED`** — 4 greps falharam; **é o que mais pesa no Achado 2**. (3) **Specs 04/05/07** (135 KB) — population de 5 specs por auditar, fora do escopo "one spec, one class". O grep de `0\.036` não as devolveu, o que prova que *esta* constante não se propagou — **não** que não haja erro análogo de fator10 noutra constante. (4) **A classe no repo inteiro** — não posso afirmá-la confinada ao spec 03. (5) **MB vs MiB no `receipt-03:148-149`** ("707 MB"): nem `48+1,02×675 MB` (736,5) nem `48+1,02×643,7 MiB` (704,6) dá707 exactamente — **UNKNOWN**, não levado a achado porque só li 3 linhas do receipt.

**Gate-doubt.** O relatório **parece** bem-supportado porque 18 asserções concordam — e **concorrência interna não é verificação**: saem da mesma fórmula que produziu o número original. A única coisa independente foi outro lane já ter achado o mesmo, e isso prova que **alguém já achou**, não que o meu cálculo está certo. Sem os checkboxes em ficheiro executável, e sem o braço RED, tenho **texto que parece gate**. O portão real que eu quereria: script que valida 01+03 GREEN **e** uma cópia com o bpp partido por uma casa decimal **RED**.

---

## P0 EM TRÊS

**AGORA:** nada a correr — a instrução é uma continuação e a vez termina. P0 real de quem for a seguir: lane `worker` a corrigir `specs/01:27-28` + `specs/03:142-144` (constante bpp e o UNKNOWN que aponta para ela) e `specs/01:56` (sinal, 120 s, termo órfão). **Eu não posso: sou read-only e defini essa fronteira.**

**JÁ FIZ:** 1 de 6 specs, linhas 1–301 do alvo, 1 classe de defeito · 18 asserções recomputadas, 4 descartadas por bug próprio e refeitas · 3 refutações ao achado principal, nenhuma sobreviveu ·achei que o defeito já era conhecido na lane e não foi propagado · **zero ficheiros escritos**.

**NÃO FIZ, e porquê:** (a) `specs/03` acima da linha 301 — 2 reads falharam; (b) marcar se existe `SUPERSEDED` — 4 greps falharam; (c) specs 04/05/07 — 135 KB, fora do escopo; (d) `replay.cpp`/`ring_buffer.h` — achado 2 assenta em relato; (e) escrever as correções — de escrita; (f) automatizar os 5 checkboxes num script com braço RED — **checkboxes em texto não são gate**.

Does your implementation meet the spec? NO - a spec não cumpre o seu próprio contrato: publica `0.036 / 0.013 bpp` como regra de shipment (`specs/03:142-144`, `specs/01:27-28`) quando a sua própria tabela exige `0,3617 / 0,1286`, um fator 10 que `src/capture/replay.h:34-37` já contornou em código; e a regra de corte em `specs/01:56` continua "at or before" com 120 s congelados, contra os 600 s do DESKTOP e o "at or after" que spec 03 e o receipt implementaram.