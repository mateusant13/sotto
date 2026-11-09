# RECIBO — o fio quente que a DM de stutter nomeou, e a classe que o deixou passar

Medido nesta máquina, hoje (2026-11-09). Dois DMs independentes acusaram a mesma árvore
(`watcher` 15:28, `w12:p7` 15:3x), e ambos apontavam **um** fio: `tid=20408`, 12,81 s de
20,7 s de janela.

## 1. O culpado, nomeado

| medida | instrumento | valor |
|---|---|---|
| processo vivo ANTES | `_main/shell-thread-cpu.py` e `shell-thread-budget-oracle` | `pid=50452 total=102,2 % de um núcleo`, `sotto-caption-tick tid=20408 = 86,3 %` |
| idade do código dele | `live-code-freshness-oracle.py --strict` | `STALE`, `pid=50452 started=08:14:03`, **17 ficheiros** com mtime posterior |
| processo vivo DEPOIS | `_main/shell-thread-cpu.py 33676 --seconds 8 --top 8` | `pid=33676: 48 fios, 13,0 % de um núcleo no total`; o fio mais quente é `sotto-yt-track` a 5,3 % |

O fio chama-se `sotto-caption-tick` (`app/webview/caption_overlay.py`, `_arm_tick`/`_tick_loop`).
A instância do dono corria o código **anterior** à cura do orçamento de pintura: o laço pedia um
quadro a cada `word_fade.FRAME_S` sem olhar ao custo, e a pintura custa **11,6 ms p50** no tamanho
real da caixa — um piso de ~69–100 % de um núcleo por construção. O código do disco já tinha a
regra: `periodo = custo / CAPTION_FRAME_BUDGET` com `CAPTION_FRAME_BUDGET = 0,40`
(`_limit_by_paint`), e é essa a diferença entre 102,2 % e 13,0 %.

**A cura é a instância nova, não um patch novo.** O que faltava era o processo ler o disco:
`_main/sotto-relaunch.py --relaunch --tag "watcher-dm-16bb006e"` matou o pid 50452 (identidade
pelo mutex do próprio log) e largou `runner=run.cmd` com o token de 13676; o pid **33676** ganhou
a mutex às 15:34:59 e a etiqueta dele é `88A0ED7098DB`, a do disco.

## 2. O que a instância nova mostrou em 15 segundos de vida

```
YOUTUBE_PAINT_READ_FAILED error=NameError("name 'source' is not defined")   x ~15 em 2 s
```
`app/webview/sotto_webview.py`, ramo da foto VELHA (`cdp-stale`): `self._yt_health_tick(source, …)`
usava um nome que é **parâmetro de outra função** do mesmo ficheiro. A excepção era engolida pelo
`except` exterior **antes** de entregar `got`, portanto enquanto o snapshot aquecia nenhuma linha
chegava ao ecrã — e o log escrevia uma linha por tick (10 Hz = 10 escritas/s).

**Porque nenhum portão o viu:** `_main/undefined-names-oracle.py` resolvia nomes por **ficheiro**
("definido em qualquer escopo"), aproximação declarada no próprio docstring. `source` existe como
parâmetro de outra função, logo contava como definido. O mesmo instrumento, agora por **escopo**
(`symtable`, a semântica do CPython), apanhou **dois** nomes no ficheiro:

1. `source` (acima);
2. `external_subs._window_title(hwnd)` em `_yt_identify` — módulo **nunca importado naquele escopo**
   (o ficheiro importa-o localmente em 3494, 3778 e 4039). O `except: pass` engolia-o, e a cura do
   desempate de **duas abas `watch`** que aquela linha existe para fazer **nunca corria**
   (`YOUTUBE_CDP_SOURCE state=ambiguous` era o sintoma documentado).

Depois das duas curas: varredura escopada = **0 nomes** nos 19 ficheiros de produção.

## 3. Custo no caminho do arrasto (mesma classe, outro sítio)

`_set_strip_offset` fazia `log(...)` **por movimento** — medido antes, 277 movimentos em 1,86 s
(~149/s), e cada `log()` escreve no stdout **e** enfileira para o ficheiro. Agora: uma linha na
primeira amostra e uma no `end`, com `moves=` (o número que interessa). O oráculo do arrasto mede
`A7 zero-log-por-amostra` (0 linhas / 67 amostras).

## 4. Portões — medidos, com o braço negativo

