# PERGUNTAS QUE SÓ O DONO PODE RESPONDER

Cada pergunta aqui tem medição anexada. Nenhuma foi decidida por um agente, porque nenhuma
pode ser: são escolhas de produto, de máquina ou de preço. Data: 2026-10-09.

## Q1 - O PUSH (o passo 9 da sua ordem)
O push de `feat/build-verify-1` está PARADO por causa de trabalho FORA do escopo do ShadowPlay
que está staged no worktree `H:\sotto` (o produto original): 5 ficheiros `app/*`
(`panel.css`, `panel.html`, `panel.js`, `theme-switcher.js`, `app/webview/sotto_webview.py`)
com +424/-111 bytes, mais 25 backdrops de skin. O git status tem 10 173 linhas untracked.

**A tua ordem foi "continue com apenas isso, não o sotto original" (F10).** O push leva
`H:/sotto`, e a árvore de trabalho desse repo tem trabalho original não comitado.

**Pergunta:** eu faço o push do `feat/build-verify-1` (o clone) mesmo assim, deixando o
trabalho original em paz, ou esperas que o trabalho original seja comitado primeiro?

## Q2 - SPEC 06 escrita, mas sem implementador
`feat/specs-05-07` contém as specs 05, 06, 07 escritas. A 06 não tem implementador
despachado.

**Pergunta:** a 06 é spec de trabalho futuro ou o próximo passo a implementar? Se for, que
prioridade tem relativa à pista de áudio (L7) e ao motor (L5)?

## Q3 - A única hipótese que não dá para testar precisa de mudança de máquina
A lane WGC (L4) mediu que criar a sessão de captura num processo medium-IL dá S_OK
(0x00000000) exactamente como num high-IL - ou seja, o acesso NÃO é o que está a falhar.
A hipótese medium-IL ficou INTESTÁVEL nesta máquina, com a causa medida: EnableLUA=0,
conta RID 500, `seclogon` STOPPED, 0 de 230 tokens são medium-IL.

Para a testar uma das duas mudanças de caixa inteira: EnableLUA 0->1 com re-logon, ou arrancar
o serviço `seclogon`.

**A minha recomendação medida: NÃO AGORA.** Um re-logon derrubaria as 16 lanes vivas, o
wake de 3 minutos e o rasto de auditoria a meio do trabalho, e o arm-4 já mediu que o acesso
não é o problema. Fica registado como OPEN-UNTESTABLE.

**Pergunta:** autorizas a mudança alguma vez? Se sim, quando (e eu paro tudo antes)?
**NOTA-RESPONDIDA-POR-MEDIÇÃO 2026-10-10 - a hipótese medium-IL está MEDIDA e a resposta é NÃO: o acesso
NÃO é o que está a falhar num processo low-IL, e a causa medida é OUTRA (AUDIT-FINDINGS F18).**
Todas as imagens executáveis debaixo de `H:\sotto` carregam o rótulo mandatório `S-1-16-4096`
(Low integrity), explícito na raiz e herdado. Um executivo assim arranca um processo LOW-IL, e um processo
LOW-IL NÃO consegue criar um item de captura WGC para uma janela MEDIUM/HIGH - daí `0x80070005` em
`CreateForWindow` para os 4 alvos nomeados, em `CreateForMonitor`, e até na própria janela do probe.
Medido nos dois sentidos com OS MESMOS bytes: 5 de 5 `S_OK` fora de `H:\sotto` e 5 de 5 `0x80070005`
dentro, e o controlo scratch moveu a resposta nas duas direcções (retirar o rótulo -> `S_OK`, pôr ->
`0x80070005`). O rótulo segue o OBJECTO ficheiro, não a cadeia de caminho. Por isso **nenhuma das duas
mudanças de caixa acima é necessária para explicar a recusa** - e a minha recomendação continua NÃO AGORA,
agora apenas por causa do custo (deitar abaixo as lanes vivas, o wake e o rasto de auditoria a meio).
Fica **OPEN-UNTESTABLE** no que respeita à hipótese medium-IL em si, e MEDIDA no que respeita à causa da
recusa WGC.

**O que continua DESCONHECIDO e é assunto teu:** quem pôs o rótulo `S-1-16-4096` nesses ficheiros não
está medido. Também não estão medidos: `GraphicsCaptureAccessStatus` nunca foi lido e o diálogo de
consentimento nunca apareceu. O mesmo exercício está em
`_main/receipts/receipt-29-review-wgc-instrument-contradiction.md` §10 (untracked, ver Q8).


## Q4 - O relógio do .mp4 não existe (lacuna das specs)
O nosso escritor de mp4 escreve `creation_time`/`modification_time` como **0,0 literal**
(`mp4_writer.cpp:257,272,293`), e o moov não traz relógio de parede. Para um ficheiro de
biblioteca estrangeiro não existe "início" intrínseco nenhum.

