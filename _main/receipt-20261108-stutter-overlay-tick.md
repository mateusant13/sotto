# RECIBO — stutter do Sotto: a criacao por frame do relogio da legenda (2026-11-08)

DM do watcher (`dm-6d9e0af7f42fd0e4481a`), acusado **pythonw.exe(52860)**, arvore de 8 processos,
`io 17.7 MB/s`, `creation=59.474 creations/s`, `interrupt=11.712 %` of cpu time, `disk=27.49 ms/op`.

## 1. A LINHA QUE PRODUZIU A PRESSAO (nomeada, como o DM exige)

`app/webview/caption_overlay.py` -> `NativeOverlay._arm_tick` (pre-cura, o codigo do pid 52860):

```python
timer = threading.Timer(delay, lambda: self._tick(gen))   # UM FIO POR QUADRO
```

Com a legenda ao vivo a 16 ms isso e' ~62 `CreateThread`/s -- e `59.474 creations/s` e' o mesmo numero
medido por outro instrumento. O resto da arvore (worker torch, 8 processos) explicava o `io 17.7 MB/s`,
que e' a carga do modelo, nao um laco.

## 2. O QUE FOI FEITO AQUI, E POR QUE NAO FOI UM EDIT NOVO

A cura ja' estava commitada (`5fa6e87`): um fio `daemon` unico com um `Event` de prazo substitui o
`Timer` por frame, provado por `_main/caption-tick-thread-oracle.py` (`VERDICT: PASS (5/5)`, e o
`--neg-arm` mede 105 construcoes em 1 s com a implementacao antiga).

O pid acusado corria codigo ANTERIOR a ela:

```
python _main/live-code-freshness-oracle.py --strict
  pid=52860 started=2026-11-08 03:40:30.204
  processo: sha256=F0904FE71314   disco: sha256=50583759B3DA   -> LIVE_CODE STALE
```

A regra do repo (AGENTS, PASSO 0) e' explicita: com `STALE`, a primeira accao e' reiniciar, nao corrigir.
O instrumento do proprio repo foi usado, nao um kill a mao:

```
python _main/sotto-relaunch.py --relaunch
  kill pid=52860 confirmado morto (alvos=8)
  CreateProcessAsUser(fonte=14016) ok=True filho=48460
  pid 55668 GANHOU a mutex (carimbo 2026-11-08 03:41:49.383)
  saude do pid 55668: {'log': True, 'mutex': True, 'code_id': '50583759B3DA',
                       'hotkey': True, 'tray': True, 'webview2_failed': False}
```

Nota de honestidade: o pid 52860 tinha sido largado por uma LANE (`--no-self-relaunch --ready-file
_main\ready-29709-19514.txt`), nao pelo dono. Uma lane que deixa uma instancia a deter
`Local\SottoShell` corre codigo velho sem ninguem saber — foi exactamente o que aconteceu.

## 3. PROVA (mesmo instrumento, antes/depois, neste PC)

| instrumento | antes (pid 52860) | depois (pid 55668) |
|---|---|---|
| `python -m watcher profile <pid>` | `cpu=5.2 % de um nucleo` = **0,3 % da maquina**, `num_threads=50` | `cpu=2.3 % de um nucleo` = **0,1 % da maquina**, `num_threads=46` |
| criacao de fios do overlay | ~62/s (um `Timer` por frame) | **0** (fio unico; oraculo: 5/5) |
| `python -m watcher perf` (maquina) | `cpu.saturated 100 %`, `disk.saturated I: queue 3.03 busy 303 %` | as mesmas linhas de MAQUINA continuam: **a maquina esta' carregada por fora** (duas lanes python a 29 % + 27 %, `watcher run` as duas) |

`watcher profile` diz `CANNOT-MEASURE` na atribuicao POR FIO neste processo (`psutil.Process.threads()`
devolve 0 ids com `num_threads()=50`), portanto o numero acima e' o do PROCESSO, kernel-billed, e nao
uma atribuicao por fio. O que fecha o caso nao e' esse numero: e' a criacao por frame ter ido a zero.

## 4. TECTO DECLARADO (o numero que a frota tem de respeitar)

- **Shell em repouso** (video pausado, painel escondido): **<= 2 % de um nucleo**. Medido agora: 2.3 %
  de um nucleo imediatamente apos o arranque (a carga do modelo e a primeira pintura), tendendo a
  menos. O numero antigo da casa era 8,1 % (`paused-pace`), a cura anterior levou-o a ~2 %.
- **Criacoes de fio do overlay**: **0 por frame**; o portao e' `caption-tick-thread-oracle.py`.
- **Lanes**: no maximo **duas** comandos pesados ao mesmo tempo, e cada um por
  `python -m watcher run --cpu 40 -- <cmd>` (Job Object, teto duro de CPU, filhos herdam).
- **Um toque de Alt+C nao pode custar uma transicao por toque**: ver `#2`/`#3` (coalescing em curso,
  `HOTKEY_COALESCED`).

## 5. O QUE FICA ABERTO

- `EXTERNAL_CAPTIONS_READ_MS ms=1015` por volta, `YOUTUBE_LOOP_HZ hz=6.3`, `YOUTUBE_TARGET_SLOW ms=1015`
  no log da instancia nova: uma leitura de CDP que estoura o prazo REPETE no tick seguinte. Nao e' o
  culpado medido deste DM, e' custo declarado a atacar com o mesmo instrumento.
- O `LIVE_CODE` volta a `STALE` enquanto lanes editam `app/panel/**` e `caption_overlay.py` (o hash do
  disco muda a cada edicao). Um `STALE` com lanes a escrever NAO e' uma app velha; o discriminador e'
  comparar o `code_id` do arranque com o hash do disco NAQUELE instante.
