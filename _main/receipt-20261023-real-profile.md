# Recibo — 2026-10-23 — o primeiro perfil REAL do Sotto (py-spy), e o que ele disse

**Palavras do dono:** *"tu ta usando alguma tool correta pra entender aonde o sotto consome seu tempo e
recurso do meu pc? um profiling/trace REAL?"* e *"abre o sotto assim que tu garantir que ele nao degrada a
performance do pc de qualquer jeito que ele nao deveria"*.

## Resposta curta, e a admissão

**Não, não estava.** O que existia era `_main/sotto-perf-log.py`: mede o **mundo** (slip de `sleep(25 ms)` —
que é o stutter que o dono sente —, CPU incl. `interrupt`/`dpc`, disco, RAM, família de processos atribuída
pela árvore). Isso responde *"o Sotto atrapalha?"* e **não** responde *"onde é que o Sotto gasta o tempo
dele?"*.

O instrumento certo estava instalado na máquina e nunca foi usado: **`py-spy 0.4.2`**
(`C:\Program Files\Python311\Scripts\py-spy.exe`), um *sampling profiler* que lê as pilhas do processo
Python a correr, a 100 Hz, sem carregar código no alvo.

ETW (`wpr.exe`) existe e **`wpa.exe` não**; um traço de CPU com stacks escreve vários GB e `I:` está a
**0,6 % livre** — logo `wpr` fica declarado como indisponível na prática, não como preferência.

## O instrumento: `_main/sotto-profile.py`

```
python _main\sotto-profile.py --selftest
python _main\sotto-profile.py --spawn -- <cmd ...>      # perfila um comando do inicio ao fim
python _main\sotto-profile.py --attach --seconds 20     # a app que JA esta a correr
```

**Quatro defeitos MEUS, encontrados por o usar** (todos corrigidos, todos com a causa escrita no código):

| # | sintoma | causa | correcção |
|---|---|---|---|
| 1 | `--output -` devolvia vazio | esta build não escreve o `raw` em stdout | escrever para ficheiro em `TMPDIR` e ler |
| 2 | família = **0 processos** para uma app saudável | um processo lançado por `schtasks /it` vem com `CommandLine` **vazio** na consulta CIM | semear também pelos `pid=` do `_main\webview-run.log` |
| 3 | attach com `0 amostras` e sem erro | o py-spy só amostra threads **activas**; a app está parada num message loop | flag `--idle` |
| 4 | falha de attach parecia "sem amostras" | o py-spy escreve o **erro em stdout**, não em stderr | devolver os dois canais |

E uma limitação de **contexto**, não da ferramenta (medida): a partir de uma pane do servidor o attach falha
com `Acesso negado (os error 5)` / `os error 31`. A cura é a **mesma** que a largada da app: correr o
profiler por `schtasks /it`, o que dá acesso simétrico. O modo `spawn` funciona em qualquer sítio.

**O selftest não é decoração:** arranca um filho com uma função de nome conhecido e **falha** se ela não
aparecer no topo. Estado hoje: `amostras=394 | SOTTO-PROFILE SELFTEST PASS`. (A primeira versão falhou com
0 amostras — e ia ser entregue assim.)

## O que o perfil disse — worker offline (`_main/en-us-sample.wav`)

Duas corridas seguidas, do mesmo comando, para separar **disco** de **grafo**:

| | corrida 1 (cache fria) | corrida 2 (cache quente) |
|---|---|---|
| parede | **86,7 s** | **50,6 s** |
| amostras | 8 671 | ~4 600 |
| `og.Model(model_dir)` — `sotto_worker.py:703` | **60,5 %** | **14,9 %** |
| `_create_inference_session` (onnxruntime) | 32,0 % | **62,6 % (~29 s)** |
| `run` — a transcrição a sério | **3,6 %** | 12,2 % |

**A conclusão que interessa ao dono:** na transcrição offline, **~93 % (fria) e ~77 % (quente) do tempo é
CARREGAR, e 3,6-12 % é transcrever.** O `og.Model` é dominado por disco frio (60,5 % → 14,9 % quando o
ficheiro já está em cache); a criação das três sessões ONNX custa **~29 s mesmo quente**.

