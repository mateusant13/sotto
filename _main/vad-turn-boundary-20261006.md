# use_vad: false -> true. What it moves, what it does not, and the crash in between.

**Date:** 2026-10-06 · **Repo:** `H:/sotto` · **Item:** `worker/config.json` `model.use_vad`,
rank 1 of `docs/oss-approaches-20261006.md`.

## The two questions

1. Does flipping the boolean change the bundled sample's numbers?
2. Does a "turn boundary" now exist for the renderer to hang on?

**Answers: (1) no, on the bundled sample — and that is a property of the CLIP, not of an inert
flag; (2) no. The flag gates chunks and emits no boundary.**

## The flag is LIVE — it is not a stored-but-ignored key

`_main/vad-option-probe.py`, one process per arm, same audio:

```
arm off  get_option('use_vad') = 'false'   silence_duration_ms='3360' prefix_padding_ms='560'
         digital silence x12 -> 12/12 blocks of shape (1,65,128), peak 16.635532
arm on   get_option('use_vad') = 'true'
         digital silence x12 -> 2 pass, then None x10
silence None counts: {'off': 0, 'on': 10}
```

A gated chunk makes `StreamingProcessor.process()` return **`None`**. That is the exact case the
model's own README guards (`if inputs is not None`). `run_chunk` did not.

## Arm 1 — the crash the boolean alone causes

`_main/vad-gap-sample.flac` = `sample1` (13.69 s) + **6.0 s of digital silence** + `sample2`,
33.9 s. Same audio, same process, only the flag differing:

```
VAD ON  (before the guard): rc=1, 16 of 26 captions, then
        File "worker\sotto_worker.py", line 477, in run_chunk
          af = feats["audio_features"]
        TypeError: 'NoneType' object is not subscriptable
VAD OFF (control)         : rc=0, 26 captions, 132 tokens, blank_frac 0.7609
```

So `"use_vad": true` on its own takes the worker DOWN on the first pause longer than 3.36 s —
which is the owner's normal audio. The guard in `run_chunk` counts the gated chunk in
`vad_gated_chunks`, advances the clock, and returns no text. Re-measured after the guard:
`rc=0`, 6 chunks gated.

## Arm 2 — bundled sample, VAD on vs off (TREE A: `lang_id` literal `0` = en-US)

`worker/assets/sample1.flac`, 13.69 s:

| arm | rc | captions | tokens | frames | blanks | blank_frac | empty_chunks | vad_gated |
|---|---|---|---|---|---|---|---|---|
| before (VAD off) | 0 | 16 | 94 | 262 | 168 | 0.6412 | 8 | n/a |
| after (VAD on) | 0 | 16 | 94 | 262 | 168 | 0.6412 | 8 | **0** |
| neg (VAD off, forced) | 0 | 16 | 94 | 262 | 168 | 0.6412 | 8 | **0** |

Transcript byte-identical across all three:
`"Going along  slushy Country roads  speaking damp  in dr drafty school  day For a fortnight
He'll have  an appearance At some Sunday morning and  he can come to  immediate"`

## Arm 3 — bundled sample, re-measured (TREE B: a sibling lane changed `lang_id` to `"os"` mid-flight)

That lane's `lang_id: "os"` resolves from the host locale to **pt-BR (12)** (`state="lang",
lang_id=12, requested="os", source="config:os-locale"`). The bundled samples are ENGLISH, so the
whole clip is now transcribed against a Portuguese prompt:

| arm | rc | captions | tokens | frames | blanks | blank_frac | empty_chunks | vad_gated |
|---|---|---|---|---|---|---|---|---|
| after (VAD on) | 0 | 2 | 10 | 178 | 168 | 0.9438 | 22 | **0** |
| neg (VAD off) | 0 | 2 | 10 | 178 | 168 | 0.9438 | 22 | **0** |

Fields differing: `rtf`, `infer_wall_s`, `peak_rss_mb` — timing only. **VAD is still a no-op on
this clip.** (Transcript both arms: `'Going along Day'`.)

*Not this lane's change, reported because it invalidates the brief's measurement surface: the
bundled sample is English and the config now prompts pt-BR on this host.*

## Arm 4 — the renderer contract

`app/electron/caption-formulation.js` derives a sentence boundary from **audio timestamps**:
`start - lastAudioEnd >= SENTENCE_GAP_S (8)`, reason `audio-gap Ns`. Driving the REAL module with
the two real caption streams (`_main/vad-renderer-arms.js`):

```
=== gap-off: 4 captions, largest observed audio gap 14.56s ===
   [audio-gap 14.56s] "Going along Day."
   lines committed 1; closed by an AUDIO GAP: 1
