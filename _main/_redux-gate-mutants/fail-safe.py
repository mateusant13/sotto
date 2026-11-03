"""O INTERRUPTOR DOS MOTORES: streaming com o painel aberto, lote com ele fechado.

PORQUE E' QUE ISTO VIVE NUM MODULO PROPRIO. `worker/sotto_worker.py` esta' debaixo
do ratchet estrutural (`_main/code-health-oracle.py`: bytes, linhas, defs, classes,
funcao mais longa, `except: pass`, `global` -- nenhum pode piorar) e a classe
`ReduxHiddenSwitch` mais as constantes que ela fecha em volta cresceram para mais
de um terco do ficheiro. A cura que o proprio ratchet nomeia e' esta: extrair, sem
tocar no comportamento. `sotto_worker.py` importa tudo de volta pelos MESMOS
nomes, por isso nenhum chamador (a shell, o `main()`, os oraculos) muda.

ESTE MODULO NAO IMPORTA `sotto_worker`. E' a regra do `engine_policy.py` ao lado, e
pela mesma razao: um modulo que importasse o worker pela metade seria a segunda
tabela que o repo inteiro existe para nao ter. O que ele precisa do resto do repo
entra por IMPORT de modulos irmaos (`live_queue`, `engine_policy`) ou esta' aqui,
movido verbatim: o `TARGET_SR`, o `REDUX_PRODUCER`, os limites do lote, o leitor da
visibilidade da shell, os manifestos de checkpoint e as duas medidas de memoria.

O QUE A CLASSE FAZ (o porque esta' escrito na docstring dela, palavra por palavra,
como estava no worker): o que para' e' o DECODE em streaming, nao o tap; o audio
que espera NUNCA e' deitado fora (RAM e depois disco); e o lote corre fora da
thread do ASR para nao encher a fila e perder audio.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))

#: Taxa de amostragem do produto. O interruptor escreve WAV a esta taxa e conta o
#: audio em segundos a partir dela (`samples / TARGET_SR`), por isso o numero tem
#: de ser o mesmo que o resto do worker usa.
TARGET_SR = 16000


def _pmc():
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    psapi = ctypes.WinDLL("psapi")
    k32 = ctypes.WinDLL("kernel32")
    # Without explicit argtypes ctypes marshals the pointer as a 32-bit int and
    # the call fails, which is why this used to report -1.0.
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = k32.GetCurrentProcess()
    ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb)
    return (ok, c)


def peak_rss_mb() -> float:
    """Peak working set of THIS process, read from the OS. Never estimated."""
    ok, c = _pmc()
    return c.PeakWorkingSetSize / (1024.0 * 1024.0) if ok else -1.0


def current_rss_mb() -> float:
    ok, c = _pmc()
    return c.WorkingSetSize / (1024.0 * 1024.0) if ok else -1.0


def err(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


try:                       # a fila de audio vivo (ver worker/live_queue.py)
    import live_queue as _live_queue
except Exception:          # pragma: no cover -- o import falha so' fora do repo
    _live_queue = None

try:                       # a politica dos motores (ver worker/engine_policy.py)
    import engine_policy as _policy
except Exception:          # pragma: no cover -- o import falha so' fora do repo
    _policy = None

#: A DECISAO do shedding e' UMA so', e ela vive ao lado da shell
#: (`app/webview/load_shedding.py`): a tabela dos motores, os limiares e a
#: histerese. O worker a IMPORTA em vez de ter a sua -- `_policy.shedding()`
#: carrega-a por caminho, porque o worker corre de `worker/` e a shell de
#: `app/webview/`, e o `None` degrada para o nivel publicado pela shell.
_SHEDDING_PATH = os.path.join(os.path.dirname(HERE), "app", "webview",
                              "load_shedding.py")


#: How long the panel must stay hidden before the batch engine takes over.
REDUX_HIDDEN_AFTER_DEFAULT_S = 20.0
#: How much accumulated audio one batch invocation covers. It is the granularity
#: of the light path: a longer window is fewer model loads and later text.
REDUX_BATCH_INTERVAL_DEFAULT_S = 15.0
#: Bound on the audio held in RAM while hidden. Without it, "accumulate" is an
#: unbounded buffer on a panel the owner may leave closed for hours.
REDUX_MAX_AUDIO_DEFAULT_S = 120.0
#: The BATCH engine's runner — ANOTHER LANE'S FILE. This lane names it, calls it
#: and never writes it. Contract: `python redux_batch.py --wav PATH --json` ->
#: JSONL on stdout, `{"type":"caption","text":…,"start":<s>,"end":<s>,"producer":"redux"}`.
REDUX_RUNNER_DEFAULT = os.path.join(HERE, "redux_batch.py")
#: The checkpoint that runner LOADS when it is invoked with no `--model-dir`,
#: RELATIVE to the runner's own directory — `redux_batch.py` resolves it exactly
#: this way (`HERE = Path(__file__).resolve().parent`, then
#: `DEFAULT_MODEL_DIR = HERE / "models" / "parakeet-redux-ternary"`). `_run_runner`
#: passes no `--model-dir`, so this is the directory every batch pass will open.
#: Keep it in step with `redux_batch.py`: the gate below must refuse to arm on a
#: checkpoint the runner cannot LOAD.
REDUX_CHECKPOINT_RELPATH = os.path.join("models", "parakeet-redux-ternary")
#: The manifests `redux_batch.load_runtime` demands, in ITS order: the first one
#: missing is the `SystemExit` that kills the pass. The DIRECTORY existing is not
#: the test — a directory without these loads nothing.
REDUX_CHECKPOINT_FILES = ("config.json", "model.safetensors", "ternary.json")
#: The shell's visibility channel — written by `app/webview/sotto_webview.py`
#: (`PanelVisibilityWriter`), read here and nowhere else.
REDUX_VISIBILITY_DEFAULT = os.path.join(
    os.path.dirname(HERE), "_main", "panel-visibility.json")
#: THE FIELD THAT OPENS THE CANONICAL TRANSCRIPT. `app/electron/history-source.js:51`
#: (`CANONICAL_PRODUCER = 'redux'`) accepts a line only when `meta.producer` is
#: literally this string, and `grep -rn producer worker/` had ZERO matches before
#: this constant existed — so "History · Redux" was decorative and the archive
#: took no new line. This is the worker's half of that contract.
REDUX_PRODUCER = "redux"
#: A batch invocation may not run forever: a hung runner would silently freeze
#: the light path while the panel is closed, which looks exactly like "working".
REDUX_RUNNER_TIMEOUT_DEFAULT_S = 180.0
#: Below this much audio a batch invocation is not worth a model load.
REDUX_MIN_AUDIO_S = 1.0
#: FREE physical memory a batch invocation is allowed to start under, in MB.
#: The runner's own documented peak is ~3.9 GB (the kestrel int8 kernel is
#: unavailable on this box, so it falls back to the dense weight form) and the
#: streaming model stays resident while the panel is hidden, so the default is
#: that peak plus a margin. MEASURED reason this exists: while another job held
#: 3.5 GB, a sibling process could not allocate a ~1 GB ONNX session at all
#: ("bad allocation"). A pass that cannot fit should be DEFERRED, not attempted:
#: the audio stays buffered and the next tick retries.
REDUX_MIN_FREE_MB_DEFAULT = 4600.0

# ── THE LIVE OVERLAY (lane S3) — a second pass POR CIMA of every live line ──
# OWNER 2026-10-12, verbatim: *"nemotron a transcrever ao vivo e o parakeet
# redux POR CIMA de tudo o que e falado ao vivo, porque tem maior qualidade."*
# and *"o historico nao e pra ser NUNCA o historico do live nvidia. e pra ser do
# parakeet redux"* (app/panel/panel.js).
#
# DEFAULT OFF, for the same measured reason the batch arm is: the overlay pays a
# second ASR decode on top of the live one (measured ~1.0-1.4 s per 5 s window,
# ~615 MB peak RSS, ~128% of one core at threads=2), so a switch that lands
# before the pass is proven means a slower, fatter live run exactly while the
# owner is not looking. With the flag off this file is byte-identical to the run
# before this lane existed: not one read, not one branch, not one extra byte.
#
# WHAT IT DOES: every line the live engine CLOSES is HELD, and exactly ONE line
# per segment is published — the Redux text when the pass answered, the live text
# byte for byte when it did not. The panel already replaces a row in place when a
# second event carries the same (source, start) identity, so the Redux text lands
# in the SAME row the live partials were growing, and the history line is the
# Redux version. The contract lives in worker/redux_live.py.
REDUX_LIVE_DEFAULT = False
#: The overlay's checkpoints, RELATIVE to this file. BOTH are named because
#: `load_backend` is given both and picks by engine; the gate below refuses when
#: the engine it would open is not on disk.
REDUX_LIVE_TERNARY_RELPATH = os.path.join("models", "parakeet-redux-ternary")
REDUX_LIVE_ONNX_RELPATH = os.path.join("models", "parakeet-redux-onnx-int4")
#: WHAT EACH ENGINE'S CHECKPOINT ACTUALLY IS. The one list, applied to both
#: directories, was WRONG, and it is the reason the owner's captions were always
#: the Nemotron's. MEASURED 2026-10-18 in the owner's own tree:
#:
#:     worker/models/parakeet-redux-onnx-int4/   config.json
#:                                           encoder-model.onnx
#:                                           decoder_joint-model.onnx
#:                                           preprocessor.onnx
#:                                           vad-model.onnx
#:                                           vocab.txt   transcribe.py
#:
#: An ONNX export has no `model.safetensors` and no `ternary.json` -- it never
#: will, that is what an ONNX export IS. So `redux_live_missing()` reported the
#: ONNX directory as incomplete even with every one of its real files present,
#: `--redux-live` was REFUSED, and the flag's own help describes what happens
#: next: *"Refused, and the run keeps streaming untouched, if the engine's
#: checkpoint is not on disk."* The owner had the accurate model sitting on his
#: disk and was told no.
#:
#: ONNX IS THE MEASURED DEFAULT (`REDUX_LIVE_ENGINE_DEFAULT`), and its comment
#: below already says ONNX is 615 MB / 8.33x RTF against the ternary's 3856 MB
#: for byte-identical text. The gate was therefore refusing the cheap engine
#: while asking for the expensive one's files.
REDUX_LIVE_ONNX_CHECKPOINTS = (
    "config.json", "encoder-model.onnx", "decoder_joint-model.onnx",
    "preprocessor.onnx", "vad-model.onnx", "vocab.txt",
)
REDUX_LIVE_TERNARY_CHECKPOINTS = ("config.json", "model.safetensors", "ternary.json")
#: Kept as a NAME for anything that imported the old constant. It is no longer
#: used to gate anything -- the two lists above are.
REDUX_LIVE_CHECKPOINT_FILES = REDUX_LIVE_TERNARY_CHECKPOINTS
#: ONNX is the measured default: 615 MB peak, 8.33x RTF on a 15 s clip, versus
#: the ternary's 3856 MB and 2.2x the latency for byte-identical text (the packed
#: int8 CPU kernel is absent from the published kestrel wheel).
REDUX_LIVE_ENGINE_DEFAULT = "onnx"
#: Seconds of rolling PCM the overlay retains. A line whose own start has been
#: trimmed is refused (and shipped as the live text), so this must exceed the
#: longest line the live engine can hold open.
REDUX_LIVE_KEEP_S = 90.0
#: The overlay's own deadline. A decode that outran it is released as the live
#: text: a late Redux line is worse than the live one the owner can read now.
REDUX_LIVE_DEADLINE_S = 4.0
#: Bound on held segments. The count includes the one being decoded.
REDUX_LIVE_MAX_QUEUE = 6
#: Below this much audio a segment is not worth a decode.
REDUX_LIVE_MIN_AUDIO_S = 1.0
#: Threads the ONNX session gets. Measured: 2 is the sweet spot on this box.
REDUX_LIVE_THREADS = 2


def redux_live_dirs():
    """(onnx_dir, ternary_dir) the overlay would open, resolved against this file."""
    here = os.path.dirname(os.path.realpath(__file__))
    return (os.path.join(here, REDUX_LIVE_ONNX_RELPATH),
            os.path.join(here, REDUX_LIVE_TERNARY_RELPATH))


def redux_live_missing(onnx_dir, ternary_dir):
    """The manifests NOT on disk under each dir; ([], []) when both can load.

    PER-ENGINE, since 2026-10-18. It used to test `REDUX_LIVE_CHECKPOINT_FILES`
    (the TERNARY's list) against BOTH directories, so the ONNX export -- which
    has no safetensors and never will -- was reported incomplete with every real
    file present, and `--redux-live` was refused on a fully-downloaded engine.
    See the two lists above for the measurement.
    """
    return ([name for name in REDUX_LIVE_ONNX_CHECKPOINTS
             if not os.path.isfile(os.path.join(onnx_dir, name))],
            [name for name in REDUX_LIVE_TERNARY_CHECKPOINTS
             if not os.path.isfile(os.path.join(ternary_dir, name))])


def _free_memory_mb():
    """Free physical memory in MB, or None when it cannot be measured.

    `None` is NOT "no memory": it means the measurement itself failed, and a gate
    that cannot measure must not block the work it would otherwise allow. The
    caller treats `None` as "go ahead and try" — a failed measurement is not
    evidence of pressure, and inventing a refusal from it would be this repo's
    oldest bug wearing a new hat.
    """
    try:
        import psutil

        return round(psutil.virtual_memory().available / 1048576.0, 1)
    except Exception:
        return None


class PanelVisibilityReader:
    """The shell's visibility file, read with the HARD RULE's fail-safe.

    THE SHAPE (frozen by `app/webview/sotto_webview.py`):

        {"visible": <bool>, "since_ms": <int>, "pid": <int>,
         "writtenAtEpoch": <float>, "staleAfterSeconds": <float>, ...}

    THE FAIL-SAFE IS THE WHOLE POINT, and it is in one direction on purpose.
    EVERY way this reader can fail to get an answer — no file, an unreadable
    file, a shape it does not recognise, a `visible` that is not a bool — returns
    `visible=True`, i.e. KEEP STREAMING. "The file said hidden" must never be
    produced by a file that meant nothing.

    STALENESS IS THE SAME RULE. A shell that died leaves its last sentence on
    disk forever; obeying `visible:false` from a dead producer would silence the
    only transcriber this tree has. So `writtenAtEpoch` is checked against
    `staleAfterSeconds`, and a stale dump also reads as visible. A dump with NO
    `writtenAtEpoch` is treated as fresh and its `visible` is believed: that is
    the shape a HAND-WRITTEN file (a probe, a human) has, and refusing it would
    make the channel untestable by the very probes that must drive it.
    """

    #: The levels the shell may publish under `shed` (owner, 2026-10-30:
    #: *"alta: desliga nemotron, so parakeet; muito alta: desliga parakeet
    #: tambem"*). Anything else is not a level.
    SHED_LEVELS = ('leve', 'alta', 'muito-alta')

    def __init__(self, path):
        self.path = path
        self.reads = 0
        self.fallbacks = 0
        self.last_reason = None
        self.last_payload = None

    #: The engine-park reasons the shell may publish under `park` (owner,
    #: 2026-11-03: the worker must LOSE ITS MODEL, never its PROCESS).
    PARK_REASONS = ('captions', 'vram')

    def shed(self, default='leve'):
        """O nivel de shedding publicado pela shell (`leve` por omissao).

        THE SAME FAIL-SAFE DIRECTION AS `visible`, and it is the whole point: a
        file with no `shed`, an unreadable one, or a value that is not one of
        `SHED_LEVELS` reads as **`leve`** -- i.e. CHANGE NOTHING. A level
        invented out of a broken file would silence the only transcriber this
        tree has, which is exactly the failure the owner already paid for.

        Read from `last_payload`, so it is the SAME read the visibility decision
        used: two reads of the same file per tick would be two chances to
        disagree with each other.
        """
        payload = self.last_payload
        if not isinstance(payload, dict):
            return default
        level = payload.get('shed')
        if isinstance(level, str) and level.strip() in self.SHED_LEVELS:
            return level.strip()
        return default

    def park(self):
        """O estacionamento do MOTOR pedido pela shell (`captions`/`vram`).

        ORDEM DO DONO, 2026-11-03. FAIL-SAFE PARA O LADO QUE NAO SILENCIA: uma
        chave ausente, ilegivel ou inventada le' como **sem pedido**, e o motor
        fica carregado -- a mesma direccao do `shed`, pelo mesmo motivo (um
        pedido nascido de um ficheiro partido nao pode calar o unico
        transcritor desta arvore).

        E' um pedido DIFERENTE do `shed`, por isso vive numa chave diferente e
        nao os dois no mesmo campo: `shed` e' PRESSao DA MAQUINA (medida), e
        este e' o ESTACIONAMENTO que o shell decide (o player esta' a fornecer
        as legendas, ou outro app quer a GPU). Mistura-los faria o monitor de
        carga a apagar o pedido do shell no tick seguinte.
        """
        payload = self.last_payload
        if not isinstance(payload, dict):
            return None
        value = payload.get('park')
        if isinstance(value, str) and value.strip() in self.PARK_REASONS:
            return value.strip()
        return None

    def read(self):
        """-> (visible: bool, why: str, age_s: float|None). Never raises."""
        self.reads += 1
        try:
            with open(self.path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except FileNotFoundError:
            return self._fallback("no-file", None)
        except Exception as exc:
            return self._fallback(f"unreadable:{type(exc).__name__}", None)
        if not isinstance(payload, dict) or not isinstance(payload.get("visible"), bool):
            return self._fallback("unknown-shape", None)
        self.last_payload = payload
        epoch = payload.get("writtenAtEpoch")
        if isinstance(epoch, (int, float)):
            age = max(0.0, time.time() - float(epoch))
            limit = payload.get("staleAfterSeconds")
            if isinstance(limit, (int, float)) and age > float(limit):
                return self._fallback(f"stale(age={age:.1f}s>limit={limit}s)", age)
            self.last_reason = "fresh"
            return bool(payload["visible"]), "fresh", age
        self.last_reason = "fresh-no-epoch"
        return bool(payload["visible"]), "fresh-no-epoch", None

    def _fallback(self, why, age):
        self.fallbacks += 1
        self.last_reason = why
        return False, why, age


def redux_checkpoint_dir(runner):
    """The checkpoint the batch runner opens when it is given no `--model-dir`.

    Resolved the way `redux_batch.py` resolves its own default — relative to the
    runner's directory (`HERE = Path(__file__).resolve().parent`) — because
    `_run_runner` passes the runner no `--model-dir` and the runner therefore
    loads exactly this path, whatever directory the worker was started from.
    """
    return os.path.join(os.path.dirname(os.path.realpath(runner)),
                        REDUX_CHECKPOINT_RELPATH)


def redux_checkpoint_missing(model_dir):
    """The manifests NOT on disk under `model_dir`; `[]` when it can load."""
    return [name for name in REDUX_CHECKPOINT_FILES
            if not os.path.isfile(os.path.join(model_dir, name))]


# ── A POLITICA DOS MOTORES VIVE EM `worker/engine_policy.py` ─────────────────
# Os DOIS motores de fundo (o parakeet ONNX e o executor ternario), a ordem dos
# niveis e a forma dos numeros do log estao la', com o porque escrito. Aqui
# ficam as referencias: extrair e' a cura que o proprio ratchet estrutural
# (`_main/code-health-oracle.py`) pede -- este ficheiro nao pode crescer.
ParakeetEngine = _policy.ParakeetEngine
RunnerEngine = _policy.RunnerEngine


class ReduxHiddenSwitch:
    """Streaming while the panel is OPEN, batch while it is CLOSED.

    WHAT "STOPS" MEANS — and this is the part that must not be got wrong. The
    thing that stops is the STREAMING DECODE: the 560 ms encoder+RNNT pass whose
    cost the owner is paying for while nobody is looking. THE TAP DOES NOT STOP,
    because the batch pass transcribes "the accumulated audio" and there is no
    audio to accumulate from a closed device. A hidden panel therefore costs one
    WAV append per 100 ms block plus one batch invocation per
    `batch_interval_s` — LEVE, and the opposite of a forward pass per chunk.

    THREE GATES, ALL OF WHICH MUST BE OPEN BEFORE THE FIRST CHUNK IS CUT:
      1. THE FLAG/GATE (`--redux-when-hidden`, or the shipped default). With the
         switch not constructed the worker is the plain streaming worker.
      2. THE BACKGROUND ENGINE must be on disk: THE PARKEET (`ParakeetEngine`,
         the ONNX int4 export) OR, for the ternary checkpoint, the runner FILE
         *AND* the checkpoint it will LOAD. A flag that switches to an engine
         which is not there would trade the ONLY transcriber in this tree for
         nothing — verbatim the failure the HARD RULE in AGENTS.md was written
         after. THE FILE ALONE IS NOT THE ENGINE (the gate until 2026-10-11, and
         a trap): `_run_runner` passes no `--model-dir`, so the runner loads its
         own `models/parakeet-redux-ternary`, and a runner on disk with that
         checkpoint absent dies in `redux_batch.load_runtime`'s SystemExit on
         EVERY pass while the switch has already cut streaming. Either absence is
         REFUSED LOUDLY, with the missing path, and the worker stays streaming.
      3. THE FILE MUST BE FRESH *AND* SAY HIDDEN for longer than
         `hidden_after_s` (see `PanelVisibilityReader`: a stale or unreadable
         file reads as VISIBLE, so gate 3 fails closed towards streaming).

    THE AUDIO THAT WAITS IS NEVER DROPPED (owner, 2026-11-01). While a pass is
    not allowed to run — the panel is closed, the level says `shed`, the memory
    floor defers it — the blocks go into `live_queue.PendingAudio`: RAM up to
    `max_audio_s`, then a DISK SPOOL, in order and lossless. When the load falls
    the pass reads EVERYTHING that accumulated. The old behaviour (trim the
    oldest block over 120 s) deleted the owner's audio silently; the spool cannot.

    THE BATCH PASS IS OFF-THREAD, and deliberately: the runner is a separate
    process with a model load, and blocking the ASR thread on it would stall
    `audio_q` until it overflowed and DROPPED audio — the accumulated audio the
    batch path exists to transcribe. So the accumulated PCM is SNAPSHOT and
    handed to the runner thread, while the ASR thread keeps consuming the queue
    into a fresh buffer. Nothing is transcribed twice and nothing is dropped.

    STDOUT STAYS ONE THREAD. The runner thread does not emit: it pushes parsed
    caption dicts onto a queue and the ASR thread drains and emits them, so the
    JSONL contract keeps its single writer even while the batch pass runs.
    """

    def __init__(self, enabled, reader, runner, log_fn,
                 hidden_after_s=REDUX_HIDDEN_AFTER_DEFAULT_S,
                 batch_interval_s=REDUX_BATCH_INTERVAL_DEFAULT_S,
                 max_audio_s=REDUX_MAX_AUDIO_DEFAULT_S,
                 runner_timeout_s=REDUX_RUNNER_TIMEOUT_DEFAULT_S,
                 wav_dir=None, armed_by="--redux-when-hidden",
                 min_free_mb=REDUX_MIN_FREE_MB_DEFAULT, model_dir=None,
                 engine=None, probe=None, pending=None, spool_dir=None,
                 engine_min_free_mb=None, engine_window_s=None,
                 unload_when_hidden=False):
        #: O MODELO AO VIVO SO' E' LARGADO POR PRESSAO, NUNCA PELA VISAO
        #: (ordem do dono, 2026-11-03, verbatim: *"era pra ta com o modelo
        #: sempre. e so descarregar quando o pc precisa da vram ou gpu em
        #: outros apps"*). O caminho `hidden_after_s` -- painel escondido ha'
        #: 20 s -> `batch` -> o nemotron cai -- recarregava o modelo a cada
        #: abertura de painel (14-26 s medidos de recarga) e o dono via
        #: `carregando modelo…` ao apertar Ctrl+Espaco com o video a tocar.
        #: Fica DESLIGADO por omissao; liga-se explicitamente onde o
        #: comportamento e' o que se esta' a provar (as arms do oraculo).
        #: A pressao REAL continua a mandar: `_measure` (commit/CPU) e o
        #: guarda de VRAM seguem a largar o motor sem esta bandeira.
        self.unload_when_hidden = bool(unload_when_hidden)
        self.enabled = bool(enabled)
        self.reader = reader
        self.runner = runner
        self.log = log_fn
        self.armed_by = str(armed_by)
        self.min_free_mb = float(min_free_mb or 0.0)
        self.engine_min_free_mb = float(
            _policy.REDUX_ENGINE_MIN_FREE_MB if engine_min_free_mb is None
            else engine_min_free_mb)
        self.engine_window_s = max(0.5, float(
            _policy.REDUX_ENGINE_WINDOW_S if engine_window_s is None
            else engine_window_s))
        self.hidden_after_s = float(hidden_after_s)
        self.batch_interval_s = max(1.0, float(batch_interval_s))
        self.max_audio_s = max(self.batch_interval_s, float(max_audio_s))
        self.runner_timeout_s = float(runner_timeout_s)
        self.wav_dir = wav_dir
        self.spool_dir = spool_dir
        # ── gate 2, decided ONCE, at construction, and stated in the log ─────
        # TWO facts, not one: the runner FILE and the checkpoint it will LOAD.
        # `_run_runner` invokes the runner with no `--model-dir`, so the runner
        # resolves its own `models/parakeet-redux-ternary` — and with that
        # directory absent (measured on this box 2026-10-11: `worker/models/`
        # holds only the nemotron export) every batch dies in
        # `redux_batch.load_runtime`'s SystemExit. Armed on the file alone, the
        # switch would cut the streaming decode in the asr thread (`if mode ==
        # "batch": ... continue`) and leave the owner with NO transcriber at all,
        # silently. So the checkpoint is part of the gate, and the refusal names
        # the path that is missing.
        self.runner_available = os.path.exists(self.runner)
        self.model_dir = os.path.abspath(
            model_dir if model_dir else redux_checkpoint_dir(self.runner))
        self.model_missing = redux_checkpoint_missing(self.model_dir)
        self.model_available = not self.model_missing
        # ── WHO RUNS THE BATCH: the parakeet, and only then the runner ───────
        # The ONNX int4 parakeet is the engine this machine actually HAS (the
        # ternary checkpoint is not on disk), so it is preferred. `engine`
        # defaults to a real `ParakeetEngine`; an injected object must offer
        # `available`, `name()`, `load()`, `release()`, `transcribe(pcm)`.
        # `RunnerEngine` keeps the ternary path and its contract (`--wav --json`)
        # exactly as it was.
        #: Os tres factos do worker que o lote extraido le' (`engine_policy`):
        #: a taxa, o produtor das linhas e o medidor de RSS. Passam como
        #: atributos para a politica nao importar o worker (seria a segunda
        #: tabela) nem duplicar constantes.
        self.rate = TARGET_SR
        self.producer = REDUX_PRODUCER
        self.rss = current_rss_mb
        self.engine = (engine if engine is not None
                       else ParakeetEngine(
                           REDUX_LIVE_ENGINE_DEFAULT, redux_live_dirs,
                           redux_live_missing, current_rss_mb,
                           threads=REDUX_LIVE_THREADS, log_fn=log_fn))
        self.runner_engine = RunnerEngine(runner, redux_checkpoint_dir,
                                          redux_checkpoint_missing, log_fn=log_fn)
        self.engine_available = bool(getattr(self.engine, "available", False))
        self.batch_kind = ("parakeet" if self.engine_available
                           else ("runner" if self.runner_engine.available
                                 else None))
        # A FORMA DESTA EXPRESSAO E' PINADA por `_main/redux-flag-gate.py`
        # (claim `hard-rule`: `self.armed = bool(` seguido de
        # `self.enabled and self.runner_available`), e o pino esta' certo: sem
        # interruptor nao ha' `armed`, e sem motor a parar o nemotron deixaria o
        # dono sem transcritor. A condicao nova -- o PARKEET no disco tambem arma
        # -- entra como o outro ramo do `or`, sem partir a ancora.
        self.armed = bool(
            self.enabled and self.runner_available and self.model_available
            or (self.enabled and self.engine_available))
        self.mode = "stream"
        # ── O NIVEL: a shell publica-o, o worker MEDE-o, obedece-se ao PIOR ──
        # `probe` e' a medicao local (`load_shedding.LoadProbe`): commit % e
        # CPU %, uma leitura por `SAMPLE_INTERVAL_S`. `None` (o omissao do
        # construtor, e o que alguns oraculos usam) deixa a decisao como era:
        # so' o nivel publicado conta. `main()` passa um probe real; o oraculo
        # passa um com leituras escritas.
        self.probe = probe
        shed_module = _policy.shedding(_SHEDDING_PATH, err)
        self._shedder = shed_module.LoadShedding() if shed_module is not None else None
        self._fed_at = None
        #: O nivel EM VIGOR (o pior entre o publicado e o medido). Vive aqui para
        #: a linha de log so' sair quando o nivel MUDA -- um log por bloco de
        #: 100 ms seria ruido.
        self._shed = "leve"
        self._shed_published = "leve"
        self._shed_measured = "leve"
        self._shed_why = ""
        self._commit_pct = None
        self._cpu_pct = None
        #: O audio que espera por um motor (RAM -> disco), NUNCA perdido.
        self.pending = pending if pending is not None else (
            _live_queue.PendingAudio(rate=TARGET_SR, ram_s=self.max_audio_s,
                                     spool_dir=spool_dir,
                                     log=(log_fn or (lambda _m: None)))
            if _live_queue is not None else None)
        self.visible = True
        self.why = "boot"
        self.hidden_since = None
        self.switches = 0
        self.segments = 0
        self.segment_lines = 0
        self.batches_kicked = 0
        self.runner_failures = 0
        self.refusals = 0
        self.deferred = 0
        self.stream_chunks_before = 0
        self.batch_seconds = 0.0
        #: O relogio do PROPRIO audio (segundos capturados desde o arranque), para
        #: as linhas do lote levarem `start`/`end` honestos e nao um zero repetido.
        self._audio_clock_s = 0.0
        self._inflight = None
        self._release_when_idle = False
        self._backoff_until = 0.0
        self._captions = queue.Queue()
        self._lock = threading.Lock()

    # -- the log line a boot leaves ----------------------------------------
    def boot_line(self):
        if not self.enabled:
            return
        if self.armed:
            self.log(
                f"REDUX_SWITCH armed=true by={self.armed_by} "
                f"hidden_after_s={self.hidden_after_s} "
                f"batch_interval_s={self.batch_interval_s} "
                f"max_audio_s={self.max_audio_s} min_free_mb={self.min_free_mb} "
                f"runner={self.runner} "
                f"visibility={self.reader.path}")
            # A SEGUNDA linha, de proposito: a primeira e' um contrato congelado
            # (`_main/redux-arm-weights-oracle.py` W6 compara-a com uma regex
            # ancorada em `visibility=...$`), e o que este lane acrescenta e' um
            # FACTO NOVO -- quem corre o lote, de onde, e se a maquina esta' a ser
            # medida localmente. Meter isto na linha de cima partia o contrato
            # para dar a mesma informacao num sitio pior.
            self.log(
                f"REDUX_BATCH_ENGINE engine={self.batch_kind} "
                f"name={self.engine.name()} dir={getattr(self.engine, 'dir', '')} "
                f"missing={','.join(getattr(self.engine, 'missing', []) or []) or 'none'} "
                f"runner_available={str(self.runner_available).lower()} "
                f"checkpoint_available={str(self.model_available).lower()} "
                f"engine_min_free_mb={self.engine_min_free_mb} "
                f"probe={'local' if self.probe is not None else 'shell-only'} "
                f"spool={self.spool_dir}")
        elif not self.runner_available:
            # LOUD, and it is the HARD RULE speaking: without a runner on disk
            # the switch would silence the only transcriber there is, so it is
            # refused and the streaming path is left exactly as it is.
            self.log(
                f"REDUX_SWITCH_REFUSED armed=false reason=runner-missing "
                f"runner={self.runner} — the batch engine is not on disk, so the "
                f"streaming capture is NOT cut while the panel is hidden "
                f"(today it is the only transcriber)")
        else:
            # The runner IS on disk and the checkpoint it will LOAD is not: the
            # distinct reason (and the path) is the whole point of this branch —
            # a bare `armed=false` would leave the next reader hunting for why.
            self.log(
                f"REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing "
                f"runner={self.runner} model_dir={self.model_dir} "
                f"missing={','.join(self.model_missing)} — the batch engine cannot "
                f"LOAD this checkpoint (`redux_batch.load_runtime` exits on the "
                f"first missing manifest), so the streaming capture is NOT cut "
                f"while the panel is hidden (today it is the only transcriber)")

    # -- the mode decision --------------------------------------------------
    def tick(self, now=None):
        """Decide the mode for THIS block, and say so in one line per change."""
        if not self.armed:
            return self.mode
        now = time.time() if now is None else now
        visible, why, age = self.reader.read()
        self.why = why
        if visible:
            self.visible = True
            self.hidden_since = None
        else:
            self.visible = False
            if self.hidden_since is None:
                self.hidden_since = now
                self.log(
                    f"REDUX_VISIBILITY visible=false source={why} "
                    f"age_s={age if age is None else round(age, 2)} "
                    f"hidden_since={round(now, 3)} "
                    f"switch_in_s={self.hidden_after_s}")
        # THE OWNER'S ORDER WEIGHS ON TOP OF VISIBILITY (2026-10-30, verbatim):
        # *"alta: desliga nemotron, so parakeet; muito alta: desliga parakeet
        # tambem. AUDIO SEMPRE fica para processar depois"*. The shell publishes
        # the level in the same file this switch already polls, so no new IPC:
        #
        #     alta        -> "batch"  (the live engine stops, the batch one runs)
        #     muito-alta  -> "shed"   (nothing runs; audio ACCUMULATES, never lost)
        #     leve        -> whatever the visibility says (the behaviour of always)
        #
        # `shed` is honoured ONLY when this switch is armed: with no batch engine
        # on disk, stopping the live one would leave NO transcriber, which is the
        # one thing the HARD RULE forbids. The decision above already refuses to
        # arm in that case, so this is not a second guard -- it is the same fact
        # read where it matters.
        #
        # TWO CHANNELS, ONE DECISION (owner, 2026-11-01: the decision "reads the
        # MEASURED load (commit %, CPU) and records the number that triggered
        # it"). The shell publishes a level in the file this switch already polls;
        # the worker now MEASURES the same two things itself every
        # `SAMPLE_INTERVAL_S` and obeys the WORSE of the two. That is what makes
        # the level exist when the shell wrote nothing (boot, a dead shell,
        # `SOTTO_LOAD_SHED=0`), and the log line carries commit/cpu so the number
        # that decided anything is never a guess.
        shed_published = self.reader.shed()
        measured, commit_pct, cpu_pct, measured_why = self._measure(shed_published)
        shed = _policy.worse_level(PanelVisibilityReader.SHED_LEVELS,
                                   shed_published, measured)
        self._shed_published = shed_published
        self._shed_measured = measured
        # O ESTACIONAMENTO DO MOTOR VEM DA SHELL, E NAO E' CARGA (2026-11-03).
        # `captions`: o player esta' a fornecer as legendas -> larga o AO VIVO e
        # deixa o parakeet no historico. `vram`: outro app quer a GPU -> larga os
        # dois. Em ambos o PROCESSO e a CAPTURA ficam: era o `bridge.stop()` que
        # fazia o audio do dono piscar a cada paragem.
        park = self.reader.park() if hasattr(self.reader, 'park') else None
        if park:
            shed = _policy.worse_level(
                PanelVisibilityReader.SHED_LEVELS, shed,
                'alta' if park == 'captions' else 'muito-alta')
        if shed != getattr(self, '_shed', 'leve') or park != getattr(self, '_park', None):
            self._park = park
            self._shed = shed
            self._shed_why = measured_why
            engines = self._engines_for(shed)
            self.log(
                f"REDUX_SHEDDING level={shed} published={shed_published} "
                f"measured={measured} park={park or 'none'} "
                f"commit_pct={_policy.fmt_num(commit_pct)} "
                f"cpu_pct={_policy.fmt_num(cpu_pct)} "
                f"engines={','.join('%s:%s' % (k, 'on' if v else 'off') for k, v in engines.items()) or 'n/a'} "
                f"why={json.dumps(measured_why or 'the shell decided')} "
                f"visible={str(self.visible).lower()}")
        if shed == "muito-alta":
            wanted = "shed"
        elif shed == "alta":
            wanted = "batch"
        else:
            # A VISAO NAO LARGA O MODELO (ordem do dono, 2026-11-03). Sem esta
            # bandeira o painel escondido deixava o motor AO VIVO caído e a
            # abertura seguinte pagava a recarga -- ver `unload_when_hidden`.
            wanted = "batch" if (
                self.unload_when_hidden
                and not self.visible
                and self.hidden_since is not None
                and (now - self.hidden_since) >= self.hidden_after_s
            ) else "stream"
        if wanted != self.mode:
            self.mode = wanted
            self.switches += 1
            if wanted == "batch":
                why = ('shed-' + str(getattr(self, '_shed', 'leve'))
                       if getattr(self, '_shed', 'leve') == 'alta'
                       else 'hidden-%ss' % self.hidden_after_s)
                self.log(
                    f"REDUX_MODE mode=batch visible={str(self.visible).lower()} "
                    f"reason={why} visibility={self.why} "
                    f"switches={self.switches} engine={self.batch_kind} "
                    f"runner={os.path.basename(self.runner)}")
            elif wanted == "shed":
                self.log(
                    f"REDUX_MODE mode=shed reason=shed-muito-alta "
                    f"visibility={self.why} switches={self.switches} "
                    f"held_s={self.pending_seconds()} "
                    f"note=audio-fica-para-processar-depois")
            else:
                self.log(
                    f"REDUX_MODE mode=stream visible={str(self.visible).lower()} "
                    f"reason={'visible-again' if self.visible else 'boot'} "
                    f"switches={self.switches} segments={self.segments}")
        # ── A CARGA LIBERTA, E O MOTOR VOLTA SOZINHO ─────────────────────────
        # `muito-alta` manda parar o parakeet, e parar e' LARGAR O MODELO: a
        # referencia ao backend cai e o RSS que voltou fica no log. O lote
        # seguinte — que so' e' pedido quando o nivel desce (ver `maybe_kick`) —
        # carrega-o outra vez, na thread do lote. Um lote ja' a correr nao e'
        # interrompido: o `release` espera que ele acabe (`_release_when_idle`),
        # porque matar uma inferencia a meio e' como nao a ter feito.
        if self.mode == "shed":
            if self.in_flight():
                self._release_when_idle = True
            else:
                self._release_when_idle = False
                self._release_engine("shed-muito-alta")
        return self.mode

    # -- a medicao da carga -------------------------------------------------
    def _measure(self, published):
        """A leitura LOCAL da maquina: `(nivel, commit_pct, cpu_pct, razao)`.

        `(published, None, None, "")` quando nao ha' probe (o omissao) ou quando
        o modulo da decisao nao esta' neste checkout: a decisao fica exactamente
        a de antes, com o nivel publicado. Uma amostra so' por
        `SAMPLE_INTERVAL_S` -- as outras devolvem a ultima (`fresh=False`) sem
        mexer no `LoadShedding`, senao a mesma leitura contaria como cinco
        confirmacoes de descida.
        """
        if self.probe is None or self._shedder is None:
            return published, None, None, ""
        try:
            commit_pct, cpu_pct, fresh = self.probe.sample()
        except Exception as exc:  # noqa: BLE001 -- medir nao pode matar o audio
            self.probe = None
            self.log(f"REDUX_LOAD_PROBE_FAILED {type(exc).__name__}: {exc} — "
                     f"a decisao volta a ser a da shell")
            return published, None, None, ""
        if not fresh:
            return self._shed_measured, self._commit_pct, self._cpu_pct, self._shed_why
        level, _changed, why = self._shedder.observe(commit_pct, cpu_pct)
        self._commit_pct = commit_pct
        self._cpu_pct = cpu_pct
        self._shed_why = why
        return level, commit_pct, cpu_pct, why

    @staticmethod
    def _engines_for(level):
        """`{'nemotron': bool, 'parakeet': bool}` do nivel -- se o modulo existir."""
        module = _policy.shedding(_SHEDDING_PATH, err)
        table = getattr(module, "ENGINES", None) if module is not None else None
        if isinstance(table, dict) and level in table:
            return dict(table[level])
        return {}

    def _release_engine(self, reason):
        release = getattr(self.engine, "release", None)
        if not callable(release):
            return False
        try:
            released = bool(release(reason=reason))
        except Exception as exc:  # noqa: BLE001 -- largar memoria nao pode matar o audio
            self.log(f"REDUX_ENGINE_RELEASE_FAILED reason={reason} "
                     f"error={type(exc).__name__}: {exc}")
            return False
        if released:
            # A LARGADA E' UMA ACCAO DO INTERRUPTOR, por isso e' o interruptor que
            # a diz: o log fica completo quer o motor seja o parakeet real (que
            # acrescenta o RSS que voltou) quer seja um objecto injectado.
            self.log(f"REDUX_ENGINE_RELEASE reason={reason} engine={self.batch_kind} "
                     f"held_s={self.pending_seconds()} "
                     f"— a carga mandou parar; recarrega sozinho quando a carga libertar")
        return released

    # -- the accumulation ---------------------------------------------------
    def add_audio(self, block):
        """Hold one 16 kHz block for the background engine. NEVER DROPS IT.

        The hold is `live_queue.PendingAudio`: RAM up to `max_audio_s` and then a
        DISK SPOOL, in order and byte-exact. The block also advances the audio
        clock, which is what gives the transcribed lines honest `start`/`end`.
        """
        self._audio_clock_s += int(getattr(block, "size", 0)) / float(TARGET_SR)
        if self.pending is None:
            return False
        return self.pending.add(block)

    def pending_seconds(self):
        return self.pending.seconds() if self.pending is not None else 0.0

    def take_pending(self):
        """Snapshot and clear: the engine gets THIS audio, once, in order."""
        if self.pending is None:
            return [], 0
        return self.pending.take_all()

    # -- the batch pass -----------------------------------------------------
    def maybe_kick(self, reason="interval"):
        """Start a batch pass if one is not already running and it is worth it.

        THE INTERVAL IS A FLOOR, NOT A HINT. This is the measured bug the first
        version of this method shipped: it delegated straight to `flush_pending`,
        whose only floor is `REDUX_MIN_AUDIO_S` (the point at which a model load
        is worth it at all), so on the live loop — which calls this once per
        100 ms block — it kicked a batch every time one second of audio had
        accumulated. Twelve invocations for sixteen seconds of hidden audio, and
        with a runner that takes seconds to load its weights the light path
        becomes a queue of model loads: the exact opposite of "um transcritor
        LEVE". The interval gate belongs HERE, where it means "how much audio one
        pass covers", and the minimum belongs in `flush_pending`, where it means
        "do not wake the model for a rounding error".

        This is also the only caller that RESPECTS the memory floor, because it is
        the only one that can afford to wait: a deferred interval pass keeps its
        audio and retries on the next tick (see `flush_pending`).
        """
        if not self.armed or self.mode != "batch":
            return False
        if self.pending_seconds() < self.batch_interval_s:
            return False
        return self.flush_pending(reason, respect_memory_floor=True)

    def flush_pending(self, reason="flush", respect_memory_floor=False):
        """One batch pass over the audio held NOW, whatever the mode is.

        THE TAIL IS THE POINT. The panel coming back must not LOSE the audio that
        accumulated since the last interval pass, and it must not DELAY the return
        to streaming either — "panel visible again -> back to streaming
        immediately". So this kick is allowed in EITHER mode and always runs
        off-thread, exactly like the interval ones; its lines come out through
        `drain_captions()` while the stream is already live again. Ordering is
        carried by `start`/`end` on every line, not by arrival order.

        This is the path the TAILS take (panel visible again, stream end), so it
        deliberately does NOT apply the interval floor: whatever is left must be
        transcribed. `REDUX_MIN_AUDIO_S` is the only floor, and it exists so a
        few milliseconds of audio does not pay for a model load.

        THE MEMORY FLOOR IS APPLIED ONLY WHEN WAITING IS FREE. `maybe_kick` (the
        interval path) passes `respect_memory_floor=True`: under pressure the pass
        is DEFERRED and its audio stays buffered, so the next tick retries and
        nothing is lost. A TAIL cannot be deferred — there is no next tick, so a
        deferral would simply drop the owner's last minute — so a tail ATTEMPTS
        under pressure and says in the log that it did. Both outcomes are stated;
        neither is silent.
        """
        if not self.armed:
            return False
        if self._inflight is not None and self._inflight.is_alive():
            # A pass is already running. The audio keeps accumulating and the
            # next tick will cover it; nothing is dropped by refusing here.
            return False
        if time.time() < self._backoff_until:
            # O lote anterior falhou: o audio esta' de volta na fila e o motor
            # arrefece (ver `_park`). Isto e' o que impede um motor partido de
            # carregar 615 MB a cada segundo -- um busy loop com factura de RAM.
            return False
        # O PISO DE MEMORIA E' O DO MOTOR QUE VAI CORRER. O executor ternario tem
        # um pico documentado de ~3,9 GB; o parakeet ONNX tem 615 MB medidos. Um
        # piso unico de 4600 MB adiava um lote de 615 MB numa maquina saudavel --
        # ou seja, `alta`/painel fechado nunca chegavam a correr.
        floor_mb = (self.engine_min_free_mb if self.batch_kind == "parakeet"
                    else self.min_free_mb)
        if floor_mb > 0:
            free = _free_memory_mb()
            if free is not None and free < floor_mb:
                if respect_memory_floor:
                    self.deferred += 1
                    # RATE-LIMITED, for the reason `on_block`'s `queue_drops` is:
                    # this is evaluated once per 100 ms block, and MEASURED that
                    # way the first version wrote NINETY lines in thirteen seconds
                    # of pressure — a log that grows ~36 000 lines an hour on the
                    # exact path (a hidden panel on a busy box) where nobody is
                    # watching. The COUNTER stays exact; only the prose is thin.
                    if self.deferred <= 3 or self.deferred % 30 == 0:
                        self.log(
                            f"REDUX_BATCH_DEFERRED reason=low-memory free_mb={free} "
                            f"floor_mb={floor_mb} engine={self.batch_kind} "
                            f"held_s={self.pending_seconds()} deferred={self.deferred} "
                            f"— the engine's documented peak is 3.9 GB (ternary) or "
                            f"615 MB (onnx int4) and a failed allocation would lose this "
                            f"pass; the audio stays buffered and the next tick retries")
                    return False
                self.deferred += 1
                self.log(
                    f"REDUX_BATCH_LOW_MEMORY free_mb={free} floor_mb={floor_mb} "
                    f"engine={self.batch_kind} reason={reason} attempting=anyway "
                    f"deferred={self.deferred} — a tail has no next tick, so the attempt "
                    f"is made and this line is the receipt that it was made under pressure")
        held, samples = self.take_pending()
        if samples < int(REDUX_MIN_AUDIO_S * TARGET_SR):
            # Not worth a model load: put it back and wait for more audio. The
            # spool gives it BACK to the front in one piece -- nothing is lost,
            # and nothing is transcribed out of order.
            if self.pending is not None:
                self.pending.requeue(held)
            return False
        return self._start_pass(held, samples, reason)

    def _start_pass(self, held, samples, reason):
        """Arranca UM lote na thread `redux-batch`. Nao bloqueia quem o pede.

        QUEM CORRE E' ESCOLHIDO AQUI, e o log diz qual: `parakeet` (o ONNX int4,
        neste processo, carregado pela propria thread) ou `runner` (o executor
        ternario num processo filho, o contrato `--wav --json` de sempre).
        """
        if not held:
            return False
        self.batches_kicked += 1
        self.batch_seconds += samples / float(TARGET_SR)
        #: O relogio do AUDIO (nao o da parede) onde este lote comeca: e' o que
        #: faz cada linha levar `start`/`end` do audio que cobriu.
        start_s = max(0.0, self._audio_clock_s - samples / float(TARGET_SR))
        if self.batch_kind == "parakeet":
            target = _policy.run_engine_pass
            args = (self, held, samples, reason, start_s)
        else:
            target, args = self._run_runner, (held, samples, reason)
        self._inflight = threading.Thread(
            target=target, args=args, name="redux-batch", daemon=True)
        self._inflight.start()
        self.log(
            f"REDUX_BATCH_KICK reason={reason} engine={self.batch_kind} "
            f"audio_s={round(samples / float(TARGET_SR), 2)} "
            f"kicks={self.batches_kicked} held_in={self._pending_counts().get('blocks_in')} "
            f"pid={os.getpid()}")
        return True

    def _pending_counts(self):
        getter = getattr(self.pending, "counts", None)
        return getter() if callable(getter) else {}

    def _write_wav(self, pcm, path):
        """16 kHz mono PCM16, via `wave` — no dependency and no ffmpeg."""
        import wave

        import numpy as np

        data = np.clip(np.concatenate(pcm) if len(pcm) > 1 else pcm[0], -1.0, 1.0)
        ints = (data * 32767.0).astype("<i2")
        with wave.open(path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(TARGET_SR)
            wav.writeframes(ints.tobytes())

    def _run_runner(self, held, samples, reason):
        """Invoke the batch engine and queue its caption lines. Never raises.

        THE FAILURE THIS CANNOT BE ALLOWED TO HAVE: dying quietly. A batch pass
        that fails and says nothing turns "the light path is working" into a
        claim with no evidence, and the owner's captions simply stop. Every exit
        from this method logs, and a failure leaves a `REDUX_BATCH_FAILED` line
        on stderr and a `redux-batch-error` status on stdout.
        """
        import subprocess
        import tempfile

        wav_path = None
        try:
            if self.wav_dir is None:
                # ONE directory per process, not per batch: a `mkdtemp` per
                # invocation leaks a directory every `batch_interval_s`, and a
                # panel left closed overnight is exactly when that is not
                # noticed. The WAV itself is removed after every run.
                self.wav_dir = tempfile.mkdtemp(prefix="sotto-redux-")
            wav_dir = self.wav_dir
            os.makedirs(wav_dir, exist_ok=True)
            wav_path = os.path.join(
                wav_dir, f"redux-{os.getpid()}-{self.batches_kicked}.wav")
            self._write_wav(held, wav_path)
            cmd = [sys.executable, self.runner, "--wav", wav_path, "--json"]
            # CREATE_NO_WINDOW: the house rule. This worker already runs without
            # a console; a child python.exe would otherwise open a NEW console
            # window on the owner's screen, and the 60 s census names the pid.
            creationflags = 0x08000000 if os.name == "nt" else 0
            t_runner = time.time()
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=self.runner_timeout_s,
                creationflags=creationflags)
            runner_wall = round(time.time() - t_runner, 2)
            lines = 0
            for raw in (proc.stdout or "").splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except ValueError:
                    self.log(f"REDUX_BATCH_MALFORMED line={json.dumps(raw[:160])}")
                    continue
                if not isinstance(payload, dict) or payload.get("type") != "caption":
                    continue
                text = str(payload.get("text") or "").strip()
                if not text:
                    continue
                # ── THE PAYOFF ───────────────────────────────────────────────
                # `producer` is stamped HERE and not taken from the runner's own
                # line unless the runner already said it: the field is what
                # `app/electron/history-source.js:51,61-63` requires, and a batch
                # line that reached the transcript without it would be refused.
                # `final:true` is the worker's OWN route vote — the panel's
                # engine reads it to derive `route='final'`
                # (`caption-formulation.js` `routeFor`).
                self._captions.put({
                    "type": "caption",
                    "text": text,
                    "start": payload.get("start"),
                    "end": payload.get("end"),
                    "final": True,
                    "producer": str(payload.get("producer") or REDUX_PRODUCER),
                    "producerModel": os.path.basename(
                        str(payload.get("model") or self.runner)),
                    "route": "redux-batch",
                })
                lines += 1
            self.segments += 1
            self.segment_lines += lines
            self.log(
                f"REDUX_BATCH_DONE reason={reason} "
                f"audio_s={round(samples / float(TARGET_SR), 2)} lines={lines} "
                f"rc={proc.returncode} segments={self.segments} "
                f"wall_s={runner_wall} timeout_s={self.runner_timeout_s}")
            # A NON-ZERO rc IS A FAILURE, not "the audio had nothing to say", and
            # it is counted and named as one. Two separate things are reported
            # because they are different facts: `REDUX_BATCH_DONE` says the runner
            # RETURNED (with its rc), and `REDUX_BATCH_FAILED` says this run lost a
            # pass. MEASURED reason this is not left to the empty-caption status:
            # the runner's stderr is captured and would otherwise be discarded, so
            # a runner that refuses its input (wrong WAV shape, missing weights, a
            # Python traceback) reported as `lines=0` — indistinguishable from a
            # silence, which is the "green exit code on a broken stage" class this
            # repo has been bitten by. The tail is logged ONLY on failure, so a
            # healthy run stays quiet.
            if proc.returncode != 0:
                tail = " | ".join(
                    (proc.stderr or "").strip().splitlines()[-4:])[:600]
                # NAO SE PERDE AUDIO POR UM rc: com ZERO linhas o lote inteiro
                # volta para o principio do que espera e sera' tentado outra vez
                # (com backoff). Com linhas ja' emitidas nao ha' como saber que
                # amostra cada uma cobriu, por isso nao se re-enfileira nada --
                # duplicar a legenda do dono e' pior do que um rc estranho, e a
                # linha `REDUX_BATCH_FAILED` fica como o recibo disso.
                rest = held if lines == 0 else []
                _policy.park_pass(self, rest, "runner-rc", extra=f"rc={proc.returncode} "
                           f"lines={lines} runner={os.path.basename(self.runner)} "
                           f"tail={json.dumps(tail)}")
            if lines == 0:
                # A silent batch is a FACT the run must state: the panel is
                # hidden, the switch is armed, and the audio produced nothing.
                self._captions.put({
                    "type": "status",
                    "state": "redux-batch-empty",
                    "producer": REDUX_PRODUCER,
                    "audio_s": round(samples / float(TARGET_SR), 2),
                    "detail": (
                        f"the batch engine ran over {round(samples / float(TARGET_SR), 2)}s "
                        f"of accumulated audio and emitted no caption "
                        f"(rc={proc.returncode}); the panel is hidden and this is the "
                        f"only transcriber running"),
                })
        except subprocess.TimeoutExpired:
            _policy.park_pass(self, held, "timeout",
                       extra=f"timeout_s={self.runner_timeout_s} runner={self.runner}")
        except Exception as exc:
            _policy.park_pass(self, held, type(exc).__name__, extra=f"error={exc!r}")
        finally:
            if wav_path:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

    def drain_captions(self):
        """The lines the runner produced, for the ASR thread to emit. Non-blocking."""
        out = []
        while True:
            try:
                out.append(self._captions.get_nowait())
            except queue.Empty:
                return out

    def in_flight(self):
        return self._inflight is not None and self._inflight.is_alive()

    def stop(self):
        """Last call: transcribe the tail, let the engine finish, then report.

        O FIM DO STREAM NAO E' UM SITIO ONDE SE DEITA AUDIO FORA. O que ainda
        espera por um motor e' transcrito AQUI, sincronamente e com o teto de
        `runner_timeout_s`, porque depois deste metodo o processo vai embora e o
        audio que ficou na `PendingAudio` (RAM ou spool) nao tem quem o leia. E'
        a mesma regra do tail do painel: o ultimo minuto do dono conta.
        """
        if not self.enabled:
            return
        if self._inflight is not None:
            self._inflight.join(timeout=max(5.0, self.runner_timeout_s))
        left = self.pending_seconds() if self.pending is not None else 0.0
        if self.armed and not self.in_flight() and left > 0:
            remaining = self.take_pending()
            if remaining[1] >= int(REDUX_MIN_AUDIO_S * TARGET_SR):
                start_s = max(0.0, self._audio_clock_s
                              - remaining[1] / float(TARGET_SR))
                self.log(f"REDUX_SHUTDOWN_TAIL audio_s={round(remaining[1] / float(TARGET_SR), 2)} "
                         f"— o audio que esperava por um motor e' transcrito antes de sair")
                if self.batch_kind == "parakeet":
                    _policy.run_engine_pass(self, remaining[0], remaining[1], "shutdown", start_s)
                else:
                    self._run_runner(remaining[0], remaining[1], "shutdown")
            else:
                if self.pending is not None:
                    self.pending.requeue(remaining[0])
        self._release_engine("stop")
        self.log(
            f"REDUX_SWITCH_STOP armed={str(self.armed).lower()} "
            f"switches={self.switches} segments={self.segments} "
            f"segment_lines={self.segment_lines} kicks={self.batches_kicked} "
            f"batch_seconds={round(self.batch_seconds, 2)} "
            f"failures={self.runner_failures} deferred={self.deferred} "
            f"refusals={self.refusals} left_s={left} "
            f"spooled={self._pending_counts().get('spooled', 0)} "
            f"fallbacks={self.reader.fallbacks}/{self.reader.reads}")
