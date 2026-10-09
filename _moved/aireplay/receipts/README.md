# `receipts/` — index

Um **receipt** é o registo durável de uma medição: o que foi corrido, com que
POPULATION, em que WINDOW, e o que fica **UNKNOWN**. Este ficheiro é o índice —
não substitui nenhum recibo.

**POPULATION: 39 ficheiros** em `receipts/` no snapshot **2026-10-07 13:36 -03:00**
(contagem com `Get-ChildItem receipts -File`; POP de ficheiros em disco, não de
linhas). Os números desta secção são um **instante**: lanes escrevem aqui em
paralelo. Re-corra o censo antes de citar.

---

## ⚠️ PERIGO DE CITAÇÃO — o NÚMERO NÃO É CHAVE

**Cinco números estão duplicados.** Duas lanes escolheram o mesmo número em
momentos diferentes e nenhuma viu a outra. Citar "receipt 16" hoje é **ambíguo**:

| número | ficheiros que o reclamam | um sobre | o outro sobre |
|---|---|---|---|
| **03** | `receipt-03-capture-impl.md` · `receipt-03-nvenc-sessions.md` | pipeline D3D11→NVENC→ring→mp4 | sessões NVENC |
| **15** | `receipt-15-instant-replay-trigger.md` · `receipt-15-offline-cut-pass1147.md` | o trigger de instant-replay | heartbeat 11:47, muxer sem WGC |
| **16** | `receipt-16-ring-cap-from-system-ram.md` · `receipt-16-wasapi-audio-loopback.md` | ring cap precificado contra RAM de sistema | loopback de áudio WASAPI |
| **23** | `receipt-23-cron-woke-this-session.md` · `receipt-23-trigger-defects.md` | o cron acordou esta sessão (headline retractado) | dois defeitos no trigger |
| **24** | `receipt-24-clip-to-asr-chain.md` · `receipt-24-wake-defects-fixed.md` | a cadeia clip→áudio→transcrição→índice | os seis defeitos de wake |

**Regra que este índice impõe: cite pelo FILENAME, nunca pelo número.**

**Porque é que não foram renumerados.** Um renumber loses as citações já
escritas: outros lanes citam `receipt-23` e `receipt-16` por número em comentários
de código e em gates que correm. Renumerar parte a chave sem avisar nenhuma das
duas pontas. Um índice que dá a chave correcta custa um ficheiro; um renumber
custa citações silenciosamente erradas.

**Nomeie o ficheiro, não o número.** `receipt-16-wasapi-audio-loopback.md` é
sempre inequívoco; `receipt 16` não é. Ao escrever um recibo novo, o número já
em uso é occupied — pegue o próximo livre (hoje: **27 usado, 31 e 33+ livres**).

---

## O índice

