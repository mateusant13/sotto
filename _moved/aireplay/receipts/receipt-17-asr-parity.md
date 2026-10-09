# receipt-17 — the ASR works END TO END on real speech, and two silent failures are now refusals

Lane 9 · 2026-10-07 · scope `src/asr/` + `_main/_lane9-asr-gate.ps1`

## The gap this closes, as measured

The brief's premise was: *"8 of 8 sample clips have NO audio stream, so the ASR has never been
fed anything from a capture."* That is true of the **capture** clips
(`src/capture` produces video-only mp4). It is **not** true of the ASR: two real-speech WAVs
already sat on this box, and the Python ASR consumes exactly that format. So the work here
was not to synthesise audio — it was to run the product path on real speech, and to fix the
two ways that run could have reported success while lying.

**Audio used — already on this box, NOT synthesised:**

| file | duration | format | language |
|---|---|---|---|
| `H:\sotto\_main\_redux-long\src-en-8s.wav` | 8.543 s | 16 kHz mono PCM16 | English |
| `H:\sotto\_main\_redux-long\src-pt-15s.wav` | 15.0 s | 16 kHz mono PCM16 | Portuguese (pt-BR) |

Both are the already-registered parity inputs (`constants.PARITY_EN` / `PARITY_PT`), 16 kHz
mono PCM16 — the model's own contract, which `audio.py:53-61` refuses anything else of. They
were copied from `H:\sotto\_main\{en-us,pt-br}-sample.wav` (22050 Hz) by the corpus builder
(`_main/_redux-long/corpus.json`). No TTS, no noise, no synthetic tone: real broadcast speech.

## ARM A — real speech in, transcript out

Through `runner.transcribe()` — the function the CLI and the parity harness both call, not a
unit test of the decoder.

**English (`src-en-8s.wav`, 8.543 s, 2 segments):**

> The radio announced that the bridge over the river will be closed next Monday. Residents
> need an alternative route to get to work.

**Portuguese (`src-pt-15s.wav`, 15.0 s, 2 segments):**

> O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira. Os
> moradores precisam de um caminho alternativo para chegar ao trabalho.

Both **byte-identical** to the Redux ternary oracle (`_main/redux-en.txt`,
`_main/redux-ptbr.txt`), including the `segunda-feira` hyphen that receipt 02 had to loosen a
threshold for.

### The accuracy number, stated honestly

**WER vs the oracle: 0.0 % on both clips (0 errors / 23 EN words, 0 / 27 PT words;
sub=0 del=0 ins=0).**