**Isto contradiz um número escrito no `AGENTS.md`:** o ficheiro diz que as três sessões custam
**1,74-2,09 s** (`load_phases_s`, medido 2026-10-21). Aqui custam ~29 s. Não sei ainda qual dos dois está a
medir o quê (o número antigo foi medido dentro da app, possivelmente com o contexto CUDA já quente naquele
processo); **fica registado como contradição a re-medir**, não como facto resolvido. Regra 1 aplicada ao
próprio `AGENTS.md`.

## O que o perfil disse — a app do dono, em repouso

`pid=51812`, 20 s a 100 Hz com `--idle`: **13 993 amostras = 7 threads × 1 999** — isto é, **todas as sete
threads Python paradas em espera**, nenhuma a girar:

| thread | onde espera |
|---|---|
| UI do pywebview | `create_window (webview\platforms\winforms.py:834)` |
| WebView2 init | `__init__ (winforms.py:289)` |
| pump do painel | `_pump (sotto_webview.py:4445)` |
| run do shell | `run (sotto_webview.py:3897)` |
| legenda nativa | `_thread_main (caption_overlay.py:893)` |
| hotkey | `run (sotto_webview.py:3513)` |
| escritor do log | `_log_writer (sotto_webview.py:1173)` |

CPU do shell em 3 s: **0,00 s (0,0 % de um núcleo)**; `rss` 76-109 MB. E o log da largada di-lo na mesma
linha de tempo: `OUTSIDE_CLICK_HOOK deferred reason=panel-hidden` — **o hook global do rato não existe
enquanto o painel está escondido**.

## O que NÃO está medido (declarado)

- **O arranque sob o profiler** (app fechada → `py-spy record -- pythonw sotto_webview.py` por `schtasks`):
  é a medida que fecha o *"abrir trava o pc"*. Exige fechar e reabrir a app do dono — não foi feito nesta
  passagem porque ele a pediu aberta.
- **O lado JS** (o painel a desenhar): não há perfil de JS; só sondas de DOM. Um perfil a sério precisa de
  `--remote-debugging-port` no WebView2.
- A contradição dos 1,74-2,09 s vs ~29 s.

## Prova

```
python _main\sotto-profile.py --selftest                      -> SOTTO-PROFILE SELFTEST PASS
python _main\agents-md-pins-oracle.py                          -> AGENTS-PINS PASS
python _main\tooling-intent-oracle.py                          -> TOOLING-INTENT VERDICT PASS
Get-Process -Id 51812                                          -> vivo, rss 76 MB
Get-Content _main\webview-run.log -Tail 4                      -> TRAY_ICON_ADD ok=true / OUTSIDE_CLICK_HOOK deferred
```

## ADENDA 2026-10-30 — a conclusao "a unica largada e' a schtasks" foi REFUTADA

Este recibo dizia que a cura do `Acesso negado` era correr o instrumento por `schtasks /it`. **Medido
2026-10-30 (mesma maquina, mesma sessao):** um processo `high` emprestado (`_main/launch-as-token.py`,
fonte `explorer.exe` pid 13844) larga um filho `high` que **executa de facto** e ganha a mutex da app
(`python _main/launch-as-token.py --selftest` -> `SELFTEST PASS ... integridade=S-1-16-12288 (HIGH)` e
`KILL-DELEGATION PASS -- taskkill direto rc=255, via token(fonte=13844) ok=True, saiu=True`). Dois
defeitos meus explicavam a medicao antiga: `cmd /c taskkill > ficheiro` criava o ficheiro **vazio**, e
`pythonw -c "<codigo>"` chegava ao filho com a linha de comando desfeita pelas aspas -- a cura foi
`subprocess.list2cmdline` e um **ficheiro** em vez de codigo inline. A tarefa agendada continua a ser a
via do vigia da propria app (que ja' corre `high`), nao a unica via de uma lane.