=== gap-on:  6 captions, largest observed audio gap 14.56s ===
   [audio-gap 14.56s] "Going along Day."
   lines committed 1; closed by an AUDIO GAP: 1
```

**Identical decision, identical reason.** What a turn boundary does and does not give:

- **Does:** a caption carries its own audio window, so a LONG gap between windows closes the line.
  That mechanism exists today and is what already fires here.
- **Does not:** the VAD emits **no** boundary event. It only withholds chunks, and a withheld chunk
  produces *no caption at all* — so it can enlarge the gap the renderer measures, but it cannot
  create the boundary by itself, and it never names one.
- **No state in the worker names a turn boundary.** Measured states in a file run: `boot`, `lang`,
  `model-loading`, `model-loaded`, `selftest-start`, `selftest-done`. The only new number is
  `vad_gated_chunks`, which says the VAD acted, not that a turn ended.

## What changed in the tree

| file | change |
|---|---|
| `worker/config.json` | `"use_vad": false` -> `true` |
| `worker/sotto_worker.py` | `run_chunk`: handle `process()` returning `None`; count `vad_gated_chunks`; surface it in `selftest-done`, the selftest stderr block, `WORKER_STATS` and the final `done` status |
| `AGENTS.md` | deviation row marked RESOLVED |
| `docs/model-specs/README.md` | §4 rewritten, §6.3 marked RESOLVED |
| `worker/README.md` | VAD line rewritten |
| `docs/oss-approaches-20261006.md` | A3 marked LANDED with the falsified prediction; §6 oracle C1 re-pinned; re-extracted and re-run -> GREEN |

Peer-doc oracle after the change (`_main/_oss_oracle.log`): 4 PASS, exit 0.

## Reproduce

```bash
py -3 _main/vad-option-probe.py                       # is the flag live?
py -3 _main/vad-arm-run.py after worker/config.json worker/assets/sample1.flac
py -3 _main/vad-arm-run.py neg   _main/config-vad-off.json worker/assets/sample1.flac
py -3 _main/vad-arm-run.py gap-on  worker/config.json     _main/vad-gap-sample.flac
py -3 _main/vad-arm-run.py gap-off _main/config-vad-off.json _main/vad-gap-sample.flac
node  _main/vad-renderer-arms.js                      # does the renderer see a boundary?
```

---

## SELF-AUDIT

- **protocolos em falta** — Eu nao verifiquei que outro lane estava a editar `worker/config.json` em
  paralelo. O repo TEM `lane_ledger`/mapa de posse exatamente para isto e eu nao o consultei antes de
  fixar o baseline. Resultado medido: o meu primeiro conjunto antes/depois foi invalidado a meio por um
  sibling que mudou `lang_id: 0` -> `"os"`, e so o notei porque o numero de captions caiu de 16 para 2.
  Diferente: consultar o ledger e o mtime de cada ficheiro citado ANTES do primeiro arm, e re-medir tudo
  no fim contra a arvore corrente (que e' o que acabei por fazer).
- **verificacao adicional** — `sha256sum worker/config.json worker/sotto_worker.py` gravado por arm.
  Barato (segundos) e teria detetado o confound no momento do arm 1 em vez de 30 minutos depois. Custo: uma chamada.
- **checkboxes novas** — MECANICO, nao "ter mais cuidado": *antes de publicar um antes/depois, os dois
  arms tem de partilhar o mesmo hash de config; se nao partilharem, a comparacao esta' VOID*. Comando:
  `py -3 -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('worker/config.json').read_bytes()).hexdigest())"`
  e assert igualdade entre os dois arms. Deve dar RED quando um sibling toca no ficheiro a meio.
