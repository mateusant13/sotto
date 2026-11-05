# O que o Sotto custa, medido (ORDEM 4-ter)

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.

### 4-ter. O QUE O SOTTO CUSTA, MEDIDO (a ferramenta, 2026-10-22)

`_main/sotto-perf-log.py` — **psutil 5.9.8** (já instalado; `wpr.exe` existe e é a ferramenta certa
para um traço ETW profundo, deixada de fora porque escreve gigabytes em discos a 0,4-20 % livres).
Mede **quatro** coisas: (1) o **slip** de um `sleep(25 ms)` — quanto tardou a acordar, que é o stutter
que o dono sente; (2) CPU incl. **`interrupt`/`dpc`**; (3) disco (% do intervalo em I/O) e RAM;
(4) a **família do Sotto atribuída pela ÁRVORE de processos**, nunca pelo nome, com os
`msedgewebview2.exe` que são de OUTRA app contados à parte.

```
python _main\sotto-perf-log.py --launch --seconds 150     # 8 s de base, abre a app, mede
python _main\sotto-perf-log.py --report <ficheiro>.jsonl
```

**O INSTRUMENTO MEDIU-SE A SI MESMO, E ISSO É A LIÇÃO.** A 1.ª corrida deu max **1135 ms** e 25 slips
acima de 250 ms — com a família a n=1 / 121 MB, CPU 38-53 %, `dpc` < 1,5 % e disco a 0 %. A causa era
a sonda a partilhar o **GIL** com o amostrador (que varre 722 processos a cada 5 s). Falsificador
executado, mesma máquina e mesmos 45 s: sonda em **processo próprio** → p50 **0,5 ms**, p99 10,0, max
64,7, **0** slips > 100 ms; sonda em thread → p50 7,4, p99 267,8, max 755,4, **44** acima de 100 ms.
⇒ a sonda vive agora num **processo próprio**. Regra derivada: *um instrumento que partilha o
scheduler com o que amostra mede o instrumento.*

**O QUE A APP CUSTA (medido com a app sã, 120 s):** 10 processos, pico **1801 MB**, **35,0 s de CPU
em 120 s** (29 % de um núcleo) — **worker 104,3 % de CPU / 1271 MB**, webview n=7 30,6 % / 361 MB,
shell 19,6 % / 161 MB. (O worker a 104,3 % **não é repouso**: naqueles 120 s couberam DOIS
carregamentos do modelo — ver o bullet do dispositivo mudo abaixo. O repouso medido é CPU 25,9 s em
~3,3 min.) **O stutter da máquina é pequeno e não é do Sotto:** p50 0,7 ms, p99 27,5,
max 103,2, **4 slips > 50 ms em 4280 amostras**.

**O DISPOSITIVO MUDO, MEDIDO — E A CORRECÇÃO DE UMA AFIRMAÇÃO MINHA.** Com o dispositivo de captura
silencioso (`VoiceMeeter Output [MME] peaked 0.000122 < floor 0.002`), o log de 03:25-03:31 diz:
1.º worker `BRIDGE_SPAWNED` 03:25:51 → `BRIDGE_LOAD_MS ms=24750` → **morre com
`ROTATION_CEILING reached`** (`BRIDGE_DEATH rc=3 deaths=1 kind=no-audio`) às 03:27:46 → a shell
respawna **15 s** depois (= `no_audio_backoff_base * 2**0`, `sotto_webview.py:13022`) → 2.º worker
`BRIDGE_LOAD_MS ms=16235` → e **não volta a morrer**: entra em `BRIDGE_SILENT_BENIGN ms=30000` a cada
30 s. O tecto existe (`no_audio_restart_cap=3` → `BRIDGE_RESTART_SUPPRESSED … why=restarting-cannot-
fix-a-routing-problem resume=press-Alt+C`, `:13004-13021`). **A 1.ª versão deste bullet chamava-lhe um
treadmill "para sempre": era FALSO** — é UMA recarga redundante (24,75 s + 16,2 s de CPU ao serviço de
zero legendas) e depois estabiliza. O modelo **não é libertado** no estado benigno: medido 03:31 →
`rss 21 MB` mas **`private 3070 MB`** (páginas *trimmed*, memória comprometida). O defeito de raiz é de
**rotagem** (decisão do dono, não código): com este dispositivo o Sotto não transcreve nada, e o log
di-lo. **A melhoria que a ordem dos eventos justifica (PROPOSTA, não feita):** o modelo carrega
**antes** de se saber que o dispositivo está plano (`worker/sotto_worker.py:5261` vs a rotação em
`:6308-6760`), pagando 1,2 GB de leitura para descobrir que não havia nada para captar; uma
verificação de tap barata antes do load pouparia o load inteiro nesse caso — com o custo de a
acrescentar ao caminho feliz.

