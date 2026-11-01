# Protocolos de observabilidade e debugging aplicados ao Sotto

**Data:** 2026-10-23 · **Estado:** em vigor, na bateria (`_main\_audit-verify-all.cmd`)

Este documento responde a duas perguntas tuas numa: *"me fala todos os protocolos novos que aplicou no
Sotto pra melhorar a observabilidade e debugging"* e *"`fewer trips to memory` — o que é possível nesse
projeto sobre essa frase?"*.

A regra que atravessa tudo: **uma afirmação sem instrumento e sem data é uma opinião com prazo de
validade.** Cada protocolo abaixo existe porque uma afirmação dessas já custou trabalho refeito neste
repo.

---

## 1. Modo BUG-HUNT obrigatório (11 passos)

Em `AGENTS.md`, secção *"MODO BUG-HUNT — OBRIGATÓRIO, SEMPRE, PARA QUALQUER DEFEITO REPORTADO"*.
Quando reportas um defeito, o trabalho **é** bug-hunt, e os artefactos são exigidos por portões, não por
gosto: entrar e nomear o cluster · triar observações (esperado vs observado, com as tuas palavras verbatim)
· reproduzir com log guardado em ficheiro · **uma hipótese + o que a refutaria** · minimizar (delta
debugging) · corrigir a **classe** e varrer os irmãos com a mesma sonda · regressão no estilo certo ·
provar o detector (o braço negativo tem de derrubar **aquele** braço) · cobertura por invocador ·
replay + revisão independente · cápsula de incidente + `recurrence-watch`.

## 2. Ledger de bugs com máquina de estados

`_main/bug-ledger.json` + `_main/bug-ledger-oracle.py` (**9 mutantes**).

Estados: `reported → reproduced → cause-isolated → fixed → verified → recurrence-watch`.

O que o portão **recusa** (cada um é um mutante):
`fixed` sem um passo da bateria · `verified` cujo verificador é o próprio autor · hipótese sem
falsificador · reprodução sem ambiente / revisão / identidade do artefacto (`artifact_sha` de 64 hex, ou
`unrecorded` **com nota**) · `fixed` sem varrer irmãos · `unknown` sem próximo passo.

Imprime em letras grandes **`FIXED, NOT VERIFIED`** — para ninguém ler um fecho que não houve. Métricas
impressas: tempo-até-reprodução, correcções com braço negativo na bateria (**3/3**), irmãos não provados
(**3**, nomeados).

## 3. Cobertura por INVOCADOR, não por teste

`_main/seam-inventory.json` + `_main/seam-coverage-oracle.py` (**9/9 provados**, 3 mutantes do inventário).

A definição que passou a valer:
`invocadores com controlo positivo a passar E negativo a falhar NAQUELE braço / invocadores enumerados`.
Um invocador sem os dois **bloqueia a entrega**. Foi um inquérito de invocadores — não um teste a mais —
que encontrou três caminhos desprotegidos no seam do rato (o `stop`, o `WM_HOOK_SYNC` entre threads e um
segundo tipo de hook de teclado).

## 4. O seam do input (a cura do teu rato)

`_main/input-path-oracle.py` — **10 braços / 10 mutantes**: instalação preguiçosa (só com painel visível
ou edit mode), `armed`/`edit_mode` como **propriedades** (ninguém muda o estado sem mexer no hook),
auto-cura por `WM_TIMER` de 5 s, `KillTimer` no `stop`, e o outro tipo de hook proibido.

A lei que ficou: qualquer coisa que o Sotto meta no **caminho de input ou de composição** do Windows tem de
ser medida **pela ausência** — provar que não existe quando o produto está parado.

## 5. Ciclo de vida do worker (ORDEM 3)

`_main/external-resume-oracle.py` — **8 braços / 8 mutantes**, cada mutante a derrubar **o seu** braço:
shell a morrer · release sem park · em pausa · escondido · a legenda conta como visível · piso de 45 s ·
caminho feliz · depois do piso.

E a lição de método: o `AGENTS.md` dizia que este método **não** trazia o worker de volta. Re-medido, traz.
**O buraco não era código — era prova.** Um documento que descreve um buraco já fechado manda trabalho para
o sítio errado.

## 6. Ratchet de saúde do código

`_main/code-health-oracle.py` + `_main/code-health-baseline.json` (43 ficheiros de produto, **3 mutantes +
controlo positivo**).

Mede por ficheiro: `bytes`, `linhas`, `defs`, `classes`, **função mais longa**, `except-pass`, `global`.
**Qualquer aumento é vermelho; reduzir é sempre verde.** Um ficheiro novo é permitido (extrair é a cura)
até 120 000 B — acima disso é mudança de sítio, não refactor.

