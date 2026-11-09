# RECIBO — a reserva de commit do worker: quem a segura, se e' devida, e o tecto

**Demanda:** DM do watcher `dm-e8e82bc2f38155c7fa42` (2026-11-09T~19:4x): *"python.exe(37112) is
holding private commit on a tight budget"* -- 2,62 GB privados parados, 121,5 s sem progresso, a
70,6 % de commit. As tres perguntas da DM respondem-se aqui com instrumento, e a terceira e' a que
fica escrita como decisao.

## 1. O pid e' MEU? -- Sim, e' o PRODUTO, nao uma lane

O pid nao e' de nenhuma sonda desta sessao. Ele e' o worker da app do dono, e o proprio log da app
o nomeia:

```
2026-11-09 19:48:18.066 sotto: WORKER WORKER_COST tag=tick cpu_s=30.438 cpu_pct_avg=1.2
  wall_s=10.0 rows=0 rows_since_tick=0 rows_per_min=0.0 chunks_since_tick=0
  audio_s_since_tick=0.000 rtf=none uptime_s=2917 pid=37112
```

Cadeia de processos (CIM, sem admin):

```
pid=37112 python.exe   started=18:59:28  ppid=27568
ppid=27568 pythonw.exe started=18:59:27  cmd=<unreadable> (integridade dele; a shell)
ppid=38908 GONE
```

`27568` e' a shell da app (o `pythonw` que ele corre), `37112` o worker que ela larga; o avo esta'
morto porque a shell do dono nasce de um largador que ja' saiu -- e' o estado normal desta app
(medido e documentado na seccao das shells orfas).

## 2. A reserva e' DEVIDA? -- Metade sim, metade NAO, e a metade que nao e' esta' medida

| o que | numero | instrumento |
|---|---|---|
| commit privado do pid | **2 685 MB** | `Win32_PerfFormattedData_PerfProc_Process.PrivateBytes` |
| working set | **23 MB** | idem (`WorkingSet`) -- a diferenca de 100x e' a assinatura de um processo PARADO |
| CPU | **0 % agora**, `cpu_pct_avg` **0,8-1,2 %** por tick de 10 s | `WORKER_COST` no log da app |
| I/O | **0 ops/s** | `IODataOperationsPersec` |
| fios / handles | 60 / 927 | idem |
| audio capturado | **0,000 s por tick**, `chunks_since_tick=0`, `rows=0` | `WORKER_COST` |
| motores | `engines=nemotron:off,parakeet:off` | `REDUX_SHEDDING level=muito-alta ... commit_pct=70.6% cpu_pct=95.2%` as 19:46:17 |
| commit da maquina | 70,6 % (leitura do worker) / **65,7 %** (`python -m watcher overview` as 19:47) | o instrumento do watcher |

**A parte devida:** o motor de ASR tem de estar residente para transcrever; a ordem do dono de
2026-11-04 proibe desligar o modelo a pretexto de "legenda ao vivo desligada". Um worker sem motor
residente e' um worker que perde a primeira fala.

**A parte NAO devida, e e' a que a DM apanhou com razao:** o `load_shedding` levou os DOIS motores a
`off` as 19:46 e o processo continuou a segurar **2 685 MB**. Ou seja, o pior dos dois mundos: o
servico esta' desligado e a memoria nao voltou. A causa e' a ja' medida em
`_main/receipt-20260926-*.md`/`engine-commit-cycles`: as arenas do `onnxruntime` (e o contexto CUDA)
**nao devolvem** commit ao processo que as criou -- o `off` corta o uso, nao a reserva.

## 3. Por que NAO matei o processo (e o numero que mostra que matar seria teatro)

O unico caminho que devolve commit de arena e' o processo sair. Medido, o que acontece a seguir:
o worker **carrega o motor no arranque**, sempre (`worker/sotto_worker.py:6822`,
`asr = StreamAsr(...)` dentro do `main`, antes de existir audio), e o log da app tem o preco:
`BRIDGE_LOAD_MS ms=8906` / `11703` / `36968` / `64954` conforme o disco e a carga. A shell respawna
em ~1,0 s. Portanto: matar devolve 2,7 GB por ~60 a 90 s e depois **volta a pôr ~2 GB** -- e a
maquina paga a recarga durante esse tempo. Nao e' libertar: e' trocar uma reserva parada por uma
recarga a correr.

## 4. O TECTO, declarado (o que a DM pede no ponto 3)

* **Tecto residente deste worker: 2,7 GB** de commit privado com os motores carregados -- medido
  hoje, 2 685 MB, e e' o valor que o governador deve tratar como *decisao*, nao como suspeita.
* **Pico historico: ~4,6 GB** quando os TRES modelos estao carregados ao mesmo tempo (medido em
  `engine-commit-cycles`: parakeet +448,5 MB, as tres sessoes ORT do nemotron +467,5 MB, os pesos do
  genai +483,2 MB, o resto segurado dentro do processo vivo).
* **Vida: enquanto a app do dono estiver aberta.** O worker e' filho dela; nao ha' prazo proprio.
* **A reserva nao cresce por ciclo:** o residuo medido por carga e' -1,3 MB (parakeet) e +40,8 MB
  (sessoes ORT), logo o que se ve e' um PLATO, nao uma fuga.

## 5. O que fica aberto, nomeado

1. **A cura estrutural** (nao feita nesta lane): quando o nivel de shed e' `muito-alta` **e** nao ha'
   audio capturado por N minutos, o worker devia SAIR em vez de segurar arenas desligadas -- e a
   shell devia respawnar SO' quando houver audio (o `load_shedding` ja' conhece as duas metades).
   Hoje o resultado medido e' o oposto: commit parado com o servico desligado. Mudar isto e' mexer no
   ciclo de vida do worker com a app dele aberta, e tem de ser medido com
   `python -m watcher overview` antes/depois -- nao se faz aqui, a quente, sem esse par.
2. `py-spy` nao anexa a esta arvore (`err=5`, integridade `high` vs `medium`), logo o que o processo
   faz com 60 fios parados nao e' atribuivel por pilha -- fica a atribuicao por fio que o
   `cpu-tripwire` faz.

## 6. O que respondi ao watcher

Classificacao: **produto, reserva parcialmente devida, tecto 2,7 GB / pico 4,6 GB, vida = a sessao
da app**; o `off` do shed sem devolucao de commit e' o defeito que a DM acertou; matar nao paga
porque o arranque recarrega o motor. O pid que esta lane possui e' outro: os processos caged das
suas proprias sondas (`python -m watcher run --cpu 40`), nenhum deles parado com GB de reserva.
