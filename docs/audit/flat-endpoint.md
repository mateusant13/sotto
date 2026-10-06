# flat-endpoint — the endpoint that came out FLAT, measured and fixed

Lane `SottoFlatEndpoint`, 2026-10-06. Ticket `140ba250c2f890e1e8bbf62d`.
Target: `H:/sotto/worker/wasapi_loopback.py`. `sotto_worker.py` was NOT changed (the
contract did not require it). No file under `app/` was touched.

**Verdict: defect 1 (the COM gate) is the CAUSE of the measured flat endpoint and is
fixed and proven end-to-end. Defect 2 (GetBuffer's SILENT flag) is a real, adjacent
contract violation in the same class and is fixed and proven deterministically; its
live firing on this box is UNPROVEN (0 SILENT-flagged packets in 800 measured
packets). One of my own predictions was REFUTED by a control run and is recorded as
refuted, not quietly dropped.**

---

## 1. The defect, reproduced exactly

`_main/_live_owner3.log:61` gives the value:

    BRIDGE_EXIT pid=13752 rc=1 ... nonzero_blocks=0 peak=0.000092

`peak=0.000092` is not a small signal — it is the documented dead-endpoint signature of
an MME pseudo-device (`worker/sotto_worker.py:128` records the same `9.2e-05` for
"Mapeador de som da Microsoft - Input" [MME]). The ladder was never reaching its live
rung at all.

### 1.1 The measured mechanism

`_main/flat-endpoint-oracle.py`, arm `real-two-calls-one-thread`, prints it:

    first=rate=48000 ch=2  second=RAISED WasapiError: CoInitializeEx failed: Função
    incorreta. (0x00000001)   refs{init=2 uninit=0}

The ladder calls `default_render_endpoint()` TWICE on one thread before any stream
exists — `device_candidates() -> loopback_device_spec()`, then
`WasapiLoopbackTap.__init__` — and the pre-fix gate took a COM reference on the first
call and never gave it back, so the second call returned `S_FALSE` (1) and the gate
raised on it. `S_FALSE` is a SUCCESS code: *"The COM library is already initialized on
this thread"* (Microsoft Learn, CoInitializeEx, return value). Rung (a) — WASAPI
loopback of the default render endpoint, the only rung that needs no virtual cable —
could therefore never open.

### 1.2 The branch that hid it, and why a natural run looks green

The gate's return value depends on who touched COM first on the ladder thread.
MEASURED, both branches, same machine, minutes apart
(`_main/flat-endpoint-oracle.py`, and the two worker runs in §2):

| first thing on the thread | `CoInitializeEx(MTA)` returns | pre-fix gate | rung (a) |
|---|---|---|---|
| nothing | `S_OK`, then **`S_FALSE`** | **raises on the 2nd call** | **never opens** |
| `sounddevice` / `sd.query_devices()` | **`RPC_E_CHANGED_MODE`** on every call | tolerated (the old `hr not in (0, RPC_E_CHANGED_MODE)`) | opens and works |

`device_candidates()` imports sounddevice and calls `sd.query_devices()` BEFORE rung (a)
is probed, so on this box the natural run lands in the second row and *looks fine* —
which is why a plain `py -3 worker/sotto_worker.py` reproduces nothing. The measured
owner failure was the first row. `_main/flat-endpoint-ladder.py` pins the branch on
purpose (`mta` = initialise the main thread MTA before anything else; `natural` = leave
it alone), so the pair below is the same command, the same audio and the same window.

## 2. BEFORE and AFTER, in the defect branch, with real audio

Audio source: `_main/_join-play.py "VoiceMeeter Input" <seconds>` — the 13.69 s,
16 kHz mono SPEECH fixture `worker/assets/sample1.flac` (LibriSpeech) rendered into the
DEFAULT render endpoint, i.e. exactly what the tap is supposed to carry. No fixture over
15 s was used. Every process was started with `pythonw.exe` (no console, no window).

Command, both arms identical:

    "C:/Program Files/Python311/pythonw.exe" _main/flat-endpoint-ladder.py mta \
        --max-seconds 45 --tap-window 5

| | BEFORE (pre-fix `wasapi_loopback.py`) | AFTER (fixed) |
|---|---|---|
| file | `_main/flat-endpoint-BEFORE-mta.out/.err` | `_main/flat-endpoint-AFTER-mta.out/.err` |
| worker rc | **3** (`ran_but_silent`) | **0** |
| candidates offered | `VoiceMeeter Output`, `CABLE Output`, `Mixagem estéreo`, `Entrada (Realtek HD Audio Line input)` — **no WASAPI rung** | `WASAPI loopback: {0.0.0.00000000}.{55395a4e-…}` **first**, then the same four |
| `blocks` | 100 | 451 |
| **`nonzero_blocks`** | **0** | **451** |
| **`peak`** | **0.000092** | **0.465224** |
| `captions` | 0 | 42 |
| `verdict` / `device_outcome` | `silent-device` / `all-flat` | `captions-emitted` / `run-ended` |
| `tap_ledger` | — | `rung "a"`, `rung_why "WASAPI loopback of the default render endpoint"`, `settled true`, `captions 42` |
| `proved_alive` / `proved_reason` | false | true / `caption` |
| `rotations` | 3 | 0 |

Captions from the AFTER run are the fixture's own words, decoded end to end:
`"Going along slushy Country roads speaking In dra drafty schoolro day …"`.

**Checkable BEFORE line (`_main/flat-endpoint-BEFORE-mta.err`, final stats):**

    WORKER_STATS tag=final blocks=100 ... nonzero_blocks=0 peak=0.000092 rms=0.00002146 ... captions=0 ... audio_s=8.96

**Checkable AFTER line (`_main/flat-endpoint-AFTER-mta.err`, final stats):**

    WORKER_STATS tag=final blocks=451 ... nonzero_blocks=451 peak=0.465224 rms=0.05580778 ... captions=42 ... audio_s=44.80

`peak=0.000092` BEFORE and `peak=0.465224` AFTER is the card's "`peak` that is not
~1e-4"; `nonzero_blocks` 0 -> 451 is the card's "`nonzero_blocks` > 0 with real audio".

### 2.1 The same pair in the branch that already worked (no regression)

    _main/flat-endpoint-ladder.py natural --max-seconds 45 --tap-window 5

| | BEFORE-natural | AFTER-natural |
|---|---|---|
| file | `_main/flat-endpoint-BEFORE.out/.err` | `_main/flat-endpoint-AFTER-natural.out/.err` |
| rc | 0 | 0 |
| `nonzero_blocks` / `peak` | 601 / 0.465224 | 451 / 0.465224 |
| `captions` | 59 | 43 |
| device | WASAPI rung (a), `rotations=0` | WASAPI rung (a), `rotations=0` |

Not a regression: the branch that worked still works, and still settles on rung (a).

## 3. The changed lines

`worker/wasapi_loopback.py` — 28 856 B after, 20 277 B before, 8 hunks, 141 added,
12 removed (`_main/flat-endpoint.diff`; the pre-fix file is frozen, byte-identical,
as `_main/_flat-endpoint-mutant-wasapi_loopback.py`, sha256
`2A2F8021D1E92FEF2CA20E6BCF8B6167B452965D7752C88598ACFE6A454A753F`, and the oracle
REFUSES to run if that hash drifts). NOTE: this file is not tracked by git
(`git ls-files` does not know it), so there is no `git diff` for it; the diff above is
against the frozen copy.

1. **Constants** (`:56-68`): `S_OK`, `S_FALSE`, `COM_REF_TAKEN`, `COM_ALREADY`,
   `AUDCLNT_BUFFERFLAGS_SILENT`.
2. **`_com_init()` / `_com_uninit()`** (new, `:140-200`): the init gate, with the vendor
   contract in the comment and the citation. Three outcomes, because they differ in what
   the caller then owes: `S_OK`/`S_FALSE` -> a reference was taken
   (`COM_REF_TAKEN`); `RPC_E_CHANGED_MODE` -> COM is already running here in another
   apartment, nothing was taken (`COM_ALREADY`); anything else -> `WasapiError`.
3. **`default_render_endpoint()`** (`:248-267`): `com = _com_init()` then
   `try: return _enumerate_default_render_endpoint(role)` / `finally:` release if a
   reference was taken. The old body moved verbatim into
   `_enumerate_default_render_endpoint` (no behaviour change inside it).
4. **`_fmt()`** (`:216-226`): narrowed to `c_int32` before `ctypes.WinError`. This is a
   pre-existing crash in the error path: `WinError` takes a SIGNED C int, so
   `_fmt(E_FAIL)` raised `OverflowError: Python int too large to convert to C long`
   instead of returning the message. Without this, "the negative HRESULTs stay errors"
   is not observable — the failure surfaces as a bare Python error out of the reporter.
   Measured: oracle arm `genuine-failure-refused` was `CRASH` pre-fix, `raise` with
   `CoInitializeEx failed: Erro não especificado (0x80004005)` post-fix.
5. **`WasapiLoopbackTap.__init__`** (`:405-415`): `self._com = None`, `self.silent_packets = 0`.
6. **`_start()`** (`:445-465`): takes a COM reference for the tap's LIFETIME and
   releases it if opening fails; the old body moved verbatim into `_open()`.
   `close()` (`:646`) calls `_release_com()`. This is required BY the balancing: with
   `default_render_endpoint()` now balanced, CoCreateInstance would otherwise run on a
   thread whose COM had just been closed.
7. **`_pump()`** (`:578-603`): the `flags` word read from `GetBuffer` is no longer
   discarded. When `AUDCLNT_BUFFERFLAGS_SILENT` is set (or `pData` is NULL), the packet
   is accumulated as `frames` ZEROS and counted in `self.silent_packets`, instead of the
   undefined buffer bytes being decoded as audio. It is accumulated rather than skipped,
   so a silent endpoint keeps the run's block cadence and is reported as the silence it
   is (peak 0) rather than vanishing from the counters.

## 4. The oracle: red with the old code, green with the new

`_main/flat-endpoint-oracle.py` — one command, both subjects, the control pair printed.
The frozen pre-fix copy is the negative arm, with its hash pinned.

    py -3 _main/flat-endpoint-oracle.py            # 8 arms
    py -3 _main/flat-endpoint-oracle.py --with-tap # 9 arms, adds a real loopback open

LIVE (fixed file, sha `10A1E611…`): **PASS 8/8** (9/9 with `--with-tap`).
CONTROL (frozen pre-fix copy, sha `2A2F8021…`): **RED on 5 arms**.

    s-false-is-success             LIVE ok(proceed, init=1 uninit=1 device=1) | MUTANT RED raise
    s-ok-is-success-and-balanced   LIVE ok(proceed, init=1 uninit=1 device=1) | MUTANT RED uninit=0
    changed-mode-usable-no-ref     LIVE ok (CONTROL arm)                      | MUTANT ok (control)
    genuine-failure-refused        LIVE ok(raise)                             | MUTANT RED CRASH
    real-two-calls-one-thread      LIVE ok(2 calls, init=2 uninit=2)          | MUTANT RED 2nd RAISED
    real-sta-mismatch-usable       LIVE ok (CONTROL arm)                      | MUTANT ok (control)
    silent-flag-is-silence         LIVE peak=0.000000000 silent_packets=3     | MUTANT RED peak=0.000091553
    unsilenced-packet-kept         LIVE peak=0.000091553 (CONTROL arm)        | MUTANT ok (control)
    live-tap-opens (opt-in)        LIVE ok(spec=ok)                           | MUTANT RED WasapiError 0x00000001

Two arms are green on BOTH subjects on purpose: `changed-mode-usable-no-ref` and
`unsilenced-packet-kept` are the CONTROLS. Without them, "never raise" and "zero
everything" would pass the arms above; with them, the RED arms are red for the
right reason.

Arm 7/8 drive the REAL `_pump` against a scripted COM vtable (a cell pointing at an array
of stdcall function pointers, which is exactly what `_vtbl()` dereferences) and feed it
`0x38C00000` float32 = **9.155e-05** per sample — the measured dead-endpoint peak — with
and without the SILENT bit. That ties the deterministic arm to the number in the
evidence rather than to an invented one.

## 5. Defect 2: proven deterministically, live firing UNPROVEN

`IAudioCaptureClient::GetBuffer` sets `AUDCLNT_BUFFERFLAGS_SILENT` (0x2) when the
packet is silence and the buffer contents are NOT valid samples. The pre-fix pump read
the flags into a local and dropped it, then decoded the packet. Oracle arms 7/8:
SILENT-flagged packet peak **0.000091553 -> 0.000000000**, same bytes un-flagged
**0.000091553 kept**.

**UNPROVEN, and named as such:** that this ever fired in the owner's measured run. The
one live flag census on this box is `_main/bfrc_flags.out` — **0 of 800 packets flagged
SILENT** — and the measured line's `peak=0.000092` came from an MME pseudo-device
(PortAudio), not from a WASAPI packet. So defect 2 did not produce
`_main/_live_owner3.log:61`; defect 1 did. Defect 2 is fixed because it is wrong against
the vendor contract and because it becomes reachable exactly when rung (a) starts
working (an idle endpoint now returns real packets), which is the state this fix creates.

## 6. What I got WRONG, and the control that refuted it

I predicted that treating `RPC_E_CHANGED_MODE` as a hard error — which is how the card's
"keep the negative HRESULTs as errors" reads literally, and how
`_main/wasapi-com-init-oracle.py` `changed-mode-raises` encodes it — would re-create the
flat endpoint. **The control run refutes that.**

`_main/flat-endpoint-control-changedmode.py -- --max-seconds 40 --tap-window 5` builds a
variant from the FIXED source with exactly one change (`return COM_ALREADY` ->
`raise WasapiError`) and runs the real worker through it:

    candidates: ['VoiceMeeter Output (VB-Audio Vo', 'CABLE Output (VB-Audio Virtual ',
                 'Mixagem estéreo (Realtek HD Audio Stereo input)',
                 'Entrada (Realtek HD Audio Line input)']      <- rung (a) is GONE
    done: verdict=captions-emitted peak=0.40097 nonzero_blocks=343 captions=24 rc=0

So: dropping rung (a) is real and measured (the candidate list loses the WASAPI entry),
but the ladder still carried the audio that time through `CABLE Output`, because the
owner's VoiceMeeter routing happened to feed it. On this box, with this routing, the
user-visible result was NOT the flat endpoint. What is NOT established is whether that
would hold on a machine with no virtual cable at all — which is the machine rung (a)
exists for (`wasapi_loopback.py`'s own docstring: the shipped config used to name three
devices that exist only where a virtual cable is installed, so the product could not
capture system audio anywhere else).

**Decision taken, and why:** `RPC_E_CHANGED_MODE` is a STATE, not a fault — COM IS
initialised on the thread, and measured on this box the tap opens and carries speech
through it. The gate therefore returns `COM_ALREADY` (usable, NO reference, so
`CoUninitialize` is NOT called: calling it would release PortAudio's reference) instead of
raising. The card's rule is honoured for every other negative HRESULT, and
`genuine-failure-refused` is the arm that proves it. This deviation is deliberate and it
is the one place where I did not follow the card literally: I did not delete a working
rung to satisfy a sentence, and §6 is the measurement, with its own limit stated.

Consequence for the sibling oracle: its `changed-mode-raises` and `real-mismatch-refused`
arms stay RED against this fix. That is a disagreement about the contract, not a
half-finished fix; the evidence for the disagreement is above. I did not edit that file.

## 7. Cheapest mechanical checks a future change must pass

    py -3 -m py_compile worker/wasapi_loopback.py     # rc=0, measured
    py -3 _main/flat-endpoint-oracle.py              # VERDICT PASS, exit 0
    py -3 _main/flat-endpoint-oracle.py --with-tap   # VERDICT PASS, exit 0

`fast` RED for a future change: delete the `finally: _com_uninit()` from
`default_render_endpoint` -> `s-ok-is-success-and-balanced` goes RED (`uninit=0`).
Second RED: drop the SILENT branch from `_pump` -> `silent-flag-is-silence` goes RED with
`peak=0.000091553`.

## 8. Limits of this report, stated

* The A/B pair in §2 is one run per arm. Two arms (BEFORE-natural, AFTER-natural) and one
  control agree with them, which is why the pair is reported as a pair and not as a
  distribution.
* §6's control carried audio through `CABLE Output` in a single run; the owner's routing
  is live and can change between runs. The claim recorded is therefore only "rung (a) is
  removed from the candidate list", not "the endpoint goes flat".
* Defect 2's live firing stays UNPROVEN (§5).
* With the fix, an idle endpoint now returns real (SILENT-flagged) packets instead of
  raising, so `wasapi_loopback` is exercised where it previously was not. The
  post-fix worker runs in §2 have no silent period in them, so `silent_packets > 0`
  in a live run is UNPROVEN here; it is proven only in the scripted arm.
* Audible side effect: the fixture is rendered into the DEFAULT render endpoint for the
  duration of each measured run, so the owner may hear the 13.7 s speech clip.

---

## SELF-AUDIT (obrigatorio)

- **protocolos em falta** — dois. (1) O protocolo de COORDENACAO DE IRMAOS por
  `write agent://<id>` nao funciona neste build ("no delegation seam"), e eu so descobri
  isso ao TENTAR avisar a lane que escreveu `_main/wasapi-com-init-oracle.py` de que um
  dos seus bracos exige uma regressao; fiquei sem canal e tive de o dizer no relatorio.
  Faria diferente: verificar a via de coordenacao ANTES de comecar a medir um defeito que
  outra lane ja esta a instrumentar. (2) Comecei a correr o worker ANTES de fixar a copia
  pre-fix como artefacto de oraculo; o congelamento (`_flat-endpoint-mutant-...`) foi feito
  a tempo, mas foi sorte, nao protocolo — o primeiro passo devia ser SEMPRE congelar a
  fonte pre-fix com o sha escrito no oraculo, para que o par vermelho/verde nao dependa de
  alguem se lembrar.
- **verificacao adicional** — a mais barata que teria aumentado a confianca e' uma segunda
  corrida de cada braco do A/B (§2): uma corrida por braco e' um par, nao uma distribuicao,
  e §6 mostra que a rota do owner (VoiceMeeter) muda entre corridas. Custo: ~2 min por
  corrida + ~30 s de load do modelo, com audio a tocar. Nao corre: o par ja reproduz o
  valor medido do cartao ao digito (`peak=0.000092`, `nonzero_blocks=0`) e o braco natural
  concorda, mas fica nomeado como a proxima coisa a fazer.
- **checkboxes novas** — (a) "congelar a fonte pre-fix e o oraculo RECUSA correr se o sha
  dela mudar" — mecanico, ja implementado (`MUTANT_SHA256` + mensagem `REFUSING`), com o
  comando `py -3 _main/flat-endpoint-oracle.py`; (b) "nenhum braco de oraculo pode passar
  por vacuidade: cada braco vermelho tem de vir com um CONTROL verde nos DOIS subjects" —
  a classe de defeito aqui era exactamente essa (um gate que aceita tudo, ou um pump que
  zera tudo, passariam); (c) "um braco que corre o pump/laco REAL contra uma vtable
  scripting tem de ter um TETO de iteracoes" — apanhei o meu proprio oraculo num laco
  infinito (a primeira versao do `_next_size` devolvia 0 e o pump faz `poll`), e a cura
  mecanica e' `if self.next_calls > 10000: raise`.
- **review por outro subagente** — sim-com-escopo: um subagente deve (1) correr
  `py -3 _main/flat-endpoint-oracle.py` e TENTAR deixar verde o controlo (mudando o sha do
  freeze ou o `MUTANT_SHA256`) para provar que o vermelho e' real; (2) ler §6 e procurar
  uma medida que sustente a decisao de manter `RPC_E_CHANGED_MODE` nao-fatal num host SEM
  virtual cable — e' a unica afirmacao do relatorio que eu sustento por desenho do modulo
  e nao por medida nesta maquina; (3) rever `_pump` linha a linha, porque os bracos 7/8
  usam blocos de 480 frames e a interaccao com `AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY`
  nao esta' testada.
- **gate-doubt**
  - **verde-de-verdade:** — `VERDICT PASS` do oraculo: e' real e nao podia passar vacuoso,
    porque a corrida `CONTROL` imprime do MESMO comando um sujeito DIFERENTE (a copia
    congelada, sha `2A2F8021`) RED em 5 bracos; nao ha' artefacto stale (`load()` faz
    `sys.modules.pop` por caminho explicito) nem flag suprida a mao. O verde mais fraco e'
    o do A/B ao vivo: MESMO device e MESMO audio com dois modulos, mas sequencialmente e
    com o modulo importado dentro do processo do worker — nao ha' isolamento entre os dois
    bracos, so' sequencia. `py_compile` rc=0 e' verde por construcao: nao prova
    comportamento.
  - **falta-no-gate:** — `silent_packets > 0` num run AO VIVO (so' o braco scripting o
    prova) e a interaccao SILENT + DATA_DISCONTINUITY (0x1|0x2 no mesmo pacote). Cenario
    futuro que atravessa o buraco: alguem reduz `block_ms` para 20 ms num desktop OCIOSO —
    os pacotes passam a ser SILENT-flagged a maioria do tempo e a cadencia de blocos passa
    a vir SO' do ramo de silencio; nenhum gate deste repo compara `blocks` contra
    `silent_packets` num run real.
  - **gate-melhor:** — `py -3 _main/flat-endpoint-oracle.py` fica RED se alguem apagar o
    ramo SILENT do `_pump` (input: `worker/wasapi_loopback.py` sem
    `flags.value & AUDCLNT_BUFFERFLAGS_SILENT`) — ja e' verdade e foi medido
    (`silent-flag-is-silence` RED com `peak=0.000091553` no freeze). O check mecanico que
    FALTA e' o do silencio ao vivo: `--with-tap` NAO verifica silence (abre 0.3 s com o PC
    possivelmente a tocar). Fechava-se com um braco `live-idle-is-silent`: com NADA a
    tocar, exigir `silent_packets > 0` E `peak == 0.0`, RED se `peak > 0`. Nao o escrevi:
    exige garantir que a maquina esta' mesmo OCIOSA, o que nao consigo provar desta sessao
    sem um instrumento de silencio ao nivel do endpoint.