- **review por outro subagente** — **sim-com-escopo**: (a) o guard novo em `run_chunk` e o facto de eu
  ter mudado o worker, e (b) a afirmacao negativa "o VAD nao da' fronteira de turno ao renderer", que e'
  uma afirmacao sobre AUSENCIA e portanto a mais facil de errar.
- **gate-doubt**:
  - **verde-de-verdade:** o ORACLE GREEN do doc peer foi RE-EXTRAIDO do ficheiro e executado (`_main/_oss_oracle.py`
    gerado a partir de `docs/oss-approaches-20261006.md`), nao retyped — a corrida existe em `_main/_oss_oracle.log`.
    Mas o C1 que ele agora afirma e' um predicado que EU escrevi, logo e' um gate de frescura do documento,
    nao um gate independente de comportamento. Os gates de comportamento reais sao os `rc` e os numeros dos arms,
    que sao saidas de processo verdadeiras.
  - **falta-no-gate:** nenhum gate verifica que dois arms comparados correram contra a MESMA config. Um cenario
    futuro atravessa este buraco exatamente como atravessou hoje: um lane muda `lang_id`, cada arm individualmente
    continua a sair rc=0 verde, e a comparacao antes/depois fica silenciosamente invalida.
  - **gate-melhor:** assertar hash igual de `worker/config.json` entre os dois arms do par. Deve ficar RED com
    input "arm A com `lang_id: 0` e arm B com `lang_id: \"os\"`" — o estado exato em que este trabalho esteve.
- **confianca** — **alta** para "o flag esta' LIVE e gateia chunks" (get_option + 12/12 vs 10/12 `None`) e
  para "no sample bundled nao muda nada" (dois arms campo-a-campo iguais, agora em duas arvores diferentes).
  **media** para o diff de decode no ficheiro com pausa ser uma diferenca de *qualidade*: nao ha ground truth.
  Muda-a uma referencia humana do audio.
