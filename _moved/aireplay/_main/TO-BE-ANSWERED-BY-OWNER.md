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