**Pergunta:** qual é a fonte da verdade do instante de um clip? A ordem que eu meço
clip-id > key.json > db > container > mtime é razoável, ou o dono quer outra (ex.: sempre
mtime, ou nunca mtime)?

## Q5 - POLÍTICA DE DUPLICADOS NÃO EXISTE
Censo de hoje: "duplicate room"/dup-room/room_dup = **ZERO ocorrências na árvore**. A
única política escrita é o overlap do ASR (0,10 s de cada lado, `specs/02-asr.md:165`).
O instrumento que eu vou correr imprime DUPLICATE ROOM POLICY: NONE WRITTEN IN THIS TREE.

**Pergunta:** qual é a regra - só intervalo sobreposto por mais de 0,10 s? por content_key?
por hash de vídeo? Nunca deduplicar?

## Q6 - ORÇAMENTO DO RING (C4), agora com medição
A máquina: 47,74 GiB, 53% livre. A regra medida da lane-C: teto = min(4 GiB, 25% da RAM
total, 50% da RAM disponível) - hoje dá 4 GiB. O piso de 256 MiB é inalcançável aqui.

**Pergunta:** 4 GiB numa máquina de 47,74 GiB (8,4%) é o preço certo, ou queres o teto
mais baixo?
## Q7 - QUATRO FICHEIROS DE PLANO EXISTEM FORA DO GIT
A rectificacao do receipt clip-to-asr (`927e724`) registou o facto e o seu §13 aponta para esta
pergunta: `runs/P4-aireplay-clip-to-asr.md` (5 089 B / 143 linhas, mtime 2026-10-08T22:04:07.458Z)
EXISTE e e `Status: SPEC - ready for implementation`. Existem mais tres irmaos na mesma pasta
`runs/`: `P4-aireplay-engine-process.md` (5 908 B), `p4-aireplay-status.md` (10 597 B) e
`P4-aireplay-wgc-unblock.md` (4 949 B). Os quatro estao UNTRACKED (`??` no git status do repo
aninhado) - trabalho real que nenhum commit captura.

**A minha recomendacao medida: comita os quatro.** Um plano que existe em disco mas nao em git
nao tem janela nem populacao: pode ser apagado por um `git clean` sem deixar rasto, e nenhuma lane
consegue cita-lo com um sha. O risco de os comitar e zero - sao quatro ficheiros markdown novos,
nenhum caminho partilhado, nenhum ficheiro existente tocado. O custo de os NAO comitar ja foi pago
uma vez: a secao 11 do receipt-20261009-clipasr.md disse que o ficheiro nao existia, e isso era
falso. A mentira nasceu de um plano fora do git.

**Pergunta:** comito os quatro `runs/P4-*.md` tal como estao (nenhum deles foi revisado por uma
lane), ou preferes rever primeiro? E `p4-aireplay-status.md` (minusculo, 10 597 B) e um quarto
plano ou um relatorio de estado - porque isso muda o commit message?

## Q8 - OS TRES FICHEIROS DO GATE AUDIT EXISTEM FORA DO GIT, e o commit que os "guardava" nunca existiu
Medido 2026-10-10. `_main/_gate-audit/gate-verdict-matrix.md` (17 565 B, mtime
2026-10-09T23:18:50.203Z), `_main/_gate-audit/HONEST-BASELINE.md` (13 066 B, mtime
2026-10-09T23:20:34.686Z) e `_main/_gate-audit/DO-NOT-RUN.md` (13 484 B, mtime
2026-10-09T23:30:34.185Z) existem em disco e nenhum deles esta em commit nenhum:
`git log --all -- _moved/aireplay/_main/_gate-audit/` e `git ls-files` devolvem vazio, e o repo
aninhado reporta `?? _main/_gate-audit/`.

No repo pai eles estao IGNORADOS, e vale a pena explicares porque isto voltou a acontecer:
`.gitignore:105` (`_moved/aireplay/_main/*/`) casa apenas DIRETORIOS. Por isso os ficheiros
directamente em `_main/` (AUDIT-FINDINGS, DEBT-LEDGER, TO-BE-ANSWERED-BY-OWNER) comitam sem
`-f`, mas cada subdiretorio — `logs/`, `receipts/`, `runs/`, `src/`, `_gate-audit/` — precisa de
`git add -f`. Foi exactamente isto que deixou os recibos e os logs fora ate hoje.