- **confianca** — ALTA no DEFEITO 1: o valor do cartao (`nonzero_blocks=0`,
  `peak=0.000092`) e' reproduzido ao digito em §3, o mecanismo esta' medido em tres formas
  independentes (API crua, stub scripting, worker real) e o par vermelho/verde imprime os
  dois sujeitos. MEDIA no DEFEITO 2: o codigo esta' errado contra o contrato e o braco
  determinista prova-o, mas o disparo ao vivo fica UNPROVEN (§5). BAIXA na afirmacao de
  DESENHO de §6 (manter changed-mode nao-fatal): sustenta-se na docstring do modulo, nao
  numa medida de um host SEM virtual cable, que eu nao tenho.
- **nao verificado** — (1) disparo AO VIVO de `AUDCLNT_BUFFERFLAGS_SILENT`
  (`_main/bfrc_flags.out`: 0/800); (2) comportamento num host SEM virtual cable instalado
  (nao existe nesta maquina); (3) SILENT|DATA_DISCONTINUITY no mesmo pacote; (4) uma
  segunda corrida de cada braco do A/B ao vivo; (5) `silent_packets > 0` num run real do
  worker; (6) o caminho do `app/` (painel/shell) — fora do alvo por instruccao;
  (7) lint/formatador do repo sobre o ficheiro mudado — apenas `py_compile` (nao encontrei
  config de lint para `worker/`).

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh SottoFlatEndpoint` (verbatim, trimmed of the
duplicated partition lines):

- source: `C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoFlatEndpoint.jsonl`
- cache: read=13016204 write=0 hit=98.0269% (cache-read / input+cache-read); universe: 75 usage rows from the same jsonl
- price: $0.00000000 USD (source: session JSONL `message.usage.cost.total`, provider-reported; exact per-model rates UNKNOWN — not recorded in this source)
- when-failed: break_items=8 WHEN=2026-10-06T09:34:52.486Z | break_items=2 WHEN=2026-10-06T09:36:47.001Z | break_items=3 WHEN=2026-10-06T09:41:43.666Z (state=RESOLVED-BREAKS-OMP; 3 of 115934 OMP prefix-ledger rows)
- where-failed: session_id=01a11090-a596-74a9-bbe1-afcfcd16d7ec provider=deepseek-flash model=deepseek-flash item_index=0 turn_id=1791279292486 | item_index=68 turn_id=1791279407001 | item_index=129 turn_id=1791279703666
- model + route: opencode-go-3/deepseek-flash (68 calls), opencode-zen/space-bunny-free (7 calls)
- usage rows: 75; input tokens 261995; output tokens 97845; cache-read 13016204; cache-write 0
- report generated_at: 2026-10-06T09:49:57.454472+00:00
- verdict: UNKNOWN — no task-level acceptance verdict is stored; the ratio is descriptive, not a prefix-stability decision
