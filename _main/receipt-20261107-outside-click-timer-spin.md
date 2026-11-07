# RECIBO — o vigia de clique-fora girava: 26-31 % de um core para nada (2026-11-07)

Ordem do dono que abriu isto, verbatim: **"acabou de acontecer stutter. culpa de quem? é pra sempre
verificar o maior culpado do stutter"** e *"é pra arrumar de fix, de forma nuclear"*.
Tudo o que segue foi medido nesta caixa hoje, com o instrumento ao lado. Onde diz `PASS`, o comando
correu nesta sessão.

## 1. A LINHA, NOMEADA

| onde | o que era |
|---|---|
| `app/webview/sotto_webview.py:7929` (o handler de `WM_TIMER`) | chamava `_restart_timer()` em **cada** tick |
| `app/webview/sotto_webview.py:7974-8008` (`OutsideClickWatcher._restart_timer`) | `KillTimer(None, 1)` + `SetTimer(None, 1, 100, None)` **a cada tick**, e matava com a **constante pedida** |
| `app/webview/sotto_webview.py:7744` (`_POLL_TIMER_ID = 1`) | o id nunca foi o que o Windows usa — ver §2 |

Classe: `OutsideClickWatcher` (`app/webview/sotto_webview.py:7786`), a thread `sotto-outside-click`.
Existe desde 2026-10-30 (quando o `WH_MOUSE_LL` foi removido) e gira sempre que o painel esteve
alguma vez visível.

## 2. O MECANISMO, MEDIDO EM TRES SONDAS

**(a) `SetTimer`/`KillTimer` sem `argtypes` — o id devolvido nao e' o id pedido.**
Trace da classe real, com as duas chamadas embrulhadas (`_main/outside-click-timer-oracle.py`,
sonda de diagnostico):

```
('kill', 1, 0)            <- KillTimer(None, 1) devolve 0 (FALHOU)
('set', 1, 100, 14973)    <- SetTimer(None, 1, 100, None) USOU/GEROU o id 14973
```

Um `KillTimer` com a constante `1` nunca encontra esse timer: **o timer ficava vivo para sempre**,
mesmo depois de `armed = False`. Sintoma medido: 14 ticks em 1,5 s com `armed=False`.

**(b) Re-armar dentro do proprio handler DEGENERA o timer.** Sonda do primitivo, 3 s, mesma thread:

| | taxa |
|---|---|
| `SetTimer` pedido UMA vez | **9,3 Hz** |
| `KillTimer`+`SetTimer` a cada `WM_TIMER` | **2 412 – 3 715 Hz** (4 corridas) |

**(c) A classe real pagava isso em CPU.** `GetThreadTimes` (kernel+user) da thread do vigia armada:

| | taxa | CPU |
|---|---|---|
| antes da cura (codigo de HEAD) | **1 591 Hz** | **13,1 % de um core** |
| depois da cura | **9,2 Hz** | **0,20 % de um core** |

## 3. O ANTES NA INSTANCIA VIVA DELE (pid 23244, codigo pre-cura)

O instrumento e' o da propria app (`THREAD_CPU`, 10 s, `GetThreadTimes` por thread —
`app/webview/sotto_webview.py:11302`). Recorte de hoje, 14:16 → 14:59:

| hora | total da shell | `sotto-outside-click` |
|---|---|---|
| 14:16:24 | 29 % | **19 %** |
| 14:19:24 | 30 % | **23 %** |
| 14:19:54 | 32 % | **27 %** |
| 14:57:54 | 36 % | **26 %** |
| 14:58:54 | 41 % | **31 %** |
| 14:59:24 | 37 % | **29 %** |

O resto do total sao migalhas: `yt-clock` 3-4 %, `sotto-batch-executor` 3 %, `Dummy-6` 1-2 %,
`sotto-gaming-mode` 1 %. **Um unico laco de 10 Hz respondia por ~80 % do CPU da shell.**

## 4. A CURA (3 sitios, nenhuma bandeira nova)

1. `argtypes`/`restype` declarados para `SetTimer`/`KillTimer` (`:7745-7757`).
2. O id guardado e' o que o `SetTimer` **devolveu** (`self._timer_id`), nunca a constante pedida;
   `KillTimer` usa esse id, e um `SetTimer` que devolva 0 passa a dizer
   `OUTSIDE_CLICK_TIMER_FAILED`.
3. O intervalo e' memorizado (`self._timer_ms`): o tick so' se re-arma quando o **estado** muda
   (armar, desarmar, entrar/sair do arrasto). `PostThreadMessageW` recusado passa a dizer
   `OUTSIDE_CLICK_TIMER_POST_FAILED` em vez de falhar em silencio.

## 5. A PROVA (portao `outside-click-timer`, 7 arms)

`python _main/outside-click-timer-oracle.py` → **VERDICT: PASS (7/7)**, rc=0:

| arm | medido | tecto |
|---|---|---|
| A1 primitivo, `SetTimer` unico | 9,3 Hz | 6-14 |
| A2 o re-arme a cada tick degenera | 3 234 Hz | > 200 (prova a causa) |
| A3 taxa da classe real | **9,2 Hz** | 6-14 |
| A4 CPU da thread | **0,20 %** | < 2 % |
| A5 `SetTimer` por segundo | **0,1** | ≤ 1 |
| A6 ticks depois de `armed=False` | **0** | 0 |
| A7 `edit_mode` (100→25 ms) re-arma | **1 vez** | exactamente 1 (o memo nao e' mordaca) |

`--neg-arm` repoe `self._timer_ms = 0` numa **copia** de `sotto_webview.py` e corre a mesma classe:
**3 arms vermelhas** (A5 9,1 re-armes/s, A6 38 ticks depois do disarm, A7 33 re-armes), rc=**1**.
Na bateria: `outside-click-timer` + `red-as-expected-outside-click-timer`
(`_main/_audit-verify-all.cmd:431-432`), os dois classe `0`, pin re-medido em `AGENTS.md`
(**273404 B / 3326 CRLF**, sha256 `FA5FFFFC…B0F7`) e `agents-md-pins-oracle.py` **PASS**.
`code-health` **PASS** (o crescimento de `sotto_webview.py` — 1189456 B / 22539 linhas — foi
absorvido no baseline, com o numero declarado aqui).

## 6. O QUE ESTE RECIBO NAO PROVA

* **O "depois" na instancia dele e' UNMEASURED.** O pid 23244 corre o codigo **anterior** a cura: o
  numero depois da cura nesta caixa e' o da classe real (0,20 %), nao o daquela instancia. O
  "depois" na tela dele exige um restart da app, que e' dele — este assento nao larga a app.
* **O resto da pressao continua.** Medido hoje, sem tocar: **9 `BRIDGE_SPAWNED`** e **8
  `BRIDGE_LOAD_MS`** somando **241 984 ms** de carregamento de modelo, com o commit privado do worker
  em **4 962,6 MB** (`BRIDGE_RSS private_mb=4962.6`) e **79 threads**. Isso e' o segundo maior
  produtor e tem lane propria (`SottoLoadChurn`, `docs/worker-lifecycle.md`); nada aqui o alterou.
* `python -m watcher profile <pid>` continua **negado a este assento** (`OpenThread` com
  `THREAD_QUERY_INFORMATION` acima da minha integridade), e `python -m watcher perf` foi corrido
  (snapshot da maquina) mas nao atribui por thread; a atribuicao por thread que este recibo usa vem
  do instrumento da propria app, que e' o mesmo `GetThreadTimes` e nao precisa de elevacao.