**E a razao porque a linha do DEBT-LEDGER os dava por aterrados esta agora medida, nome e tudo:**
a linha D-GATE-AUDIT citava o commit `f4ca6691`. `git cat-file -t f4ca6691` devolve
`fatal: Not a valid object name` nos DOIS repos. E a identidade desse id nao e um mistério:
`f4ca6691` sao os primeiros 8 caracteres hex de um ID de subagente —
`f4ca6691-20f6-4718-aa5f-13d303894f08`, "Phase G - per-gate aggregate verdicts", filho desta
sessao, INACTIVE. Nunca foi um commit. O erro foi de categoria: o id curto do proprio agente que
escreveu os ficheiros foi citado como commit, e isso fez o trabalho parecer ja aterrado — que e
como um erro de categoria se disfarca de "nada a fazer". Isto e DIFERENTE do F16.9 (la havia um
commit que perdeu a casa; aqui nao havia casa nenhuma).

**A minha recomendacao medida: comita os tres com `-f`.** O que eles contam e prova — o proprio
DEBT-LEDGER rele o agregado e confirma que quatro alegacoes sobrevivem e duas foram corrigidas
para F13. Nao os aterrar custa: nenhuma lane os pode citar com um sha, e um `git clean` leva-os
sem deixar rasto. Aterrar custa tres ficheiros markdown novos e um `-f` — e o commit message tem de
dizer que estao ignorados por causa de `.gitignore:105`, senao a proxima pessoa acha que o `-f`
foi engano. Nao ha caminho partilhado com nada existente.

**Pergunta:** comito os tres com `git add -f` tal como estao, ou preferes rever primeiro? E nota
que `HONEST-BASELINE.md` tem um numero que ja sei estar errado (a sha do bateria foi medida de
novo em 2026-10-10) — queres que o corrija no mesmo commit ou que o deixe como evidencia do que
a lane mediu nessa altura?

---

## RESPOSTAS 2026-10-10 — o dono autorizou "push and take all decisions and continue with everything"

Todas as respostas abaixo são minhas (do agente), tomadas com essa autorização, e cada uma carrega a
medição em que assenta. Nenhuma foi decidida por impressão. A Q1 já estava respondida por ti e está
feita. Quando uma resposta cria trabalho novo, esse trabalho fica nomeado como tarefa de lane e não
como decisão.

### Q1 — O PUSH: respondido por ti e FEITO
Push executado 2026-10-10 (`e36964e..40f5a35`). Tudo o que aterrou desde então — os 3 ficheiros do
gate audit, os 4 planos, o receipt-29, o probe p95, mais o trabalho de design do produto original
que veio de outra lane — está na mesma branch e já em `origin/feat/build-verify-1`.

### Q2 — SPEC 06: fica escrita; L5 (motor) e L7 (áudio) aterram primeiro
Decisão: a 06 **não** é o próximo passo a implementar. Fica como spec escrita, e a prioridade é L5 e
L7 antes dela. Motivo medido, não preferência: L7 acabou de aterrar com prova de instrumento — o
`ffprobe` dum corte real dá uma segunda pista `aac` a 48 kHz estéreo com o ASC no `esds`, o MFT de
AAC é criável nesta máquina, e a reconstrução do commit é idêntica ao binário embarcado em 19 de 19
secções (só `TimeDateStamp` e o `CheckSum` do PE diferem). L5 é o motor sem o qual nada do resto liga. E
a 06 depende das 05 e 07 — a 07 é a spec do motor — portanto implementar a 06 antes do motor seria
construir sobre nada. POP/JANELA: estado do repositório em 2026-10-10, parent `feat/build-verify-1`.

### Q3 — MUDANÇA DE CAIXA: não, e já não é necessária
A pergunta era "autorizas a mudança alguma vez?". A resposta é **não**, e a razão mudou: **não é
preciso mudança de caixa nenhuma para explicar a recusa**, porque a causa medida é o rótulo
`S-1-16-4096` (Low integrity) nos ficheiros, não a política. As duas mudanças (EnableLUA 0->1 com
re-logon, arrancar o `seclogon`) só serviriam para testar a hipótese medium-IL, que fica
**OPEN-UNTESTABLE** — não to peço. O que continua teu é o desconhecido: quem pôs o rótulo. Por
medir: `GraphicsCaptureAccessStatus` nunca lido; diálogo de consentimento nunca visto. BOUND: um
host, uma conta admin elevada, `EnableLUA=0`.

### Q4 — RELÓGIO DO CLIP: mantém a ordem medida; mtime só corrobora
Decisão: fica **clip-id > key.json > db > container > mtime**, e o **mtime é corroboração apenas,
nunca fonte da verdade** — porque muda com `git clean`, com cópias e com backups, e um clip cujo
instante dependa do mtime perde o instante no primeiro `cp`. O `container` (moov) hoje não traz
relógio de parede (`mp4_writer.cpp:257,272,293` escreve 0,0 literal); isso fica registado como
lacuna das specs, não como decisão. POP/JANELA: lido em `src/capture/mp4_writer.cpp`, árvore de
2026-10-10.