| # | filename | assunto (uma linha) |
|---|---|---|
| 01 | `receipt-01-capture-encode.md` | captura + encode: o que foi CORRIDO e o que continua UNKNOWN |
| 02 | `receipt-02-asr-impl.md` | ASR: a primeira spec e o primeiro código de produto do repo |
| 03 | `receipt-03-capture-impl.md` | pipeline D3D11 → NVENC → ring RAM → `clip.mp4`, MEDIDO |
| 03 | `receipt-03-nvenc-sessions.md` | sessões NVENC (probe: `_main\nvenc-probe.cpp`) — **nº duplicado** |
| 04 | `receipt-04-asr.md` | ASR: o que foi RUN/VERIFIED e o que é UNKNOWN |
| 05 | `receipt-05-onnx-asr.md` | ASR via ONNX Runtime: RUN, VERIFIED e UNKNOWN |
| 06 | `receipt-06-embeddings.md` | embeddings: o que foi RUN/READ e o que é UNKNOWN |
| 07 | `receipt-07-index-search.md` | índice e pesquisa (store, schema, fusão, reranker, doisursors) |
| 08 | `receipt-08-import-library.md` | biblioteca de importação: RUN/MEASURED e UNKNOWN |
| 10 | `receipt-10-redux-2-threads.md` | Redux a 2 threads: RUN, VERIFIED e UNKNOWN |
| 11 | `receipt-11-onnx-threads.md` | contagem de threads do ONNX: RUN, VERIFIED e UNKNOWN |
| 12 | `receipt-12-audio-level-contract.md` | contrato de nível de áudio (UMA pergunta: o painel vê um nível real?) |
| 13 | `receipt-13-refute-integration-audit.md` | a passagem de refutação sobre a auditoria de integração |
| 14 | `receipt-14-ring-cap-vram-vs-ram.md` | o ring cap precifica RAM de sistema contra VRAM |
| 15 | `receipt-15-instant-replay-trigger.md` | o trigger de instant-replay (a promessa do ShadowPlay) — **nº duplicado** |
| 15 | `receipt-15-offline-cut-pass1147.md` | heartbeat 11:47 — o muxer é provável sem WGC — **nº duplicado** |
| 16 | `receipt-16-ring-cap-from-system-ram.md` | o ring cap agora é precificado contra RAM de SISTEMA — **nº duplicado** |
| 16 | `receipt-16-wasapi-audio-loopback.md` | loopback de áudio WASAPI (a feature de áudio que faltava) — **nº duplicado** |
| 17 | `receipt-17-asr-parity.md` | o ASR funciona END TO END em fala real; duas falhas silenciosas viraram recusas |
| 18 | `receipt-18-capture-capability-battery.md` | o que esta box consegue REALMENTE codificar e capturar, medido agora |
| 19 | `receipt-19-aggregate-gate.md` | o gate agregado: um comando que diz a verdade sobre o projeto |
| 20 | `receipt-20-durability-git-coverage.md` | durability: um mau dia ainda consegue destruir este produto? |
| 21 | `receipt-21-wake-mechanism-audit.md` | auditoria do mecanismo de wake (lane 16, auditor) |
| 22 | `receipt-22-single-cron-delivers.md` | um único cron CONSEGUI enviar mensagem para uma sessão, como o dono escreve |
| 23 | `receipt-23-cron-woke-this-session.md` | a headline de text-match é RETRACTADA; a evidência da retractação também — **nº duplicado** |
| 23 | `receipt-23-trigger-defects.md` | dois defeitos concretos no trigger, remedidos e gateados — **nº duplicado** |
| 24 | `receipt-24-clip-to-asr-chain.md` | a CADEIA ponta a ponta: clip → áudio → transcrição → linha de índice → pesquisa — **nº duplicado** |
| 24 | `receipt-24-wake-defects-fixed.md` | os seis defeitos de wake aplicados, mais um sétimo — **nº duplicado** |
| 25 | `receipt-25-overlay-panel.md` | o painel overlay (`src/ui/`) e a sua cura de mapeamento de janela |
| 26 | `receipt-26-receipt-audit.md` | a ferramenta de auditoria que encontra afirmações que ninguém verificou |
| 27 | `receipt-27-queue-delivery-latency.md` | latência de entrega na fila, medida com a ligação autoritativa |
| 28 | `receipt-28-review-synthesis.md` | síntese de reviews: 6 veredictos → 12 itens de trabalho ordenados |
| 29 | `receipt-29-agents-truth.md` | o `AGENTS.md` é o primeiro conjunto de instruções do produto — e estava a mentir |
| 30 | `receipt-30-clip-storage-retention.md` | o store de clips em rotação: layout, retenção, disco cheio, recuperação |
| 32 | `receipt-32-ring-defects-closed.md` | defeitos do ring cap da lane 3: as seis findings de review, fechadas |
| — | `receipt-preview-designs.md` | uma página que mostra as cinco direções de design |
| — | `receipt-render-panel-temas.md` | o renderizador de capturas por tema |
| — | `review-L16.md` | review da lane L16 — a auditoria do mecanismo de wake |
| — | `review-L4.md` | review da lane L4 — `src/index/` (schema, store FTS5, writer, search) |

Os quatro últimos **não** seguem a numeração: `receipt-preview-designs` e
`receipt-render-panel-temas` são recibos anteriores ao esquema numerado, e
`review-L*.md` são **veredictos de reviewer**, não medições — são a peça que o
receipt 28 sintetiza. Não os renumore: as lanes citam-nos por filename.

---

## DURABILIDADE — porque estedirectório precisa de um índice

Medido em **2026-10-07 13:36 -03:00**, POPULATION = 39 ficheiros em disco:

| estado | n | meaning |
|---|---|---|
| `TRACKED` | 24 | no índice do git — sobrevive a `git clean`/`checkout` |
| `UNTRACKED` | 15 | **em disco, em nenhum índice** — um `git clean -fd` apaga-os sem aviso |
| `MODIFIED` | 2 | tracked com trabalho por commitpar (lane escrevendo agora) |
| `IGNORED` | **0** | — verificado: `git check-ignore` rc=1 em todos os receipts |

**Os 15 untracked foram versionados pelo commit que adicionou este README.** Não
são um resto esquecido: são evidência escrita por lanes em voo que nunca foi
stageada. **Não estão excluídos** — `.gitignore` não menciona `receipts/`, e
`git check-ignore -v` devolve **rc=1** (nada casa) para todos eles. Eram
simplesmente *não commitados*.

O `receipt-20` (lane de durability) **cobriu este directório** — a classe
`receipts`, POP 21 às 12:37:15, com 3 untracked na altura — e o seu §6 diz, sem
ambiguidade, que **não faz fixing**: *"It does not stage, commit, or fix
anything."* Logo isto **não é um esquecimento do L12**: foi uma exclusão
deliberada, com o fixingPushido para uma lane posterior. Esta é essa lane.

**A fracção importa menos que o mecanismo.** 15/39 = **38,5 %** da evidência do
projecto estava a um `git clean` de desaparecer. Um recibo untracked é a mesma
classe de falha que o resto: evidência que desaparece sem nenhum aviso. O
rollback de um ficheiro untracked **não existe** — `git checkout -- <path>`
devolve **rc=1** e `git fsck --unreachable` devolve 0 commits pendurados
(medido no `receipt-20` §R3). Versionar não é higiene: é o rollback.

**Nota de janela.** Este `README.md` foi escrito enquanto as lanes escreviam.
Se um recibo novo aparecer depois do snapshot, o índice está desatualizado por
construção — acrescente a linha. A lista de duplicados, essa, só cresce se
alguém repetir um número; por isso a regra de citar por filename.