**NÃO SE PODE LANÇAR A APP A PARTIR DE UMA PANE (medido, e é o mecanismo por trás da HARD RULE).**
Duas largadas do contexto do servidor OpenCode deram `TRAY_ICON_ADD ok=false winerror=5` **e**
`WEBVIEW2_INIT_FAILED` (`RPC_E_DISCONNECTED` / `E_ACCESSDENIED`): a app sobe **sem painel e sem
worker**. Não é sessão (a pane e o Explorer estão ambos na sessão 1, interactiva) nem disco. A **mesma
linha de comando** lançada pelo **Task Scheduler com `/it`** deu uma app **sã** (`TRAY_ICON_ADD
ok=true winerror=0`, `WORKER_PRELOAD done started=true`). Histórico: **69** `TRAY_ICON_ADD ok=true`
contra **6** `TRAY_UNAVAILABLE` — e 2 dessas 6 são as da pane. Receita para uma lane que precise mesmo
da app: `schtasks /create … /it` + `/run`, e apagar a tarefa depois.

**A APP ARRANCA COM O WINDOWS, E ISSO FOI MEDIDO DUAS VEZES (a segunda corrigiu a primeira):** em
2026-10-23 mediu-se `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` e afirmou-se que `Sotto` **não
estava** lá. **Re-medido no mesmo dia, com o valor lido à frente: a chave tem 22 entradas e `Sotto` é uma
delas** (`Sotto presente=True`). A "correção" anterior estava ela própria errada — e é a segunda vez que
uma afirmação deste ficheiro sobreviveu por não ter sido re-medida. A bullet do §Factos ("A app arranca
com o Windows", `pythonw.exe ... sotto_webview.py --log ...`, nunca `run.cmd`) é a **verdadeira**. Gerir
com `run.cmd --install-autostart / --autostart-status / --uninstall-autostart`. Consequência para o
stutter: o Sotto entra no arranque da máquina do dono, logo qualquer custo de arranque paga-se em cada
boot — e o preload idle-gated (6 s de inactividade, tecto de 120 s) existe por isso.

## RE-MEDIDO 2026-11-05, 19:0x — a instância VIVA, e o termo que enche o commit não é o Sotto

Instrumento: `_main/shell-thread-cpu.py <pid>` (Toolhelp32 + `GetThreadTimes`), `BRIDGE_RSS` do
próprio worker, `psutil.memory_info().private`, `performance-gate.py status`.

| quem | working set | privado | CPU de UM núcleo |
|---|---|---|---|
| shell (pid 20288, `pythonw`) | 172 MB | **134 MB** | **1,2 %** (8 s) / **3,7 %** (30 s) |
| worker (pid 31348, `python`) | 2 216 MB | **4 674 MB** | **2,5 %** (8 s) |

O `private` do worker mede-se pelo `BRIDGE_RSS` e a série é **degrau, não rampa**: 3 389,6 MB com o
áudio parado (`blocks=855`) e **4 674,1 MB quando o áudio volta** (`blocks=906`) — o motor ao vivo
aloca ali e o número fica plano depois (cinco amostras seguidas em 4 674,8). Não é fuga; é o patamar
real, **2,6× o pico de 1 801 MB** que o bullet acima cita (aquele número é working set, e o respectivo
`private` já aparecia a 3 070 MB duas linhas abaixo).

**O COMMIT DA MÁQUINA (82,6 %, gateway AMBER às 19:2x) NÃO É DO SOTTO.** Ranking por `private` medido
no mesmo minuto: `python.exe` pid 61116 **11 624 MB** (`benchmarks/model_ab_20261105/run_ab.py`, cinco
modelos de embedding, 6 000 documentos, arrancado 19:11:52), `bash.exe` pid 26760 2 839 MB
(`state/work/perf500/FG1/sha-prototype.sh`), daemon do codeintel 4 440 MB, **Sotto worker 4 675 MB**.
O heavy lease foi **RECUSADO** nesse minuto com `commit-pct=82.6 >= amber 80.0`: a bateria não corre
por medição do gate, não por ordem de ninguém.

**Um parque e uma retomada de VRAM em ~13 min** nesta sessão (`VRAM_GUARD_PARKING free_mb=393` 18:57:22
→ `VRAM_GUARD_RESUMING free_mb=13643` 18:59:10, `showing=False`), contra os 21 parques medidos antes da
cura da esteira.