| portão | resultado |
|---|---|
| `caption-overlay-theme-oracle.py` | `VERDICT: PASS (9/9)`; `--neg-arm` **4/4** mutantes (`criacao-veste-o-desenho` incluído) |
| `panel-history-wheel-probe.mjs` | `PROBE GREEN` (W2 1:1, W3 rajada ×6,86, W4 pressão do meio); `--neg-arm` **3/3 RED** |
| `undefined-names-oracle.py` | `GREEN — 19 ficheiros, 0 nomes`; `--neg-arm` **3 mutantes** (nome não importado, parâmetro de outra função, módulo sem import) |
| `window-drag-oracle.py` | `VERDICT: PASS (9/9)`; `--neg-arm` `PASS` |
| `agents-md-pins-oracle.py` | `PASS — 2 pin(s) checked live` |
| `battery-wiring-oracle.py` | `PASS checks=7 fail=0` — `ligados=170 sem_passo=109 populacao=279` |
| `battery-record-pairing-oracle.py` | `PASS — 419 passos, 419 nomes com registo, 0 achados` |
| `battery-class-oracle.py` | `PASS — arms=3 fail=0` |

## 5. O que NÃO está provado

- **A taxa do arrasto numa máquina carregada.** `A6 taxa-entregue` media 222,2 Hz (RED) e 239,9 Hz
  (GREEN) no mesmo minuto, com a caixa a 81 % de CPU. O piso passou a **200 Hz** com a razão escrita
  no código: o braço existe para apanhar a regressão de 60 Hz, não o escalonador do Windows.
- **A metade `insufficient-integrity` da DM.** O watcher não consegue despromover esta árvore
  (`winerror 5`) porque a app corre a integridade `high`. A alternativa (a) da DM — relançar
  NÃO-elevada — está medida como impossível nesta caixa: um filho `medium` falha
  `WEBVIEW2_INIT_FAILED 0x80010108` e `TRAY_ICON_ADD winerror=5`. Fica registado, não corrigido.
- **A tela do dono.** O painel não foi aberto por esta lane; `verified` continua a exigir a mão dele.

## 6. Rodada 2 (2026-11-09, 19:0xZ) -- a DM de stutter que nomeava o pid 33676

DM `dm-79d1e980` (watcher): `pythonw.exe(33676)` como maior pressao, `cpu 8,1 % da maquina`
(20 nucleos) e "1 processo da arvore despromovido". Medido, nesta arvore:

| instrumento | comando | resultado |
|---|---|---|
| per-thread, projeto | `python _main/shell-thread-cpu.py 50452 --seconds 8` | **102,2 % de um nucleo**, `sotto-caption-tick tid 20408 = 86,3 %` |
| per-thread, projeto | `python _main/shell-thread-cpu.py 33676 --seconds 8` | **13,0 % de um nucleo**, mais quente `sotto-yt-track 5,3 %` |
| per-thread, watcher | `python -m watcher profile 33676 --seconds 20` | `22,7 % de um nucleo = 1,1 % da maquina`; atribuicao por fio **CANNOT-MEASURE** (psutil devolve 0 tids; sem py-spy) |

O `8,1 %` da maquina sao **~162 % de um nucleo**, ou seja PICO -- e o pico tem nome no log da
propria shell (`_main/webview-run.log`):

```
15:44:36.228 BRIDGE_SILENT ms=30000 pid=54592
15:44:36.245 BRIDGE_ALIVE WORKER_ALIVE seq=3944 phase=window age_ms=39657
15:44:36.950 BRIDGE_KILLED pid=54592 rc=1 why=the-shell-terminated-it
15:45:39.038 BRIDGE_LOAD_MS ms=61781 pid=47096 worker_load_s=59.51
```

A janela de 30 s expirou **com um batimento em voo** (chegou 17 ms depois) e o respawn custou
**61,8 s a reler 1,9 GB**. Tres curas no commit `783c912`, e os numeros de antes/depois sao os de
cima: (a) `_on_silence` pergunta antes de matar (`silence_grace_s`, 10 % da janela) -- oraculo
`worker-silence-grace-oracle.py` 5/5 + `--neg-arm` a apanhar A1/A2; (b) `log()` deixou de escrever no
stdout no fio do CHAMADOR (o `_pump` era a testemunha do cao de guarda) -- `log-sink-dead-oracle.py`
6/6 + `--neg-arm` 2/2; (c) `_kill_and_restart` carimba `pending_error` -- `restart-30s-oracle.py`
passou de **RED a GREEN**, com `panel-state RED ... named_states_seen=['capture-started','exit',
'spawning']` e `pending_error_samples=24` (antes: 0, a arm estava morta, e o mesmo vermelho aparece no
shell de HEAD -- era defeito do instrumento E da shell).