Medição de partida (é o plano, não a opinião): `sotto_webview.py` **758 679 B / 13 273 linhas**, `main` do
worker **2 297 linhas**, **82** `except: pass`, **10** `global`.

## 7. Higiene de excepções, classificada pela função que a contém

`_main/exception-hygiene-oracle.py` + censo AST que atribui cada `except: pass` à **função** onde vive.
Resultado: **47 silêncios, 0 no teu caminho** (mostrar/esconder painel, arrancar worker, hotkey, histórico);
os 7 "críticos" são `stop`, `_uninstall_hook` e `nvmlShutdown` — teardown, onde engolir é o comportamento
certo — e cada um tem um `log()` logo a seguir.

## 8. Intenção declarada de ferramenta

`_main/tooling-intent-oracle.py` + baseline (**160** herdados, **4 mutantes + controlo positivo**).

Uma ferramenta nova em `_main` tem de declarar `# BLOCKS: BUG-…` (com o id a **existir** no ledger) ou
`# NO-BUG: <razão>`. A dívida não pode crescer.

**Provou-se contra o autor:** escrevi `# BLOCKS: BUG-20261021-03` num oráculo novo; o ledger tem
`BUG-20261023-03`; o portão ficou vermelho (`tooling-intent=2`) e a bateria recusou. É o comportamento
certo.

## 9. Cache incremental por CONTEÚDO, com o que corre e o que não corre declarado

`_main/_stepcache.py`, estado `_cache/battery-steps.json` (**115 passos**, 67 448 B).

Por passo: fingerprint do **conteúdo** das dependências (não do mtime) + `log_sha256` + `rc` + `elapsed_s`
+ carimbo. Três classes:

- **normal** — não corre se o conteúdo não mudou;
- **`heavy`** — abre o teu ecrã, o teu dispositivo de áudio ou a GPU: **não corre** sem
  `SOTTO_BATTERY_HEAVY=1`, e quando não corre é **`skipped`**, nunca `gate`;
- **`always`** — a população é um *directório* (`skip-verdict-guard`, `code-health`): uma lista de
  dependências nunca estaria completa, logo um cache seria um falso verde.

Marcação de tempo real: **`WALL_S=33.0`** com **100/115** em cache; soma de `elapsed_s` de todos os passos
**448,1 s**; modo rápido medido **27,7 s**.

## 10. Vocabulário do veredicto (jidoka: desconhecido ≠ verde)

`BATTERY-VERDICT` + exit code, e **só um** `steps=`:
`gate`, `control`, `expect-red`, `skipped`, `heavy`, `missing`, `cached`.
**Um passo saltado não é um portão que passou** — o `skipped=` é a prova, e o veredicto nomeia os saltados
um a um.

## 11. Braço negativo executado, sempre

Todo o portão novo nasce com `--neg-arm` que **corre** (`NEG-ARM PASS`, rc=1 por desenho) e **entra na
bateria** como passo `expect-red`. Um braço negativo fora da bateria é um mutante a que ninguém volta a
olhar.

## 12. Cápsula de incidente + `recurrence-watch`

`_main/incidents/INC-20261023-01-mouse-hook.md`: esperado/observado, invocador, revisão, config,
reprodução, fronteira, primeira divergência, condições contribuintes, acção com estado final + teste de
escape. O `recurrence-watch` tem **instrumento e janela** — não "vamos ficar atentos".

## 13. Profiler real (novo hoje)

`_main/sotto-profile.py` — `py-spy` 0.4.2, pilhas a 100 Hz, sem carregar código no alvo.

- `--selftest` **pode falhar** (arranca um filho com uma função de nome conhecido e exige vê-la no topo):
  `amostras=394 | PASS`.
- `--spawn` (funciona sempre) e `--attach` (só de uma sessão interactiva e não elevada).
- **Quatro defeitos meus, encontrados por o usar:** `--output -` vazio nesta build; a família dava 0
  processos porque o `CommandLine` de um processo lançado por `schtasks` vem **vazio** (curei semeando
  pelos `pid=` do log); `0 amostras` porque o py-spy só amostra threads activas (falta `--idle`); e o erro
  do py-spy vai para **stdout**, que eu estava a descartar.

Primeira medição real: worker offline **86,7 s frio / 50,6 s quente**, com **60,5 % → 14,9 %** em
`og.Model`, **32 % → 62,6 %** a criar as três sessões, e **apenas 3,6 % → 12,2 % a transcrever**.
E o próprio worker diz: `load_s=22.8`, `load_phases_s: encoder 19.013, decoder 0.209, joint 0.116`.