- **nao verificado** — (1) o caminho LIVE (dispositivo) nunca foi exercitado, so' file mode; o guard esta' em
  `run_chunk`, que ambos os caminhos chamam, mas nao houve corrida com dispositivo. (2) a ligacao
  painel/WebView2 do `vad_gated_chunks` nao foi exercitada — o painel nao foi aberto. (3) o efeito do
  `lang_id: "os"` -> pt-BR sobre os samples ingleses e' de outro lane; nao avaliei se e' intencional.

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh SottoVadOn` — output pasted VERBATIM:

```
## CACHE/PRICE
- task/agent: SottoVadOn
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoVadOn.jsonl
- cache: read=10357504 write=0 hit=97.9693% (cache-read / input+cache-read); universe: 76 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoVadOn.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=72 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 76 of 76 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T06:38:32.740000+00:00 | break_items=1; WHEN=2026-10-06T06:40:24.722000+00:00 | break_items=2; WHEN=2026-10-06T06:45:33.606000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 112245 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoVadOn']; window: 2026-10-06T06:38:32.740000+00:00..2026-10-06T06:45:33.606000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10fef-296e-7391-967b-20b92f1642d3 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791268712740 | session_id=01a10fef-296e-7391-967b-20b92f1642d3 provider=deepseek-flash model=deepseek-flash item_index=79; turn_id=1791268824722 | session_id=01a10fef-296e-7391-967b-20b92f1642d3 provider=deepseek-flash model=deepseek-flash item_index=257; turn_id=1791269133606 (state=RESOLVED-BREAKS-OMP; population: 3 of 112245 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoVadOn']; window: 2026-10-06T06:38:32.740000+00:00..2026-10-06T06:45:33.606000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T06:48:05.411127+00:00
- usage rows: 76
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 214685
- output tokens: 45638
- cache-read tokens: 10357504
- cache-write tokens: 0
- hit ratio: 97.9693% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=72 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 76 of 76 matched usage rows
- prefix breaks: 6 (state=RESOLVED-BREAKS-OMP; population: 3 of 112245 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoVadOn']; window: 2026-10-06T06:38:32.740000+00:00..2026-10-06T06:45:33.606000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T06:38:32.740000+00:00; WHERE session_id=01a10fef-296e-7391-967b-20b92f1642d3 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791268712740
  - break_items=1; WHEN=2026-10-06T06:40:24.722000+00:00; WHERE session_id=01a10fef-296e-7391-967b-20b92f1642d3 provider=deepseek-flash model=deepseek-flash item_index=79; turn_id=1791268824722
  - break_items=2; WHEN=2026-10-06T06:45:33.606000+00:00; WHERE session_id=01a10fef-296e-7391-967b-20b92f1642d3 provider=deepseek-flash model=deepseek-flash item_index=257; turn_id=1791269133606
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

- cache: read=10357504 write=0 hit=97.9693% over 76 usage rows; instrument `scripts/cache-task-report.sh`, universe = my own session JSONL (named above).
- price: $0.00000000 USD — provider-reported `message.usage.cost.total`; per-model rates unknown in this source.
- when-failed: three prefix breaks, WHEN 06:38:32.740Z / 06:40:24.722Z / 06:45:33.606Z (state `RESOLVED-BREAKS-OMP`); run of `cache-task-report.sh` rc=0.
- where-failed: session `01a10fef-296e-7391-967b-20b92f1642d3`, provider/model `deepseek-flash`, item_index 0 / 79 / 257.
- source: `C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoVadOn.jsonl` (log also at `_main/_cache-report.log`).

---

## Launch hygiene, and the ALERTA-JANELA that coincides with this lane's run window

The house census logged one window while the arms were running:

```
ALERTA-JANELA ts=2026-10-06T06:42:22Z chave=24836:22814874 pid=24836 hwnd=22814874 nome=python
JANELAS ts=2026-10-06T06:42:22Z modo=medicao visiveis=15 alarmSet=1 reencontro=0 pidsConhecidos=137 alarmeHerdadoApagado=0
JANELAS ts=2026-10-06T06:43:22Z modo=medicao visiveis=15 alarmSet=0 reencontro=0 pidsConhecidos=137 alarmeHerdadoApagado=1
```

**What is established:** the entry names a process called `python` (not `pythonw`) with a non-zero
hwnd, inside the window in which the four arms were running; the alarm cleared one minute later,
so the process was short-lived.

**What is NOT established:** that pid 24836 is mine. The census log records a pid and an hwnd, not
a parent chain or a command line, so it cannot attribute the window to a lane. Other lanes were
running python in the same window (the census had already flagged three `pythonw` windows from
other work at 06:11–06:13, and `OpenWith` at 06:33).

**What I did to remove the exposure rather than test it.** `windows()` reports
`NO WINDOW SHOWING SIGNAL FOUND` for the runner command, but that instrument reads the COMMAND
TEXT — it cannot see the `creationflags=0x08000000` inside `_main/vad-arm-run.py`, and it cannot
see whether the parent `py -3` owns a console. So instead of probing (which would itself open a
window if the hypothesis were true), the arm was re-run under a launch form that provably cannot
own a console, and the numbers were required to be identical:

```
pyw -3 _main/vad-arm-run.py after-w worker/config.json worker/assets/sample1.flac   # rc=0
py  (child launched with CREATE_NO_WINDOW)  rc 0  caps 2  text 'Going along Day'
pyw (GUI subsystem, no console possible)    rc 0  caps 2  text 'Going along Day'
identical on every transcription field: True          (text, tokens, frames, blanks,
                                                       blank_frac, empty_chunks, vad_gated_chunks, audio_s)
```

Two things are settled by that pair: the arm is **deterministic across launch forms** (so the
before/after comparison is not a launch artifact), and `pyw` is the hardened form for any future
run of this runner.