**NAO VERIFICADO**: nenhuma das tres corre na instancia do dono -- a app esta' fechada e o
`_main/sotto-relaunch.py --relaunch` abortou ("a instancia antiga nao morreu"); `fixed, NOT verified`.

## 7. Rodada 3 (2026-11-09, 19:0xZ) -- a DM que acusava o pid que EU tinha largado

DM `dm-61ee34c4` (watcher): `pythonw.exe(53208)` no pico, `cpu 9,8 % da maquina` (20 nucleos)
sobre 2 processos, sinais `interrupt` + `creation`, `ceiling = NONE PROVED`.

**Quem e' este pid: a minha propria largada.** `_main/sotto-relaunch.py --relaunch` as
16:08:05 (`CreateProcessAsUser(fonte=13676) ok=True child=40172`; o pid que ganhou a mutex,
53208, arrancou as 16:08:06.845). Nao e' um laco da app: e' o ARRANQUE A FRIO que a lane
pediu, e ele correu em paralelo com o `pre-commit` do commit `b22f829` -- dois trabalhos
pesados ao mesmo tempo, exactamente o que a regra da casa proibe.

**A medicao que separa "laco" de "arranque" (mesmo pid, 90 s depois):**

| instrumento | numero | leitura |
|---|---|---|
| `python _main/shell-thread-cpu.py 53208 --seconds 8 --top 6` | **12,4 % de UM nucleo** (0,62 % da maquina), 55 fios | o pico nao continua |
| fio mais quente | `yt-clock` 3,0 %, `sotto-gaming-mode` 2,2 %, `sotto-worker-stdout` 1,3 % | nenhum fio comerrado |
| `python -m watcher profile 53208 --seconds 15` | nenhum tid acima de 0,03 s na janela | nada a rodar |
| `_main/live-code-freshness-oracle.py --strict` | **FRESH** (hash==disco, 0 ficheiro com mtime depois do arranque) | o codigo curado esta' a correr: o worker arrancou as 16:08:07 e carregou em **11 610 ms** (`BRIDGE_LOAD_MS`) contra os **61 781 ms** de 15:45:39 |
| `python -m watcher perf` no mesmo minuto | estolos atribuidos a `ffmpeg.exe(63048)`, `rustc.exe(42272)`, pythons alheios | os estolos do kernel nao sao deste processo |

**A metade que era minha, e a cura.** O `CREATORS` da DM nomeia como maior criador o
`msedge.exe(26576)` x35 com `--user-data-dir=H:\!gravador\state\profiles\capt*` -- outro
projecto, nao esta arvore. `msedgewebview2.exe(6356)` x5 e' o WebView2 desta app. A minha
metade era o trabalho pesado sem tecto: o **`pre-commit` era o unico trabalho pesado desta
casa que se largava SEM Job Object** (a bateria ja' corria em `python -m watcher run --cpu 40`).
Agora ele tambem:

* `scripts/pre-commit` larga `node run-all.mjs` dentro de
  `python -m watcher run --cpu "$HOOK_CPU_CAP" -- ...` (default **40 %** de um nucleo, Job
  Object, os filhos herdam). Medido no commit do proprio patch:
  `job CPU hard cap 40% (children inherit)` + `SUITES 15 passed, 0 failed, 0 unreported`.
* `SOTTO_HOOK_NOCAGE=1` devolve o modo sem tecto e IMPRIME que o fez; um largador ausente
  (rc 2/126/127) imprime `watcher cap unavailable` e corre sem tecto -- um commit nunca e'
  recusado por o tecto nao existir nesta maquina.
* Tecto declarado: **40 % de um nucleo**, fan-out dos suites inalterado (15 ficheiros, um
  `node`). CUSTO DO TECTO, medido no proprio commit que o instalou (`2f95886`), com o box
  carregado por outras lanes: **353,7 s** de parede contra **172,2 s** da mesma corrida sem
  tecto no commit anterior -- **2,05x**, e esse e' o preco de ele ser um tecto. O wrapper
  imprime os dois numeros que provam que o custo nao e' do `node`:
  `wrapper cpu 0,59 s`, `child cpu 0,25 s`, `not-scheduled 0,0 s` e
  `3,4 s outside the observed phases`. `SOTTO_HOOK_CPU_CAP` existe para o subir.

**O que NAO se corta:** o arranque a frio do modelo (11,6 s, `--threads 2`, o mesmo tecto de
fios declarado no argv do worker). Encolher isso e' encolher o produto; o que se faz e' nao
o sobrepor a outro trabalho pesado -- a regra de largura 1 ja' escrita no AGENTS.md.