**That is NOT an accuracy claim.** The reference is `redux-{en,ptbr}.txt` — the transcript of a
**different engine** (the sibling's Redux ternary), not a human transcription of these clips.
So the number is **agreement between two engines on the same audio**. It is **not a bound on
anything**: if both engines were wrong in the same way, the error would still read 0.0 %. The
honest reading is "the int8 ONNX export reproduces the trusted engine exactly on these two
clips". A true WER needs a labelled corpus; **this box has none, so human-labelled WER is
`NOT MEASURED`** and no accuracy figure is claimed anywhere in this receipt.

**Population:** 2 clips, 23.543 s of speech, 50 reference words. A third clip would move the
number; it does not change what the number *is*.

**Normaliser limits, measured not assumed** (verifier-found, now stated): `wer_against` is
case- and punctuation-insensitive, but **accent-SENSITIVE** (`"rádio"` vs `"radio"` → 1.0) and
does **not** normalise hyphens (`"segunda-feira"` vs `"segunda feira"` → 0.0). So the score is
strictly conservative on accents and blind to hyphen differences.

The WER is computed in `src/asr/gate.py:wer_against` (word-level Levenshtein with a
substitution/deletion/insertion split, cross-checked against an `assert sub+del+ins == errors`),
because **`jiwer` and `editdistance` are not installed on this box** (verified:
`import jiwer` → `ModuleNotFoundError`). It was checked against 9 hand-computable cases
(identical, deletion, insertion, substitution, doubles, reorder) — 0 mismatches — and, by the
verifier, against an independent 900-pair sweep. The oracle for Portuguese is
**cp1252, not UTF-8** (0xE1 at offset 135), and the driver **announces the decode it used on
stderr** rather than silently picking one — a mis-decoded reference changes characters and
therefore the score, with nothing else looking wrong.

## ARM B — the language prompt, both directions

**The finding, and it corrects the brief's premise: this engine is NOT language-conditioned
at all, so the "prompt 12 collapses English / literal 0 collapses Portuguese" failure mode
cannot occur on this path — because there is no prompt slot.**

Read off the loaded sessions, not inferred from the model name:

```
encoder      : ['audio_signal', 'length']
decoder_joint: ['encoder_outputs', 'targets', 'target_length', 'input_states_1', 'input_states_2']
language inputs declared: NONE
```

`docs/model-specs/README.md` §4 says the same thing about a sibling export — *"its encoder
declares no `lang_id` input at all (it is not prompt-conditioned). Every constant in §1
belongs to ONE export."* That is the spec line that governs this lane: the `lang_id` table
(§3, `pt-BR: 12`, `auto: 101`) belongs to the **Nemotron** export in `H:\sotto\worker`, not
to `nemo-parakeet-tdt-0.6b-v3`. **I did not port, emulate or invent a prompt for it.**

But the silent version of the same defect is real here, and it is worse than a wrong id:

```
onnx_asr recognize(..., language=X) on src-pt-15s.wav:
   {}             -> sha 6a5d7b8acad6, 159 chars
   language='pt'  -> sha 6a5d7b8acad6, 159 chars   IDENTICAL
   language='en'  -> sha 6a5d7b8acad6, 159 chars   IDENTICAL
   language='klingon' -> sha 6a5d7b8acad6, 159 chars   IDENTICAL
```

`onnx_asr` accepts `language=` because Whisper/Canary need it
(`onnx_asr/adapters.py:50`, `models/nemo.py:232-238`); on the **TDT transducer** path
(`onnx_asr/asr.py:192-229`) it is read by nobody, so it changes nothing. A caller who selects
a language selected **nothing** — and, unlike the Nemotron case, **nothing on screen would ever
say so**.

**Both directions proven:** a *matching* language (`pt` on Portuguese) and a *mismatching* one
(`en`, and the undeclared `klingon`) are all equally ignored — 4/4 identical transcripts.

## The two cures (both in `src/asr/`, both refusals, neither a behaviour change on the good path)

### 1. A provider that did not load is now a refusal — `engine.ProviderUnavailableError`

Measured **before** the cure, `--provider cuda` on this box:

* exit code **0**
* transcript **identical** to `--provider cpu** (sha `b7e338fa06da`)
* `session.get_providers()` → `[['CPUExecutionProvider'], ['CPUExecutionProvider']]`
* ORT's own stderr: `Failed to create CUDAExecutionProvider ... cublasLt64_13.dll which is missing`

A gate, a CI run, or a receipt could all have reported a CUDA run. `engine._verify_provider`
now compares the **requested** provider against what the sessions **actually bound**, in both
directions (a requested CUDA that fell back, and a requested CPU-only session that bound
anything else). Measured after:

```
$ py -3 -m asr.transcribe --wav src-en-8s.wav --provider cuda
rc=2
asr: ProviderUnavailableError: provider 'CUDAExecutionProvider' did not load (ORT fell back
silently): sessions=[['CPUExecutionProvider'], ['CPUExecutionProvider']],
available=['TensorrtExecutionProvider','CUDAExecutionProvider','CPUExecutionProvider'].
On this box CUDA is requested but not loadable (AGENTS.md:230-234); use --provider cpu.
```

### 2. A language this export cannot honour is now a refusal — `engine.LanguageNotSupportedError`

`recognize()` takes `language=` **precisely so it can be refused**, instead of the caller
passing it to `onnx_asr`, where it is swallowed. The engine records the declared graph inputs
at load and refuses unless a language input actually exists.

```
$ py -3 -m asr.transcribe --wav src-pt-15s.wav --language pt
rc=2
asr: LanguageNotSupportedError: language='pt' cannot be honoured: nemo-parakeet-tdt-0.6b-v3
declares no language input (graph inputs={'encoder': ['audio_signal','length'], ...}).
onnx_asr accepts the kwarg for Whisper/Canary and IGNORES it here, returning the identical
transcript for every value -- a silent no-op.
```

**No regression on the good path**, measured by transcript hash before and after the change:
`b7e338fa06da5301` **identical**, 130 chars, `provider_cpu_only=True`,
`language_conditioned=False` now reported in every `done` event and on the `RESULT` line.

## ARM C — the control: revert both cures in a COPY, and it must go red

`_main\_lane9-ctl\asr\` is a byte copy of the package with (1) the `_verify_provider` call
removed and (2) `recognize()` reverted to the unconditional one-argument call. Measured:

```
copy          : _main\_lane9-ctl\asr  (10 modules, engine.py sha256 13523ac1a8d48787)
imported from : _main\_lane9-ctl\asr\__init__.py      <- the COPY, asserted
cuda_silently_accepted : True                        <- pre-cure defect reproduced
onnx_asr_accepts_pt    : yes, 159 chars, sha 6a5d7b8acad6
onnx_asr_accepts_en    : yes, 159 chars, sha 6a5d7b8acad6
VERDICT : PASS (the control reproduced the defect)
```

**Two control bugs were found and fixed by making the gate actually run it** — recorded
because both are the exact failure shape this repo keeps paying for:

1. **The control imported the LIVE package.** The first copy was written to
   `_main\_lane9-ctl\` and the import put `_main` on `sys.path`, where `src` already won, so
   ARM C ran the *cured* code and could never fail. `arm_c` now asserts
   `Path(ctl_src).parent == root/"asr"` and **raises** otherwise — a control that runs the
   product's own path is the trap recorded at `constants.py:150-153`.
2. **The control failed for the wrong reason** — `REPO_ROOT` derives from `__file__`
   (`constants.py:52`), so the copy looked for `models/` under `_main` and raised
   `ModelDirError`. The real model dir is now passed explicitly, so the control exercises the
   defect and not the path arithmetic.

## THE REVIEWER'S VERDICT — verbatim, and it was FAIL

Dispatched read-only (`mcode exec --permission off`, the runtime's own headless agent; this
session has no `task` tool, so the CLI route is the honest equivalent — the reviewer could not
write to the repo). It ran the gate itself, read the exit code without a pipe, proved
`wer_against` against an independent Levenshtein over **900 pairs (0 divergences)**, and
audited ownership.

> `VERIFIER VERDICT: FAIL -- o gate não tem braço vermelho no ARM A (gate.py:198-205 nunca usa
> o WER no veredicto: PASS com WER 100%) e a cura do provider nunca é exercitada no código vivo
> (provider="cuda" só aparece na cópia, gate.py:366); a metade de idioma do ARM C
> (gate.py:373-384) contorna o engine revertido e não pode falhar`

It also confirmed what was right: criterion A carries **no overstatement** ("That is NOT an
accuracy claim" — WER humano `NOT MEASURED`), criterion B is confirmed at
`docs/model-specs/README.md:208` and on the loaded graph inputs, rules 1-3 are honoured, and
ownership left no out-of-scope artefact.

### The four substantive defects it found, and what I did about each

| # | Sev | Defect | Fix |
|---|---|---|---|
| **F1** | ALTA | **ARM A could never say no.** `problems` only checked transcript-非empty, provider, segment count — so the gate would print `LANE9-GATE PASS` with a **WER of 100 %** | `ARM_A_MAX_WER = 0.0` is now **inside the verdict** (`gate.py`), threshold taken from the pre-existing lock (`PARITY_*`: `ratio_min=1.0`, `max_char_diff_blocks=0`), with the sub/del/ins split in the failure message |
| **F2** | MÉDIA-ALTA | **Cure #1 had no red arm in the shipped code.** `provider="cuda"` appeared only inside the ARM C copy, so a neutered live `_verify_provider` (an early `return`) left all arms green | **New ARM D** asks the **LIVE** engine for `--provider cuda` and requires `ProviderUnavailableError`, while also asserting the cpu arm still loads CPU-only. A stray `-NoNewWindow`/`return` in the cure now fails the gate |
| **F3** | MÉDIA | **ARM C's language half could not fail** — it called `e.model.recognize` (raw onnx_asr), the same call ARM B already makes, bypassing the reverted `recognize` entirely | It now calls the copy's own `e.recognize(...)`, records whether the signature still takes `language`, and the arm only passes when **both** pre-cure defects are visible. The `runner.py` `.replace()` is now **guarded**: if the call site moves, it raises instead of silently no-op'ing into a TypeError for the wrong reason |
| **F4** | MÉDIA | The CPU arm failed **open** on an empty session list, and `provider_cpu_only` was vacuously `True` via `all([])` — absence of evidence reading as evidence | **Half-fixed by me, then caught half-fixed by verifier pass 2** (`engine.py:210` still carried `and self.provider != "cpu"`, so the CPU arm still passed vacuously, and `gate.py` had two more `all([])` sites). **Now closed on both arms**: an empty session list refuses for `cpu` AND `cuda`, and both `all([])` sites are guarded with `bool(session_providers) and ...`. The 6-state probe shows `cpu + empty sessions` flipping ACCEPTED → **REFUSED**. The cost is deliberate and disclosed: a model whose adapter exposes no encoder session is refused, because a check that cannot check must not pass. |
| **F5** | BAIXA-MÉD | "an upper bound on error against human labels" is **mathematically false** — two engines wrong the same way would read 0 | Rewritten above: agreement between two engines, **not a bound** |
| **F6** | BAIXA | "`get_providers()` is what ORT **ACTUALLY bound**" overstates: it is *reported*, not executed — a session listing CUDA can pass the check with no GPU work done | Docstring rewritten to say the session **reports** what it bound, and to name the readback as a readback. **NOT fixed in my first pass** — verifier pass 2 found the offending sentence still sitting at `engine.py:200` while this table already claimed it done. Fixed on the second pass. |
| **F7/F8/F9** | BAIXA | PS1 header advertised `0x08000000\|0x00000008` that the body said it removed; `$TimeoutSec` declared and unused (a hung run looked slow); stderr filter hid tracebacks | Header corrected to what the code does, timeout **honoured** via `WaitForExit(ms)`, stderr now **unfiltered** |
| **F10** | BAIXA | The control copy lived in `_main/` and dirtied the tree every run | The gate's copy now goes to **`%TEMP%\lane9-ctl\asr`**. **NOT fully fixed:** a stale PRE-CURE copy is still **committed** at `_main/_lane9-ctl/` — it entered via another lane's freeze commit `51f84cc` ("entrega transportavel"), which is the owner's delivery snapshot. Nothing in `src/asr/` or the PS1 references it any more, so it is inert, but it is still there. **`git rm -r _main/_lane9-ctl` is an OWNER DECISION**: it edits a delivery snapshot, not a lane's own file. |
| **F11** | BAIXA | `wer_against` returned a partial dict for an empty reference → latent `KeyError` in the caller | Both branches return the same key set |
| **F12** | BAIXA | `--skip-c` printed the **same** `LANE9-GATE PASS` as a full run — a dishonest green by omission | `--skip-c` now prints `LANE9-GATE INCOMPLETE (control skipped)` and **exits 2** |

## THE SELF-CHECK: the negative instruments are shipped, not in a scratch dir

Verifier pass 1 named the right lesson — *"a gate nobody has seen go red is an ornament"* — and
the cited proofs lived in `%TEMP%`, where pass 2 found them **absent** and rebuilt every one
from scratch. So the reds now ship **inside the gate driver**, re-runnable in one command,
writing nothing into the repo:

```
pwsh -File _main\_lane9-asr-gate.ps1                       # the gate: 5 arms, exit 0
py -3 -m asr.gate --selfcheck            # the reds: 17 boxes, exit 0, loads NO model
```

**17 boxes, 17 pass.** NEG-1 ARM A red on a wrong transcript (`FAIL`, WER 100.0 %, 23 errors)
· NEG-2 six hand-computable WER cases + the empty-reference shape · NEG-3 all seven provider
states · NEG-4 the control imports the COPY (`G:\Temp\lane9-selfcheck-ctl\asr\__init__.py`)
and reproduces the pre-cure defect.

**It immediately paid for itself by catching two bugs in itself.** The first `--selfcheck` run
reported **4 BAD** — three "false" WER failures caused by comparing the function's *rounded*
output against `1/3` with a `1e-9` tolerance, and a shape-parity box that compared key SETS
when the empty branch legitimately carries an extra diagnostic `reason` key. Neither was a
defect in `wer_against` (the standalone 9-case check had already passed); both were defects in
the instrument asserting the instrument. That is exactly the failure mode a self-check must be
able to have, so it is recorded rather than quietly corrected.

## VERIFIER PASS 2 — also FAIL, also fair, and the sentence that mattered

> `VERIFIER-2 VERDICT: FAIL -- F4 half-fixed (the all([]) fail-open survives at gate.py:213/:345,
> and engine.py:210 accepts cpu with no session), F6 not fixed in code despite receipt line 213
> claiming it was (engine.py:200 still says "ACTUALLY bound"), and F10's stale pre-cure copy is
> still committed at _main/_lane9-ctl -- plus a stale ARM C hash in the receipt.`
> `...F1, F2, F12 re-proven red by its own arms. NOT MEASURED: machine load during its runs.`

It independently **rebuilt** every negative rather than trust mine (it found the TEMP scripts
absent and said so), then re-proved F1, F2 and F12 with its own arms: `V2-BOX-1` corrupted both
clips → A-en **104.348 %**, A-pt **92.593 %**, both FAIL; `V2-BOX-2` **neutered the shipped
`_verify_provider`** and `gate.arm_d()` went FAIL while the unpatched file passed — which is the
strongest evidence anyone has that ARM D is a real red arm.

**It caught me claiming fixes the code did not have**, which is this repo's most expensive
lesson and it applied it to me: my F4 row said "closed" while `engine.py:210` still exempted
`cpu`; my F6 row said "softened" while the sentence was still there. Both tables are corrected
above. Its own limits are stated in its report: gate **N=1** (its promised N=2 re-run hit a
tool delivery seam and did not execute), ownership attributed from commit metadata rather than
byte-level `git log -p`, and machine CPU during its runs `NOT MEASURED`.

### Gate N=2, and the CLI exit-code contract — the two gaps pass 2 named

| check | command | result |
|---|---|---|
| **gate drift control** | the PS1 twice, sequentially, `$LASTEXITCODE` each time | **both rc=0** — a single pass cannot separate signal from drift (`11-onnx-threads.md` reversed arm order for exactly this) |
| **CLI `--provider cuda`** | `py -3 -m asr.transcribe --wav … --provider cuda --json` | **rc=2** — verifier pass 2 proved the refusal inside `arm_d`, which builds the engine directly; this proves the **CLI** contract |
| **CLI `--language pt`** | same, with `--language pt` | **rc=2** |
| **CLI default (cpu)** | same, no flags | **rc=0** |

## PROVIDER HONESTY, INCLUDING A SELF-AUDIT FIND

`PROVIDERS(shipped, requested, verified) = ['CPUExecutionProvider']` is printed by the gate on
**every** run, and ARM A additionally asserts `provider_cpu_only` from
`session.get_providers()`. ORT *lists* `CUDAExecutionProvider` in
`ort.get_available_providers()` on this box — **available is not loaded**, and only the session
readback distinguishes them.

## THE GATE

```
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane9-asr-gate.ps1
```

Prints `LANE9-GATE PASS` and exits **0** only when A-en, A-pt, B, C and D all behave.
Last full run: **5 arms, pass=5, fail=0, rc=0.**

```
ARM A-en  WER vs oracle 0.0% (0/23 ref words)                      PASS
ARM A-pt  WER vs oracle 0.0% (0/27 ref words)                      PASS
ARM B     graph declares no language input; kwarg swallowed 4/4; engine refuses all   PASS
ARM D     LIVE engine refuses --provider cuda; cpu arm still loads cpu-only           PASS
ARM C     control: copy accepted the provider that did not load, and its reverted
          recognize() has no language guard (ctl_recognize_takes_language=False)       PASS
```

**The fixes are proven by negative arms, not asserted:**

* **F1 proof** (`lane9-armA-negative`, TEMP): with a deliberately wrong transcript injected,
  ARM A returns **FAIL — `WER vs oracle 95.652% exceeds the 0% threshold (22 errors:
  sub=6 del=16 ins=0)`**. Before the fix the same input printed PASS.
* **F4 proof** (`lane9-provider-edge`, TEMP), 6 states of `_verify_provider`:
  `cpu+CPU` ACCEPTED · `cpu+CUDA promoted` REFUSED · `cpu+TensorRT` REFUSED ·
  `cuda+loaded` ACCEPTED · `cuda+fell back` REFUSED · **`cuda+no session` REFUSED** (this one
  was ACCEPTED before the fail-closed fix — a verification that cannot verify was passing).
* **F3 proof**: `ctl_recognize_takes_language=False` and both languages raising
  `TypeError (pre-cure signature)` — the control now exercises the copy's own `recognize`.

**Fingerprints of the exact bytes this receipt describes** (sha256, 16 hex):
`engine.py D3053191DC2CA7A1` · `gate.py 69EBA549925B4043` · `runner.py A401DBA05FECBB48` ·
`transcribe.py 3C2BCD31388624DF` · `_lane9-asr-gate.ps1 33B6AFEE98467660`
(full set in `_main/lane9-sha256.json`). Verifier pass 1 flagged that a stale-file hash makes a
green meaningless — its own rc=0 was 78 s older than the `engine.py` it had validated — so the
hashes are stated here for the same reason. **These are the post-review, post-fix bytes**; the
ones an earlier draft of this receipt carried were already stale and were replaced.

Rules honoured: **rule 1** `Start-Process -WindowStyle Hidden` (the route that actually
suppresses a console-subsystem child; a first draft declared `0x08000000|0x00000008` in a
variable nothing read, which is decoration and was removed); **rule 2** exit code read from
`$p.ExitCode` of the process object, never through a pipe; **rule 3** native `H:\` paths only.
Post-run census: **no lingering `asr`/`_lane9` python process and no visible window.**

## Regression checks run

| check | command | result |
|---|---|---|
| pre-existing ASR selftest | `py -3 _main\asr02-selftest.py` | **rc=0** |
| registered parity arms | `py -3 -m asr.parity --arm en-8s --arm pt-15s` | **GREEN**, both EXACT, ratio 1.0 |
| transcript unchanged by the cures | sha256 before/after | **identical** `b7e338fa06da5301` |

## What this lane did NOT do

* **Did not** wire the ASR to a capture device. That is `src/capture/*` (not mine) and lanes
  L2/WASAPI. This receipt proves the **ASR half** on real audio; nothing here closes the
  capture→WAV→ASR chain end to end. (`git diff HEAD` does list `src/capture/*` and
  `src/index/*` files as modified — those are **concurrent lanes'** work, L2's WASAPI audio
  and L4's index; I made no edit there.)
* **Did not** port the Nemotron `lang_id` table (`pt-BR: 12`, `auto: 101`) into this engine.
  It belongs to a different export, per `docs/model-specs/README.md` §3-§4.
* **Did not** claim a human-labelled WER. No labelled corpus exists on this box.
* **Did not** modify `src/capture/*`, `src/index/*`, `src/ui/*`, or `build.cmd`.
* **Did not** `git rm -r _main/_lane9-ctl` — 10 stale pre-cure files still committed from
  another lane's freeze commit `51f84cc`. Removing them edits the owner's delivery snapshot, so
  it is **his call**, not mine. They are inert: nothing references them.
* **Did not** `git commit` — brief rule 7 defers commits until the gate is green; it is green
  (5/5, rc=0, N=2), but a concurrent lane is committing to this tree and I will not race it.

## SELF-AUDIT — confidence, what would move it, what is missing

| claim | confidence | what would move it |
|---|---|---|
| The ASR transcribes real speech end-to-end | **HIGH** | N=2 gate runs + N=2 parity runs, byte-identical transcripts, transcript hash unchanged by every cure |
| 0.0 % WER vs the oracle | **HIGH as agreement** | a labelled corpus would change what the number *is*; that is the owner's call, not a measurement I can take |
| This export is not language-conditioned | **HIGH** | read off the loaded sessions, and `docs/model-specs/README.md:208` says the same about a sibling export |
| `--language` is refused, never swallowed | **HIGH** | CLI rc=2 measured; `arm_d`/`arm_b`/`selfcheck` all exercise it |
| `--provider cuda` is refused | **HIGH** | CLI rc=2 measured, plus 7-state matrix, plus a verifier that neutered the cure and watched ARM D go red |
| ownership respected | **HIGH for src/** | a concurrent lane also writes `src/asr/runner.py` and `transcribe.py`; both are in my declared scope, and a `git log -p` per file would be needed to attribute authorship, which I did not do |

**Protocols missing.** (1) No **human listening** — POPULATION 0 clips judged by ear; "real
speech" rests on the corpus manifest and the oracle's agreement, not on my ear. (2) **Machine
CPU during my runs: NOT MEASURED** — concurrent lanes were active and I never sampled load, so
no RTFx or timing number in this receipt is claimed as a clean-box measurement. (3) **N=2, not
N=3+** on the gate. (4) **No third review** of the two fixes made after pass 2 (F4's CPU arm,
F6's docstring); the `selfcheck` boxes cover F4, but F6 is a wording change nothing mechanical
can falsify.

**Gate doubts, named.** The gate still asserts against an **oracle produced by another
engine**, so it cannot detect an error both engines share — it can only detect disagreement.
The `ARM_A_MAX_WER = 0.0` threshold will fail a legitimately re-transcribed accent variant
(verifier pass 2 flagged this and it is undecided): it is tight because the pre-existing parity
lock is already exact, and loosening it would be a judgement call about what "agreement" is
worth, which is the owner's. And ARM D proves the *refusal fires*, not that CUDA work would
have been correct if it had loaded — untestable here, since CUDA does not load.