## 14. Declarar o que NÃO está medido

Secções *"POR MEDIR / NÃO ATRIBUÍDO"* e *"o que este revamp NÃO faz"*. Exemplos actuais: o arranque sob o
profiler; o perfil do lado JS do painel; a contradição do flash do painel (0/20 vs 18/20); os 6 passos
pesados que não correm por omissão; e o facto de `verified` ser **impossível** a partir de uma lane (sem
verificador independente e sem corrida real da app).

---

## 15. `fewer trips to memory` — o que é possível neste projecto

A frase tem três leituras neste repo, e as três são accionáveis. Nenhuma delas é sobre "escrever menos".

### 15.1 Menos idas à memória HUMANA (a tua e a minha)

O problema real: facto medido ontem, esquecido hoje, re-medido amanhã — ou pior, **citado de cor e errado**.
Aconteceu duas vezes nesta sessão com o mesmo ficheiro: o `AGENTS.md` dizia que `HKCU\...\Run\Sotto` não
existia (existe), e dizia que o worker não voltava depois da legenda externa (volta).

O que já existe: **pins** (`agents-md-pins-oracle.py` re-mede o `--help` e o `.cmd`), **recibos** com o
comando e a saída, **oráculos** cujo stdout é a prova, e o **ledger**.

O que é possível e ainda não está feito:
1. **Um `sotto facts`** — um comando que imprime os factos medidos **com o instrumento ao lado**
   (`load_s=22.8 (worker: model-loaded)`, `encoder=19.013`), para ninguém os citar de cor.
2. **Uma página de estado gerada** a partir da saída dos oráculos (não escrita à mão): o `AGENTS.md`
   encolhe e passa a apontar para ela.
3. **Uma data obrigatória por afirmação numérica** no `AGENTS.md`, verificada por portão: um número sem
   data é vermelho. Isto é o mesmo padrão do `BLOCKS:`/`NO-BUG:`, aplicado à prosa.

### 15.2 Menos idas à memória do PROCESSO (RAM) — e aqui há um achado

O perfil mostrou **duas cargas dos mesmos pesos**: `og.Model(model_dir)` (60,5 % frio) **e** as três
`InferenceSession` a ler `encoder.onnx` / `decoder.onnx` / `joint.onnx` (32 % → 62,6 % quente). O
`peak_rss_mb` do worker é **785 MB** para um modelo de 747 MB, e o estado benigno já foi medido com
`private 3070 MB` (páginas *trimmed*, memória comprometida).

O que é possível, por ordem de preço/benefício:
1. **`session.use_ort_model_bytes_directly=1`** — os pesos vão do ficheiro directo para a sessão em vez de
   serem copiados para o heap. Já está no código atrás de `SOTTO_LOAD_AB=bytes`, **à espera do A/B**
   (3 corridas de ~30 s; o resultado decide, não eu).
2. **Perceber se o `og.Model` precisa dos pesos todos** ou só do front-end mel/VAD. Se só precisa do
   front-end, os 747 MB estão a ser lidos duas vezes e a cura é estrutural, não um travão de ORT.
3. **`private 3070 MB` com `rss 21 MB`** — o modelo não é libertado no estado benigno. Medir com
   `EmptyWorkingSet`/`SetProcessWorkingSetSize` e um *unload* explícito quando o worker entre em silêncio
   benigno.
4. **Orçamento de memória por processo, impresso no log** (rss, private, working set) em cada transição de
   estado — para a memória deixar de ser invisível no log.

### 15.3 Menos idas ao DISCO (o que já está medido e o que falta)

O contraste frio/quente é **86,7 s → 50,6 s**: **36 s** de puro cache de disco. O preload existe para isso
(paga o custo quando estás inactivo, com tecto de 120 s), e o `PROCESS_MODE_BACKGROUND_BEGIN` existe para
o load não competir contigo.

O que falta: medir o arranque **sob o profiler** (app fechada → `py-spy record -- pythonw
sotto_webview.py`), que é a única medida que fecha o *"abrir o Sotto trava o PC"*.

---

## O que estes protocolos NÃO resolvem (declarado)

- **`verified` continua impossível de uma lane** — sem verificador independente e sem corrida real da app.
- **Mutantes provam afirmações sobre mutações escolhidas**, nunca a completude de um inventário.
- **O relógio do produto não é o relógio dos testes**: hoje, três largadas minhas deram app surda, app sem
  WebView2 e app morta em silêncio — e o perfil de repouso chamou "repouso, 7 threads paradas" a uma app
  que estava **encravada**. Um instrumento que não distingue "parado" de "encravado" ainda não é um
  instrumento de saúde.