### Q5 — DUPLICADOS: por `content_key`, nunca por intervalo sozinho
Decisão: a política é **duas condições juntas** — (1) `content_key` igual e só então (2) o intervalo,
com o overlap de 0,10 s já escrito em `specs/02-asr.md:165`. **Nunca dedup por intervalo sozinho**:
fundiria duas gravações diferentes do mesmo minuto (duas janelas, dois monitores) e apagava uma.
**Nunca por hash de vídeo**: o mesmo conteúdo capturado duas vezes é o caso em que queres duas
entradas na biblioteca. POP/JANELA: censo de 2026-10-09 — "duplicate room"/dup-room/room_dup = ZERO
ocorrências na árvore; o instrumento continua a imprimir `DUPLICATE ROOM POLICY: NONE WRITTEN IN THIS
TREE` até a política ser escrita.

### Q6 — ORÇAMENTO DO RING: a regra medida, com o preço saído da RAM do sistema
Decisão: **teto = min(4 GiB, 25% da RAM total, 50% da RAM disponível)**, hoje 4 GiB (8,4% de 47,74
GiB). O piso de 256 MiB fica **inalcançável e é removido da regra** em vez de cumprido por decreto:
o piso real é o do código, `ring_buffer.cpp:78` rejeita menos de 16 MiB. E esta decisão carrega um
defeito a corrigir, que é a razão de a tomarmos agora: a lei 7 dos aireplay diz que o orçamento do
ring sai da RAM do **sistema**, e `d3d11_ctx.cpp:70` tira-o da VRAM dedicada (998,69 MiB), dando um
teto de ~62 MiB sobre uma arena que é RAM. A correção é tarefa de lane, não desta decisão.
POP/JANELA: medido 2026-10-10 pela lane-C; caixa 47,74 GiB.

### Q7 — OS QUATRO FICHEIROS DE PLANO: comitados, e um deles não é plano
Feito em `5b8ddd7`, com caminhos explícitos. Resposta à tua segunda pergunta:
`p4-aireplay-status.md` **não é um plano**, é um **relatório de estado** — o cabeçalho diz "# P4 —
AIREPLAY PROJECT STATUS", Lane: aireplay (inspection), Owner: absent (11 prompts), data 2026-10-08.
Não tem `Status: SPEC` nem lane própria, por isso **não entra na fila de trabalho**, e os seus
números são um retrato de 2026-10-08, a reler contra o DEBT-LEDGER antes de serem acreditados. O
commit message diz exactamente isso. Os outros três são SPEC abertos; o do WGC tem a pergunta
"porquê `0x80070005` quando a política parece permitir" **respondida por medição** (F18 +
receipt-29): a caixa não recusa por política, recusa pelo rótulo LOW, e o braço de correcção como
está escrito precisa de uma mudança de máquina que não autorizas — por isso aterrou como registo da
pergunta, com o "porquê" resolvido e o "o que fazer" aberto.

### Q8 — OS TRÊS FICHEIROS DO GATE AUDIT: comitados com `-f` e corrigidos por acréscimo
Feito em `2f9071c`, com dois companheiros: receipt-29 em `c0581e0` e o probe p95 em `19a031c`. A
razão do `-f` está no commit message: `.gitignore:105` (`_moved/aireplay/_main/*/`) casa apenas
DIRETÓRIOS, logo cada subdiretório do `_main/` precisa de `git add -f`. Sobre o número errado —
**corrigi por acréscimo, não reescrevi**: o `HONEST-BASELINE.md` ganhou uma secção 14 datada de
2026-10-10 que diz qual era a frase falsa ("p95 ... no run yet": hoje é falso, o instrumento existe e
correu, F16.7) e deixa a frase original de pé. E uma confirmação medida, porque eu esperava que a sha
da bateria estivesse errada e **não estava**: `_main/build/aireplay-capture.exe` dá
`6CADE9A3...A05296` hoje, 783 865 B — a linha do binário continua VERDADEIRA, e a linha do
instrumento de registo (`run_battery.ps1`, 28 309 B / 436 linhas) é exactamente verdadeira. A única
linha falsa era a do p95. O `f4ca6691` fica registado como o que é: um id de subagente citado como
commit — erro de categoria, não commit perdido.

### O que continua em aberto depois destas respostas
Quem pôs o rótulo `S-1-16-4096` (teu, por medição — não adivinho). O veredicto do revisor do probe
p95 (L18), ainda em voo. As lanes L5 e L6, e os revisores que faltam à wave-2 (L5, L6, L7, L18 pela
regra 4). E o WGC continua sem um único fotograma capturado: F18.8 mede a CRIAÇÃO de itens, nunca
uma sessão inteira.
