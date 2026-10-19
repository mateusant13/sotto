#!/usr/bin/env python
"""speaker_sidecar.py -- the WRITER half: capture the call, decide who spoke.

`worker/speaker_bridge.py` reads what this writes. Nothing in the ASR path
imports this, and this never imports the ASR. The two halves are deliberately
separate processes because the diarizer's own cost was measured today
(`_main/_hoje-ctrl.json`): **277 MB RSS, 0,9 s to load, RTF 0,416**. Put it in
the worker and the worker carries a second set of weights on a box whose owner
has already said, verbatim, "PARA DE FAZER MEU PC TRAVAR. AGORA."

THE PART THAT IS EASY TO GET WRONG, and the reason this file exists rather than
a loop in the worker.

Diarization is a BATCH job over a WINDOW, and the batch job's clock does not
start where the app's clock does. A window covering the last 20 seconds returns
segments timed from 0,0 -- but the worker's captions are timed from the moment
the capture started, an hour ago. Stamping a window's segments into the app's
timeline without adding the window's offset does not fail loudly: it attributes
every line to whatever voice happened to speak at that offset in some earlier
minute. The speaker badge would look perfectly plausible and be completely
wrong, which is the worst failure mode a caption can have.

So the offset is not a detail of the writer, it is the writer's job:
`to_absolute()` is the only path from a diarizer result to a payload, and it is
pinned by `_main/speaker-sidecar-oracle.py` with a window that starts 300 s into
a timeline.

ATOMIC BY CONSTRUCTION. The bridge may read this file at any instant, including
while it is being rewritten. The payload is written to a sibling temporary file
and moved into place with `os.replace`, which is atomic on Windows and on
POSIX: a reader sees the whole previous payload or the whole new one, never a
half-written one. The bridge treats a partial read as `None` anyway, because a
future writer might not be this one.

WHAT IS AND IS NOT MEASURED. The decision half -- diarizer output to a speaker
per caption line -- is gated at 70/70 arms and 11/11 mutants against the
vendor's real four-speaker output. The capture half (`WasapiLoopbackTap`) is the
worker's own, already shipping. THE JOIN between them -- a live call, this
sidecar running, the panel naming two or more people -- has NOT been run on this
machine: it needs the model in memory and a real Discord call, and the owner
asked for quiet while he was on one. `--selftest` therefore exercises the
cadence, the buffer, the offset and the atomic write with a FAKE diarizer and no
audio device, so that when a live run is authorised the only unproven step is
the model's own output, which is already measured elsewhere.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir))

DEFAULT_OUT = os.path.join(REPO, "_main", "diar-live.json")
DEFAULT_SEG_MODEL = os.path.join(REPO, "_main", "diar-models",
                                 "sherpa-onnx-pyannote-segmentation-3-0",
                                 "model.onnx")
DEFAULT_EMB_MODEL = os.path.join(REPO, "_main", "diar-models",
                                 "3dspeaker_eres2net_base_16k.onnx")

DEFAULT_RATE = 16000
DEFAULT_WINDOW_S = 20.0
DEFAULT_EVERY_S = 10.0
#: Must be >= the bridge's `DEFAULT_MAX_AGE_S` or the writer's own output would
#: be refused as stale. Kept as a constant here so the coupling is visible.
DEFAULT_MAX_AGE_S = 30.0


class RingBuffer:
    """The last `window_s` seconds of 16 kHz mono float, and nothing older.

    Bounded by construction, because the alternative is a call that eats the
    owner's RAM until it dies -- and the box already runs the ASR model.
    """

    def __init__(self, rate: int = DEFAULT_RATE, window_s: float = DEFAULT_WINDOW_S):
        self.rate = int(rate)
        self.window_s = float(window_s)
        self.capacity = max(1, int(self.rate * self.window_s))
        self._buf = []
        self._n = 0
        #: Absolute time, in the CAPTURE's clock, of the first sample currently
        #: in the buffer. This is the number the offset arithmetic turns on.
        self.start_t = 0.0

    def __len__(self) -> int:
        return self._n

    def push(self, samples, t0_abs: float) -> None:
        """Append float samples whose first one is at absolute time `t0_abs`."""
        block = list(samples)
        if not block:
            return
        if self._n == 0:
            self.start_t = float(t0_abs)
        self._buf.extend(block)
        self._n += len(block)
        while self._n > self.capacity:
            drop = self._n - self.capacity
            del self._buf[:drop]
            self._n -= drop
            self.start_t += drop / float(self.rate)

    def window(self) -> list:
        return list(self._buf)

    def window_duration_s(self) -> float:
        return self._n / float(self.rate)


def to_absolute(payload, window_start_abs: float) -> dict:
    """A diarizer result timed from 0,0 -> a payload on the CAPTURE's clock.

    The whole point of the file. `window_start_abs` is `RingBuffer.start_t` of
    the window that was handed to the model.
    """
    if not isinstance(payload, dict):
        return {}
    out = dict(payload)
    rows = []
    for row in payload.get("segments") or ():
        if not isinstance(row, dict):
            continue
        try:
            start = float(row["start"]) + window_start_abs
            end = float(row["end"]) + window_start_abs
        except (KeyError, TypeError, ValueError):
            continue
        new = dict(row)
        new["start"] = start
        new["end"] = end
        rows.append(new)
    out["segments"] = rows
    out["window_start_abs"] = window_start_abs
    return out


def _replace_with_retry(tmp: str, path: str, attempts: int = 40,
                        delay_s: float = 0.025) -> None:
    """`os.replace`, retried -- because on Windows it legitimately fails.

    MEASURED, not theorised. `_main/speaker-sidecar-oracle.py` publishes in a
    loop while a reader thread holds the file open, and the writer gets
    `PermissionError: [Errno 13]` -- every time. The reason is the Windows
    sharing model: Python opens files through `_wopen`, which grants
    `FILE_SHARE_READ | FILE_SHARE_WRITE` but NOT `FILE_SHARE_DELETE`, and
    `os.replace` needs DELETE access to the target. So on this OS an atomic
    publish is atomic *except* in the exact window where somebody is reading,
    which is precisely when publishing happens.

    This is not a rare race: the bridge reads on every caption. Retrying
    closes it. Losing a publish outright is harmless by design -- the next tick
    is `every_s` away -- but silently never publishing again is not, which is
    why the retry exists rather than a bare `except`.

    **THE BUDGET WAS TOO SMALL, AND THE ORACLE CAUGHT IT.** MEASURED
    2026-10-18: with `attempts=8, delay_s=0.02` (160 ms) the arm "the writer lost
    zero publishes on Windows" printed **`lost=1 of 150`** -- a real RED. The two
    runs immediately after printed `lost=0 of 150`. A gate that is green most of
    the time is a gate that cannot be trusted on the day it matters, and the fix
    is not to re-run until it is green.

    8 x 20 ms is ~160 ms; a reader on this box occasionally holds the file
    longer than that. 40 x 25 ms is ~1,0 s, which is a stall in the publish call
    and NOT in transcription: it happens on the sidecar's tick thread, the tick
    period is `every_s` (10 s by default), and the alternative is publishing
    nothing at all. One second once in a while is the cheaper of the two.
    """
    last = None
    for attempt in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(delay_s)
    raise last


def write_payload_atomic(path: str, payload) -> bool:
    """Move a complete payload into place. A reader never sees half of one."""
    try:
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".diar-", suffix=".tmp",
                                   dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            _replace_with_retry(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except (OSError, TypeError, ValueError):
        return False


def _merged_intervals(spans):
    out = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def _intersect_duration(a, b):
    """Seconds where both lists of spans are speaking at once."""
    ma = _merged_intervals(a)
    mb = _merged_intervals(b)
    total = 0.0
    i = j = 0
    while i < len(ma) and j < len(mb):
        lo = max(ma[i][0], mb[j][0])
        hi = min(ma[i][1], mb[j][1])
        if hi > lo:
            total += hi - lo
        if ma[i][1] < mb[j][1]:
            i += 1
        else:
            j += 1
    return total


class StableSpeakerSlots:
    """Map each window's LOCAL diarizer labels onto GLOBAL, stable ids.

    THE DEFECT THIS EXISTS TO FIX, MEASURED on the owner's own Discord call with
    the real model (20 s windows, 10 s step, `_main/_call-diar-cmap.py`):

        par 1->2    etiqueta CRUA  25,0 %   (cMAP, alinhado,  75,0 %)
        par 15->16  etiqueta CRUA   0,0 %   (cMAP 100,0 %, mapa {0:1, 1:0})

    A complete swap. The diarizer renumbers the same person from one window to
    the next, and `tick` was publishing that raw number straight into the
    payload. `source` is the panel's row key (`panel.js:386` `rowIdentity`), so
    publishing it raw means ONE person's captions hop between two rows every ten
    seconds -- which is the exact failure the whole per-voice `source` exists to
    prevent.

    **Pinning `num_speakers` does NOT fix it.** Measured: raw-label agreement was
    **68,4 %** with `num_clusters=2`, worse than the **70,2 %** of auto mode. The
    count was never the problem; the NUMBERING was.

    WHY `cmap` NEVER CAUGHT IT: `cmap` aligns the two label sets before scoring,
    because labels are arbitrary and an unaligned score would read "the number
    changed" as "the person changed". That alignment is exactly what hides this.
    The metric was blind to it BY CONSTRUCTION, which is the sharpest form of the
    rule this repo keeps re-learning: a guard that the design makes equivalent
    cannot be caught by a measurement built on that same design.

    The fix is a matching layer, not a parameter: each window's local label is
    matched to the global slot that shares the most speaking TIME with it, and
    the history is kept for `horizon_s` so a speaker who pauses comes back to the
    slot they left rather than a new one.
    """

    def __init__(self, horizon_s: float = 60.0):
        self.horizon_s = horizon_s
        self.spans = {}              # slot_id -> [(start, end), ...] absolute
        self.next_id = 1             # 1-based: the bridge prints `speaker-<n>`
        self.seen = 0

    def remap(self, segments, now: float):
        """`segments` in ABSOLUTE time -> the same list with global ids.

        Returns `(segments, mapping, created)` so a caller -- and the oracle --
        can see which local label became which slot, and which slots are new.
        """
        by_local = {}
        for s in segments or ():
            by_local.setdefault(int(s["speaker"]), []).append(
                (float(s["start"]), float(s["end"])))

        # RETIRE BEFORE MATCHING, not after. MEASURED: the first version pruned
        # afterwards, which meant a slot that had been silent for longer than
        # `horizon_s` could still win the match -- the horizon was then not a
        # bound on anything, it only decided what survived to the NEXT window.
        # Pruning first makes the promise true: a slot that has not spoken
        # within `horizon_s` does not exist, and slots cannot creep upward over
        # a call lasting hours.
        cutoff = now - self.horizon_s
        for slot in list(self.spans):
            keep = [(s, e) for s, e in self.spans[slot] if e >= cutoff]
            if keep:
                self.spans[slot] = keep
            else:
                del self.spans[slot]

        pairs = []
        for loc, spans in by_local.items():
            for slot, hist in self.spans.items():
                pairs.append((_intersect_duration(spans, hist), loc, slot))
        # A TOTAL order, so the result never depends on dict iteration. The
        # non-determinism-by-iteration bug in `speaker_id.py` is not repeated
        # here by accident: ties are broken by (local, slot), both integers.
        pairs.sort(key=lambda t: (-t[0], t[1], t[2]))
        mapping = {}
        used_loc = set()
        used_slot = set()
        for score, loc, slot in pairs:
            if score <= 0.0 or loc in used_loc or slot in used_slot:
                continue
            mapping[loc] = slot
            used_loc.add(loc)
            used_slot.add(slot)
        created = []
        for loc in sorted(by_local):
            if loc not in mapping:
                mapping[loc] = self.next_id
                self.next_id += 1
                created.append(mapping[loc])

        for loc, slot in sorted(mapping.items()):
            self.spans.setdefault(slot, []).extend(by_local[loc])

        self.seen += 1
        out = []
        for s in segments or ():
            d = dict(s)
            d["local_speaker"] = int(s["speaker"])
            d["speaker"] = mapping[int(s["speaker"])]
            out.append(d)
        return out, mapping, created


SAFE_WINDOW_S = 10.0

#: ABAIXO DESTA DENSIDADE DE FALA, A JANELA NAO TEM IDENTIDADE PARA ATRIBUIR.
#:
#: MEDIDO nas duas gravacoes reais da call do dono (`_main/_speech-seconds-
#: probe.py`, `_main/_energy-gate-probe.py`), janela de 10 s:
#:
#:                    gravacao DENSA      gravacao ESPARSA
#:     fala (modelo)     5,1 a 9,8 s         0,3 a 3,2 s     <- da 2 slots vs 12
#:     fala (envolvente) 3,3 a 7,9 s         0,0 a 2,3 s     <- SEPARADO
#:
#: A gravacao esparsa e' 89 % de silencio: 21,2 s de fala em 180 s, com segmentos
#: de mediana 1,52 s. Nela a cadeia de produto cria um slot NOVO por janela -- o
#: painel faria 12 pontos coloridos para 2 pessoas.
#:
#: POR QUE A SOBREPOSICAO NAO RESOLVE ISTO, que era a minha hipotese inicial e
#: esta refutado: mais sobreposicao deu MAIS fragmentos, nao menos (10/5 -> 22
#: slots, 10/3 -> 33, 10/2 -> 49). `StableSpeakerSlots` casa por tempo falado
#: PARTILHADO; com 89 % de silencio, 10 s de sobreposicao entre duas janelas nao
#: contem fala, e nao ha o que casar. Nao e' que o casamento esteja partido -- e'
#: que lhe falta materia.
#:
#: E AS DUAS ALAVANCAS "OBVIAS" NAO SERVEM, ambas medidas
#: (`_main/_fragment-levers.py`):
#:     `--num-speakers 2`   12 slots -> 12 slots, e 3,7x mais lento. Nao faz nada,
#:                         porque a fragmentacao esta ao nivel do segmento.
#:     `--min-on 2,0 s`     12 -> 4 slots, MAS deita fora 58 % da fala
#:                         (21,1 s -> 8,9 s). Nao e' um curativo, e' apagar.
#:
#: A PORTA E' DE ENERGIA, NAO DE MODELO, por duas razoes: nao custa RAM nenhuma
#: (e' o que torna a porta utilizavel na Fase A), e e' INDEPENDENTE -- o RMS do
#: audio nao sabe nada sobre vozes, ao passo que usar a classe 0 do proprio modelo
#: de segmentacao seria vigiar o modelo com ele proprio.
#:
#: O LIMIAR E' RELATIVO AO PICO DA JANELA, nunca absoluto: as duas gravacoes
#: medem -18,5 dBFS e -32,5 dBFS, 14 dB de diferenca. Um limiar em dBFS mediria
#: o ganho, nao o audio, e dari um limiar limpo que nao existe.
#:
#: A doutrina e' a do resto do projecto: **legenda sem voz melhor que legenda
#: com a voz errada**. Uma janela sem fala para casar nao recebe voz inventada --
#: recebe `segments: []`, que e' o que o painel ja sabe ler como "sem vozes".
MIN_SPEECH_FRACTION = 0.30
SPEECH_ENV_THR = 0.10             # fracao do pico da janela


def speech_fraction(samples, thr: float = SPEECH_ENV_THR) -> float:
    """Que fracao da janela parece fala, por envolvente de energia.

    Zero modelos, zero dependencias, e independente de tudo o que o pipeline
    faz a seguir. Uma janela de silencio digital devolve 0,0 -- o `peak <= 0`
    trata o log de zero, que daria -240 dBFS e uma fracao sem sentido.
    """
    import numpy as np                                             # noqa: PLC0415
    x = np.asarray(samples, dtype=np.float32)
    if x.size < 2:
        return 0.0
    hop = max(1, int(0.020 * DEFAULT_RATE))
    win = max(1, int(0.040 * DEFAULT_RATE))
    n = max(0, (x.size - win) // hop + 1)
    if n == 0:
        return 0.0
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    rms = np.sqrt((x[idx] ** 2).mean(axis=1))
    peak = float(rms.max()) if rms.size else 0.0
    if peak <= 0.0:
        return 0.0
    return float((rms >= peak * thr).sum()) / float(n)

def tick(buffer: RingBuffer, diarize, out_path: str, threshold: float = 0.9,
         num_speakers: int = -1, min_audio_s: float = 1.0,
         slots: "StableSpeakerSlots" = None,
         min_speech_fraction: float = MIN_SPEECH_FRACTION) -> dict:
    """One cadence step: diarize what is buffered, publish it, say what happened.

    `min_audio_s` is the floor on how much audio the window must actually hold.
    MEASURED, not theorised: the first version ticked immediately on start-up,
    found an empty buffer, and -- in a six-second run with a ten-second period
    -- that wasted tick was the ONLY tick, so nothing was ever published. A
    diarizer handed a tenth of a second of audio is also being asked a question
    nobody asked it; publishing the answer would be worse than publishing
    nothing.

    Returns a small dict instead of raising: a sidecar that dies takes the
    attribution with it, and the owner would rather have captions with no names
    than a worker that stopped transcribing.
    """
    samples = buffer.window()
    if not samples:
        return {"state": "empty", "n_segments": 0}
    have_s = len(samples) / float(buffer.rate)
    if have_s < min_audio_s:
        return {"state": "too-short", "n_segments": 0,
                "have_s": round(have_s, 3), "want_s": min_audio_s}
    window_start = buffer.start_t
    try:
        raw = diarize(samples, threshold=threshold, num_speakers=num_speakers)
    except Exception as exc:                                    # noqa: BLE001
        return {"state": "error", "error": type(exc).__name__,
                "n_segments": 0, "window_start_abs": window_start}

    payload = to_absolute(raw, window_start)
    payload.setdefault("written_at", time.time())

    # ---- A PORTA DE DENSIDADE ------------------------------------------------
    # Publicar `segments: []` quando a janela nao tem fala para merecer
    # identidade. E' deliberado: publicar nada deixaria no painel a atribuicao
    # ANTIGA, que e' pior do que nao ter. Uma lista vazia e' o que
    # `speaker_bridge.voices()` ja le como "sem vozes", e o painel ja sabe
    # mostrar isso sem texto novo.
    #
    # Quando se chegou aqui: `call180.wav`, 180 s reais da call do dono, 89 % de
    # silencio. A cadeia criava 12 slots para 2 pessoas, e o painel faria 12
    # pontos coloridos. Medir a porta: `_main/_energy-gate-probe.py`.
    frac = speech_fraction(samples)
    payload["speech_fraction"] = round(frac, 4)
    if min_speech_fraction > 0.0 and frac < min_speech_fraction:
        payload["segments"] = []
        payload["n_segments"] = 0
        payload["attribution"] = "declined"
        payload["min_speech_fraction"] = min_speech_fraction
        ok = write_payload_atomic(out_path, payload)
        return {"state": "written" if ok else "write-failed",
                "n_segments": 0, "declined": True,
                "speech_fraction": round(frac, 4),
                "window_start_abs": window_start,
                "window_s": len(samples) / float(buffer.rate)}

    if slots is not None:
        # THE HORIZON RUNS ON THE CAPTURE'S CLOCK, NOT THE WALL CLOCK.
        # MEASURED: `_main/_sidecar-replay-real.py` replayed 60 s of the owner's
        # real call through the REAL tick and came back with **8 global slots for
        # 2 people** -- a brand new slot every window. The cause was this line
        # passing `written_at`, which is `time.time()`, as the horizon's `now`.
        # The segments carry ABSOLUTE CAPTURE time, not wall time. Whenever the
        # two clocks disagree by more than `horizon_s` -- which they do the
        # moment the audio is anything other than live -- every slot is older
        # than the cutoff, is pruned BEFORE matching, and nothing can ever match
        # a previous window. The feature silently degrades to "new person every
        # 10 s", which is worse than having no voices at all.
        # The window's own END, in the capture's clock, is the only `now` that
        # means the same thing as the spans it is compared against.
        window_end = window_start + len(samples) / float(buffer.rate)
        payload["segments"], mapping, created = slots.remap(
            payload.get("segments") or [], now=window_end)
        payload["speaker_slots"] = {str(k): v for k, v in sorted(mapping.items())}
        if created:
            payload["speaker_slots_created"] = sorted(created)
    payload["window_s"] = len(samples) / float(buffer.rate)
    payload["n_segments"] = len(payload.get("segments") or ())
    ok = write_payload_atomic(out_path, payload)
    return {"state": "written" if ok else "write-failed",
            "n_segments": payload["n_segments"],
            "window_start_abs": window_start,
            "window_s": payload["window_s"]}


class FakeDiarizer:
    """A diarizer with no model, for `--selftest`.

    It says "speaker A holds 1,0-3,0 s of whatever window it is given", which is
    enough to prove the CADENCE, the BUFFER and above all the OFFSET -- and it
    costs nothing, which is the point.
    """

    def __init__(self, segments=None):
        self.segments = segments or [
            {"start": 1.0, "end": 3.0, "speaker": 0},
            {"start": 4.0, "end": 6.5, "speaker": 1},
        ]
        self.calls = 0

    def __call__(self, samples, threshold=0.9, num_speakers=-1):
        self.calls += 1
        return {"segments": [dict(s) for s in self.segments],
                "threshold": threshold, "fake": True}


# --------------------------------------------------------------------------
# Live mode. Imported lazily so `--selftest` never touches sherpa-onnx.
# --------------------------------------------------------------------------

def _load_sherpa_diarizer(seg_model: str, emb_model: str, threads: int = 2,
                          provider: str = "cpu", num_clusters: int = -1,
                          threshold: float = 0.9, min_on: float = 0.3,
                          min_off: float = 0.5):
    """Build the SDK's diarizer from NESTED configs.

    MEASURED, the hard way: the first version passed model paths straight to
    `OfflineSpeakerDiarizationConfig` and the first live run died with
    `TypeError: incompatible constructor arguments`, which lists the real
    signature:

        OfflineSpeakerDiarizationConfig(
            segmentation: OfflineSpeakerSegmentationModelConfig,
            embedding:    SpeakerEmbeddingExtractorConfig,
            clustering:   FastClusteringConfig,
            min_duration_on: float, min_duration_off: float)

    The shape below is copied from `_main/_diar-run.py:64-86`, the instrument
    that measured **DER 0,03 %** on the vendor's own ground truth today. Two
    details there are not decoration and are kept: the pyannote sub-config is
    built inside a `try` because sherpa-onnx 1.13.4's pybind signature is
    `(model: str)` only -- `window_shift_ratio` arrived on master after this
    release -- and the threshold belongs to the CLUSTERING, not to the process
    call, which is why `--threshold` is wired here and not at `process()` time.
    """
    import sherpa_onnx                                             # noqa: PLC0415

    pyannote_fn = sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig
    try:
        pyannote_cfg = pyannote_fn(model=seg_model)
    except TypeError:
        pyannote_cfg = pyannote_fn(model=seg_model)

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=pyannote_cfg, num_threads=threads, provider=provider),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=emb_model, num_threads=threads, provider=provider),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=num_clusters, threshold=threshold),
        min_duration_on=min_on,
        min_duration_off=min_off,
    )
    if not config.validate():
        raise SystemExit("sidecar: diarizer config did not validate: %s"
                         % (seg_model,))
    return sherpa_onnx.OfflineSpeakerDiarization(config)


# ---------------------------------------------------------------------------
# FASE A -- "HÁ DUAS VOZES AO MESMO TEMPO?" sem pagar pela identidade.
# ---------------------------------------------------------------------------
#
# O QUE ISTO E'
# --------------
# A separacao de vozes completa custa 135-207 MB e 0,18-0,89 de tempo real, e o
# que sustenta a identidade entre janelas e' a SOBREPOSICAO -- cada janela e'
# diarizada duas vezes. O dono pediu (2026-10-18) para separar as vozes DEPOIS,
# quando for seguro, mas manter a DETECCAO de multiplas vozes a correr, porque sem
# ela nao se sabe o que vale a pena reprocessar.
#
# A deteccao e' uma propriedade do modelo de SEGMENTACAO sozinho (5,7 MB): nao
# precisa do modelo de embeddings (37,8 MB), nem de clustering, nem de identidade
# entre janelas -- logo nao precisa da sobreposicao, que e' o que custa.
#
# MEDIDO, mesma maquina, mesma corrida (`_main/multivoice-oracle.py`, 13/13):
#     RTF 0,0097 contra 0,503 da pipeline completa -> 52x mais barato
#     F1 0,932 na sobreposicao a 100 % (P 1,000 / R 0,872)
#     a MESMA voz em duas camadas dispara 0,00 s -> mede pessoas, nao volume
#     RSS em regime 90,3 MB contra 135,4 MB
#
# O INPUT E' A ONDA CRUA
# ----------------------
# `model.onnx` declara `x: [N, 1, T]` com T em AMOSTRAS. O filterbank e' a
# primeira camada do proprio modelo (SincNet): InstanceNorm -> Conv sinc de
# [80, 1, 251] com stride 10 -> Abs -> MaxPool x3. Nao ha fbank para calcular em
# Python, e portanto nao ha um fbank meu que possa divergir em silencio do do
# sherpa. Instrumento: `I:\\cc-tmp\\trace-x.py`.
#
# AS 7 CLASSES PODERSET: 1 + 3 + 3
# ---------------------------------
#     0        ninguem
#     1 2 3    UMA voz, em tres slots
#     4 5 6    DUAS vozes simultaneas, em tres combinacoes de slots
#
# DEDUZIDO de distribuicoes medidas, nao assumido. A leitura decisiva e' o clip de
# QUATRO vozes (`_main/diar-models/0-four-speakers-zh.wav`): 56,9 s, 16,5 s de
# fala, e ZERO frames de 4/5/6 -- porque nao ha sobreposicao. Se 4/5/6 fossem
# "muita gente a falar", teriam disparado la. E num braco de 100 % de
# sobreposicao construido, disparou a classe 4 e nao a 6: testar so a 6 daria
# F1 0,000 e um "detector" que nunca dispara.
#
# 1 FRAME = 270 AMOSTRAS = 16,875 ms
# ----------------------------------
# stride 10 do sinc conv x 3^3. Derivacao arquitectural, verificada contra 7
# comprimentos medidos; transcrever a expressao `floor` do grafo em Python erra
# +-1 frame por arredondamento e da um "DIVERGE" que nao e' divergencia.

MULTI_CLASSES = (4, 5, 6)
FRAME_SAMPLES = 270
FRAME_S = FRAME_SAMPLES / float(DEFAULT_RATE)
DEFAULT_WATCH_HOLD = 3          # frames; 3 = 50,6 ms
DEFAULT_WATCH_OUT = os.path.join(REPO, "_main", "diar-watch.json")

#: ONDE O AUDIO ASSINALADO SOBREVIVE. Vazio = nao guardar nada.
#:
#: MEDIDO, e este e' o furo do desenho em duas fases (`_main/_phase-a-
#: retention-probe.py`): o `RingBuffer` e' em memoria e desliza. Depois de 30 s
#: empurrados num buffer de 10 s, sobram 10 s e os primeiros 20 s foram
#: libertados. A janela do meio (10 s a 20 s) e' libertada **10 s** depois de ter
#: sido vista. A DETECCAO sobrevive -- o payload leva tempos absolutos -- mas o
#: AUDIO nao. E' por isso que "processar depois" nao e' lento: e' IMPOSSIVEL.
#:
#: Por isso, quando a Fase A assinala, o audio assinalado e' escrito aqui.
DEFAULT_WATCH_SAVE = ""          # desligado por omissao: escrever audio do dono
                                 # num disco sem ele pedir isso nao se decide aqui
DEFAULT_WATCH_PAD_S = 2.0        # contexto de cada lado; o diarizador precisa
                                 # de alguns segundos em volta para estabilizar
DEFAULT_WATCH_SAVE_MAX_MB = 256  # FIFO: o mais antigo sai primeiro

#: A JANELA ACIMA DA QUAL A SEPARACAO DE VOZES FICA MAIS CARA DO QUE TEMPO REAL.
#:
#: MEDIDO, e nao teorizado (`_main/_phase-b-cliff-probe.py`, mesmo processo,
#: mesmo audio, 2 nucleos):
#:
#:     janela | so segmentacao (Fase A) | pipeline completa (Fase B)
#:        4 s  |     RTF 0,0256         |  RTF 0,1007
#:        8 s  |     RTF 0,0176         |  RTF 0,0265
#:       10 s  |     RTF 0,0147         |  RTF 0,0423
#:       11 s  |     RTF 0,0212         |  RTF 0,6683   <- o degrau
#:       14 s  |     RTF 0,0150         |  RTF 1,6930   <- pior que tempo real
#:       20 s  |     RTF 0,0154         |  RTF 1,5196
#:
#: A SEGMENTACAO NAO TEM DEGRAU -- e' plana em todo o intervalo. O degrau e' da
#: metade de embeddings + clustering, e e' um degrau a serio: entre 10 s e 11 s a
#: pipeline completa multiplica por 16, e a partir dai fica ACIMA de 1, ou seja,
#: mais lenta do que o audio que esta a tratar.
#:
#: POR QUE ISTO IMPORTA PARA O DONO: `--window-s` e' um flag que qualquer um mexe,
#: e a janela de omissao sao 10 s -- do lado bom por UM segundo. Subir a janela
#: para "dar mais contexto", que e' o movimento natural, poe o diarizador a
#: correr mais devagar do que o tempo real durante a call inteira. E' a forma
#: mais provavel de "pesado para o utilizador" -- e nao se resolve com mais
#: nucleos, resolve-se nao pasando do ponto.

def _load_powerset(seg_model: str, threads: int = 2):
    """So o modelo de segmentacao. Sem sherpa, sem embeddings, sem clustering.

    A importacao e' preguicosa de proposito: `--selftest` nunca deve tocar em
    onnxruntime, e `--watch-only` nunca deve tocar em sherpa-onnx.
    """
    import onnxruntime                                             # noqa: PLC0415
    opts = onnxruntime.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = max(1, int(threads))
    return onnxruntime.InferenceSession(seg_model, opts)


def powerset_windows(sess, samples):
    """A onda CRUA -> a classe powerset que ganha em cada frame."""
    import numpy as np                                             # noqa: PLC0415
    x = np.ascontiguousarray(np.asarray(samples, dtype=np.float32))
    out = sess.run(None, {"x": x[None, None, :]})[0]
    return out[0].argmax(axis=1)


def multivoice_spans(win, hold_frames: int = DEFAULT_WATCH_HOLD):
    """Frames winners -> [(frame_inicial, frame_final_exclusivo)] de >=2 vozes.

    `hold_frames` existe porque o modelo emite ruido isolado: no clip de QUATRO
    vozes as classes 1 e 6 ficaram em 2 frames (33,8 ms) cada, e uma janela
    desse tamanho nao quer dizer nada. Tudo abaixo do limiar e' descartado.
    """
    import numpy as np                                             # noqa: PLC0415
    hit = np.isin(win, MULTI_CLASSES)
    spans = []
    n = len(hit)
    i = 0
    while i < n:
        if not hit[i]:
            i += 1
            continue
        j = i
        while j < n and hit[j]:
            j += 1
        if (j - i) >= hold_frames:
            spans.append((i, j))
        i = j
    return spans


def resume_evicted_total(out_path: str) -> int:
    """O acumulado de audio perdido, lido do payload JA EXISTENTE.

    PORQUE ISTO EXISTE, E NAO E' UM DETALHE
    =======================================
    O sidecar reinicia SOZINHO durante uma call -- o watcher reinicia-o. Um total
    que so vive em memoria do processo e' esquecido a cada reinicio, e o que
    acontece a seguir e' o pior dos dois: a Fase B, corrida depois da call, le o
    payload, ve `clips_evicted_total: 0` e diz ao dono que o directorio esta
    completo, sobre audio que JA FOI PERDIDO.

    O payload e' reescrito a cada janela, mas SOBREVIVE ao processo. Por isso e'
    ele que guarda a verdade, e nao o RAM.

    NUNCA LEVANTA: um payload ausente, a meio de uma escrita ou corrompido e' uma
    condicao normal numa maquina com outro processo a escrever. Devolve 0. Um
    ficheiro a meio nao pode parar a deteccao de duas vozes.
    """
    try:
        with open(out_path, "r", encoding="utf-8") as fh:
            prev = json.load(fh)
        return int(prev.get("clips_evicted_total") or 0)
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


def save_multivoice_clips(samples, window_start, spans, out_dir, rate,
                          pad_s: float = DEFAULT_WATCH_PAD_S,
                          max_mb: float = DEFAULT_WATCH_SAVE_MAX_MB) -> tuple:
    """Escreve um WAV por span de duas vozes.

    Devolve `(**clips_que_sobreviveram, clips_que_foram_apagados**)`.

    A segunda lista **nao existia** e e' o defeito que este retorno corrige.
    `_evict_oldest` ja devolvia o numero de ficheiros removidos, e esta funcao
    DEITAVA-O FORA. O efeito medido: numa call longa o bastante para encher a
    fila, o audio assinalado do dono desaparecia sem uma linha no log, sem um
    campo no payload e sem nada. Pior: a eviccao corre DEPOIS da escrita, na
    mesma chamada, e com uma tampa apertada o clip acabado de escrever era o
    primeiro a sair -- o estado dizia `n_clips=2` com **zero** clips no disco.

    Um numero que se le como caminho quando nao e' caminho e' pior do que nao
    imprimir. Por isso o que volta e' o que FICOU, e o que se PERDEU, e o
    `watch_tick` publica os dois.

    SO O QUE FOI ASSINALADO. Um troco de 2-4 s ocupa ~100 KB contra os 320 KB da
    janela inteira, e aponta directamente para o momento que interessou --
    guardar a janela toda seria guardar 80 % de audio em que havia uma pessoa
    so, e nao e' esse o objectivo.

    `pad_s` de contexto de cada lado porque um diarizador precisa de uns segundos
    em volta para assentar; sem eles, um clip de 2 s e' um problema sem
    resposta, nao uma resposta curta.

    NUNCA LEVANTA. Um disco cheio, um caminho sem permissao ou um WAV truncado
    sao condicoes normais numa maquina com outras coisas a escrever; cada uma
    devolve listas vazias e a fala continua a ser publicada. Um portao que
    morre por causa do disco e' um portao que deixa de proteger.
    """
    import wave as _wave                                          # noqa: PLC0415
    if not spans or not out_dir:
        return [], []
    written = []
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError:
        return [], []
    pad = int(round(max(0.0, float(pad_s)) * rate))
    n = len(samples)
    for a, b in spans:
        lo = max(0, a * FRAME_SAMPLES - pad)
        hi = min(n, b * FRAME_SAMPLES + pad)
        if hi - lo < rate // 2:              # meio segundo: abaixo disto nao ha clip
            continue
        chunk = samples[lo:hi]
        # O nome carrega o instante ABSOLUTO do inicio do troco. Ordenar por
        # nome e' ordena-lo por tempo, sem ler um indice.
        stamp = int(round((window_start + lo / float(rate)) * 1000.0))
        final = os.path.join(out_dir, "mv-%d.wav" % stamp)
        tmp = final + ".part"
        try:
            with _wave.open(tmp, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(int(rate))
                pcm = bytearray(len(chunk) * 2)
                for i, v in enumerate(chunk):
                    v = float(v)
                    iv = 32767 if v > 1.0 else (-32768 if v < -1.0 else int(v * 32767.0))
                    pcm[i * 2] = iv & 0xFF
                    pcm[i * 2 + 1] = (iv >> 8) & 0xFF
                w.writeframes(bytes(pcm))
            # NUNCA um WAV meio escrito com o nome final: quem o abrir tem de
            # poder confiar no que leu.
            os.replace(tmp, final)
            written.append(final)
        except (OSError, ValueError, EOFError):
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            continue
    evicted = _evict_oldest(out_dir, max_mb)
    # O que a fila levou pode ter incluido um clip desta MESMA chamada: a
    # eviccao corre depois da escrita. Contar esse como guardado era a segunda
    # metade do defeito, e e' o que dava `n_clips=1` com nada no disco.
    lost = set(os.path.basename(p) for p in evicted)
    surviving = [p for p in written if os.path.basename(p) not in lost]
    return surviving, evicted


def _evict_oldest(out_dir: str, max_mb: float) -> list:
    """Mantem o directorio abaixo de `max_mb`, o mais antigo a sair primeiro.

    Devolve os NOMES do que removeu, na ordem em que removeu. Antes devolvia
    um inteiro que o unico chamador deitava fora -- o numero de audio do dono
    que deixou de existir e' exactamente o que nao pode ser irrecuperavel.

    FIFO por nome, e nao por mtime: o nome ja e' o instante, e um `mtime` muda
    quando se copia um ficheiro, o que baralharia a ordem numa pasta que o dono
    ande a arrumar.
    """
    try:
        entries = sorted(f for f in os.listdir(out_dir)
                         if f.startswith("mv-") and f.endswith(".wav"))
    except OSError:
        return []
    limit = max(0.0, float(max_mb)) * 1048576.0
    total = 0
    sizes = {}
    for name in entries:
        try:
            sizes[name] = os.path.getsize(os.path.join(out_dir, name))
            total += sizes[name]
        except OSError:
            sizes[name] = 0
    removed = []
    for name in entries:
        if total <= limit:
            break
        try:
            os.remove(os.path.join(out_dir, name))
            total -= sizes[name]
            removed.append(name)
        except OSError:
            pass
    return removed


def watch_tick(buffer: RingBuffer, sess, out_path: str,
               hold_frames: int = DEFAULT_WATCH_HOLD,
               min_audio_s: float = 1.0,
               save_dir: str = "",
               pad_s: float = DEFAULT_WATCH_PAD_S,
               max_mb: float = DEFAULT_WATCH_SAVE_MAX_MB,
               evicted_before: int = 0) -> dict:
    """Um passo da Fase A: responder SO "havia duas vozes?", e publicar isso.

    Deliberadamente NAO escreve `segments`. `speaker_bridge.payload_if_fresh`
    exige `segments` para devolver alguma coisa e devolve `None` sem essa chave
    -- ou seja, um payload de watch nao pode ser confundido com o de fala, e o
    painel continua a ver "sem vozes" em vez de uma lista vazia que ele trataria
    como a verdade. O portao `_main/speaker-watch-oracle.py` verifica esta
    propriedade em vez de a deixar como comentario.
    """
    samples = buffer.window()
    if not samples:
        return {"state": "empty", "n_spans": 0}
    have_s = len(samples) / float(buffer.rate)
    if have_s < min_audio_s:
        return {"state": "too-short", "n_spans": 0,
                "have_s": round(have_s, 3), "want_s": min_audio_s}
    window_start = buffer.start_t
    try:
        win = powerset_windows(sess, samples)
        spans = multivoice_spans(win, hold_frames)
    except Exception as exc:                                       # noqa: BLE001
        return {"state": "error", "error": type(exc).__name__,
                "n_spans": 0, "window_start_abs": window_start}

    out_spans = []
    for a, b in spans:
        out_spans.append({
            "start": round(window_start + a * FRAME_S, 3),
            "end": round(window_start + b * FRAME_S, 3),
            "frames": b - a,
            "s": round((b - a) * FRAME_S, 3),
        })
    # O audio que a deteccao assinalou, guardado ANTES de a janela deslizar.
    # E' o que torna 'processar depois' possivel em vez de aspiracional.
    #
    # ANTES de publicar o payload, e nao depois: a fila pode ter apagado um
    # clip desta MESMA janela, e o payload tem de poder dizer isso. Um payload
    # que diz "assinalei 2 vozes" sem dizer que o audio ja nao esta la e' um
    # payload que promete uma coisa que nao pode cumprir.
    clips = []
    evicted = []
    if save_dir:
        clips, evicted = save_multivoice_clips(samples, window_start, spans,
                                               save_dir, buffer.rate, pad_s,
                                               max_mb)
    payload = {
        "state": "watch",
        "written_at": time.time(),
        "window_start_abs": window_start,
        "window_s": have_s,
        "frame_s": FRAME_S,
        "classes": list(MULTI_CLASSES),
        "hold_frames": hold_frames,
        "n_frames": len(win),
        "multivoice": out_spans,
        "n_spans": len(out_spans),
        "multivoice_s": round(sum(s["s"] for s in out_spans), 3),
        # O QUE FICOU e O QUE SE PERDEU.
        #
        # `clips_evicted` e' **desta janela**. MEDIDO: em quatro janelas seguidas
        # que perderam 1, 1 e 1 clip, o payload final dizia `clips_evicted: 1` --
        # o numero lia-se como "perdidos ate agora" e era "perdidos agora". E o
        # payload e' reescrito a cada tick, portanto o historico da perda vivia
        # so no log, num ficheiro que ninguem pode ler para depois juntar ao
        # resultado da separacao.
        #
        # `clips_evicted_total` fecha isso: e' o acumulado que o sidecar carrega
        # entre janelas (`evicted_before`). Sem ele, quem corre a Fase B nao tem
        # como saber que o directorio esta incompleto.
        "clips_saved": len(clips),
        "clips_evicted": len(evicted),
        "clips_evicted_total": int(evicted_before or 0) + len(evicted),
    }
    ok = write_payload_atomic(out_path, payload)
    return {"state": "written" if ok else "write-failed",
            "n_spans": len(out_spans),
            "multivoice_s": payload["multivoice_s"],
            "n_clips": len(clips),
            "n_clips_evicted": len(evicted),
            "n_clips_evicted_total": int(evicted_before or 0) + len(evicted),
            "clips_evicted_names": list(evicted[-3:]),
            "window_start_abs": window_start,
            "window_s": have_s}


def to_mono16k(block, src_rate: int, target: int = DEFAULT_RATE):
    """Whatever WASAPI hands over -> 16 kHz mono float32, which is what the
    diarizer wants.

    MEASURED, because the guess was wrong first: this function's first draft
    assumed the endpoint's own mix format arrived as a single interleaved
    vector, and the first real capture handed it a 2-D array. Both shapes occur
    depending on the endpoint's `channel_mask`, so both are handled, and the
    reduction is written so neither can silently produce half the samples.

    The resample is the worker's own `resample_to_16k` (`sotto_worker.py:1278`)
    -- block averaging for an exact integer ratio, `np.interp` otherwise --
    reproduced here rather than imported, because importing it would drag in
    the whole 358 KB worker and the ASR stack behind it. 48 000 -> 16 000 is
    the common case on this box and takes the exact-ratio path.
    """
    import numpy as np                                             # noqa: PLC0415
    x = np.asarray(block, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=0) if x.shape[0] <= x.shape[1] else x.mean(axis=1)
    x = np.ascontiguousarray(x, dtype=np.float32)
    src_rate = int(src_rate or target)
    if src_rate == int(target):
        return x
    if len(x) < 2:
        return np.zeros(0, dtype=np.float32)
    if src_rate > target and src_rate % target == 0:
        k = src_rate // target
        usable = (len(x) // k) * k
        return x[:usable].reshape(-1, k).mean(axis=1).astype(np.float32)
    n = int(len(x) * target / src_rate)
    if n <= 1:
        return np.zeros(0, dtype=np.float32)
    return np.interp(np.linspace(0, len(x) - 1, n),
                     np.arange(len(x)), x).astype(np.float32)


def _open_endpoint(specs, wanted=None):
    """Pick the render endpoint to capture, by name or the ladder's first rung.

    `loopback_device_specs()` leaves `default` None on every rung on this box
    (MEASURED: 7 active endpoints, `default=None` on all of them), so the
    fallback is the FIRST rung rather than a truthy match -- which on this
    machine is `VoiceMeeter Input`, and that is also what Windows reports as
    the system default output.
    """
    if wanted:
        for spec in specs:
            if wanted.lower() in str(spec.get("name", "")).lower():
                return spec
        return None
    for spec in specs:
        if spec.get("default"):
            return spec
    return specs[0] if specs else None


def _tap_for(spec, sink):
    """Build a REAL `WasapiLoopbackTap` on this endpoint.

    MEASURED, and this signature was wrong in the first draft:
        WasapiLoopbackTap(on_block, block_ms=100, role=0, endpoint_id=None)
    -- a callback and an ENDPOINT ID, not a spec dict with a rate. The draft's
    call would have raised `TypeError` on the first live run, and no oracle
    could have said so, because every oracle drove a fake diarizer and never
    opened a device. Seven endpoints were available; not one of them was ever
    touched until this function was written.
    """
    import wasapi_loopback                                           # noqa: PLC0415
    return wasapi_loopback.WasapiLoopbackTap(
        sink, block_ms=100, role=0, endpoint_id=spec.get("endpoint_id"))


def capture_selftest(args) -> int:
    """The REAL capture, the FAKE diarizer. No model, no sound, no ASR.

    This is the arm that closes the join without loading 277 MB: a genuine
    WASAPI loopback tap on a genuine render endpoint, blocks arriving at the
    endpoint's own rate and channel count, the real ring buffer, the real
    cadence, the real atomic publish -- and a diarizer that invents two
    segments so the OUTPUT can be checked without the model.

    `--duration-s` defaults to something short because it is capturing the
    owner's own audio while he is on a call.
    """
    import wasapi_loopback                                           # noqa: PLC0415
    specs = wasapi_loopback.loopback_device_specs()
    spec = _open_endpoint(specs, args.device)
    if spec is None:
        print("selftest: no render endpoint matches %r" % (args.device,))
        return 2
    src_rate = int(spec.get("rate") or args.rate)
    buf = RingBuffer(rate=args.rate, window_s=args.window_s)
    state = {"blocks": 0, "samples": 0, "first_block_at": None, "peak": 0.0}

    def sink(block):
        mono = to_mono16k(block, src_rate, args.rate)
        if mono.size == 0:
            return
        now = time.time()
        if state["first_block_at"] is None:
            state["first_block_at"] = now
        state["blocks"] += 1
        state["samples"] += int(mono.size)
        peak = float(max(abs(float(mono.min())), float(mono.max())))
        state["peak"] = max(state["peak"], peak)
        buf.push(mono.tolist(), now)

    print("selftest: capturing %r  %d Hz x %dch -> %d Hz mono, into %s"
          % (spec.get("name"), src_rate, int(spec.get("channels") or 1),
             args.rate, args.out))
    tap = _tap_for(spec, sink)
    dial = FakeDiarizer()
    tap.stream.start()
    started = time.time()
    # NOT `started`: a tick at t=0 finds an empty buffer, and in a short run
    # that wasted tick can be the only one. Wait one period first.
    next_tick = started + args.every_s
    try:
        while True:
            now = time.time()
            if args.duration_s and now - started >= args.duration_s:
                break
            if now >= next_tick:
                print("selftest: %s"
                      % json.dumps(tick(buf, dial, args.out, threshold=0.9)))
                next_tick = now + args.every_s
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        tap.stream.stop()

    ok = True

    def chk(cond, name, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print("  %s %s%s" % ("GREEN" if cond else "RED  ", name,
                             ("  " + detail) if detail else ""))

    print("\nCAPTURE SELFTEST (real tap, fake diarizer, no model)")
    chk(state["blocks"] > 0, "blocks arrived from a REAL endpoint",
        "%d blocks in %.1f s" % (state["blocks"], args.duration_s))
    chk(state["samples"] > 0, "and they became 16 kHz samples",
        "%d samples" % state["samples"])
    chk(state["first_block_at"] is not None,
        "the first block carried a wall-clock stamp",
        repr(state["first_block_at"]))
    chk(buf.start_t > 0, "the ring buffer knows where it starts",
        "%.3f" % buf.start_t)
    chk(len(buf) <= buf.capacity, "the ring buffer stayed bounded",
        "%d of %d" % (len(buf), buf.capacity))
    chk(os.path.isfile(args.out), "a payload was published", args.out)
    if os.path.isfile(args.out):
        with open(args.out, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        # Compared against the window the PAYLOAD records, not against
        # `buf.start_t` read now: the ring buffer slid forward after the tick,
        # so reading it afterwards measures a different moment. A first draft
        # did exactly that and reported a 0,9 s discrepancy that was the
        # buffer moving, not the offset being wrong.
        want = payload.get("window_start_abs")
        seg0 = payload["segments"][0]["start"]
        chk(want is not None and abs(seg0 - want - 1.0) < 1e-6,
            "the published segments sit ON the window the capture used",
            "seg0-window_start=%.4f (the fake diarizer says 1.0)"
            % (seg0 - (want or 0.0)))
    print("\n  peak of captured audio = %.5f  (silence is a correct answer when"
          " nothing is playing)" % state["peak"])
    print("\nVERDICT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def _make_live_diarizer(args):
    """The callable `tick` drives.

    `process()` takes the audio and NOTHING ELSE -- MEASURED against
    `_main/_diar-run.py:103`, the call that produced DER 0,03 % today:
    `sd.process(audio).sort_by_start_time()`. The threshold and the cluster
    count are NOT process arguments; they belong to the CLUSTERING config built
    in `_load_sherpa_diarizer`. Passing them here is the second form of the
    same mistake as passing paths instead of configs.
    """
    sdk = _load_sherpa_diarizer(args.seg_model, args.emb_model, args.threads,
                                num_clusters=args.num_speakers,
                                threshold=args.threshold)

    def diarize(samples, threshold=0.9, num_speakers=-1):
        import numpy as np                                             # noqa: PLC0415
        audio = np.asarray(samples, dtype=np.float32)
        result = sdk.process(audio).sort_by_start_time()
        return {"segments": [{"start": float(s.start), "end": float(s.end),
                              "speaker": int(s.speaker)} for s in result]}
    return diarize


def selftest(args) -> int:
    """The whole loop, with no device and no model. Milliseconds."""
    rate = 1000                     # 1 kHz: a 4 s call is 4 000 samples
    buf = RingBuffer(rate=rate, window_s=4.0)
    fake = FakeDiarizer()
    t = 300.0                       # the call started five minutes ago
    pushed = 0
    states = []
    for _ in range(8):              # eight 0,5 s pushes = 4 s of audio
        chunk = [0.01 * ((i % 7) - 3) for i in range(rate // 2)]
        buf.push(chunk, t)
        t += 0.5
        pushed += len(chunk)
        if len(buf) % (rate // 2) == 0:
            states.append(tick(buf, fake, args.out, threshold=0.9))

    payload = {}
    if os.path.isfile(args.out):
        with open(args.out, "r", encoding="utf-8") as fh:
            payload = json.load(fh)

    ok = True

    def chk(cond, name, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print("  %s %s%s" % ("GREEN" if cond else "RED  ", name,
                             ("  " + detail) if detail else ""))

    print("SELFTEST (no model, no audio device, no ASR)")
    chk(fake.calls == len(states) - 1 and len(states) == 8,
        "the cadence ran on every beat", "states=%d diarizer=%d"
        % (len(states), fake.calls))
    # ...and exactly ONE of them was refused before reaching the model, the
    # beat that held half a second. The first draft asserted every tick reached
    # the diarizer; that stopped being true when the minimum-audio floor landed,
    # and the arm was reporting a CORRECT refusal as a failure.
    chk(states[0].get("state") == "too-short",
        "the first beat refused a 0,5 s window instead of asking the model",
        repr(states[0].get("state")))
    chk(all(s.get("state") in ("too-short", "written") for s in states),
        "no beat ever reached the model with too little audio to mean anything")
    chk(len(buf) <= buf.capacity,
        "the buffer is bounded", "%d of %d samples" % (len(buf), buf.capacity))
    chk(abs(buf.window_duration_s() - 4.0) < 1e-6,
        "the buffer holds exactly the window",
        "%.3f s" % buf.window_duration_s())
    chk(pushed == rate * 4, "8 x 0,5 s really is 4 s of audio",
        "%d samples" % pushed)
    chk(bool(payload), "a payload was published", args.out)
    chk(payload.get("fake") is True, "and it says it is a fake")
    chk(payload.get("n_segments") == 2, "with both fake segments",
        repr(payload.get("n_segments")))

    # THE OFFSET. The fake says 1,0-3,0 s of its window. The window started at
    # 300,0 s on the capture clock, so the payload must say 301,0-303,0 s.
    segs = payload.get("segments") or []
    if len(segs) == 2:
        chk(abs(segs[0]["start"] - 301.0) < 1e-9,
            "the offset is applied to the first segment",
            "start=%.3f" % segs[0]["start"])
        chk(abs(segs[1]["end"] - 306.5) < 1e-9,
            "and to the last", "end=%.3f" % segs[1]["end"])
        chk(abs(payload.get("window_start_abs", -1) - buf.start_t) < 1e-9,
            "the payload records which window it came from",
            repr(payload.get("window_start_abs")))
    else:
        chk(False, "the offset is applied", "segments=%r" % (segs,))

    print("\nVERDICT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--window-s", type=float, default=DEFAULT_WINDOW_S)
    ap.add_argument("--every-s", type=float, default=DEFAULT_EVERY_S)
    ap.add_argument("--rate", type=int, default=DEFAULT_RATE)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--min-speech-frac", type=float, default=MIN_SPEECH_FRACTION,
                    help="a partir de que fracao da janela, por envolvente de "
                         "energia, ha fala para merecer identidade. Abaixo "
                         "disso publica-se `segments: []` em vez de uma voz "
                         "inventada. MEDIDO: a gravacao densa da call da 33-79%%, "
                         "a esparsa (89%% de silencio) da 0-23%%, e e' a esparsa "
                         "que criava 12 slots para 2 pessoas. 0 desliga a porta")
    ap.add_argument("--num-speakers", type=int, default=-1)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--device", default=None,
                    help="loopback endpoint name; default is the render mix")
    ap.add_argument("--seg-model", default=DEFAULT_SEG_MODEL)
    ap.add_argument("--emb-model", default=DEFAULT_EMB_MODEL)
    ap.add_argument("--duration-s", type=float, default=0.0,
                    help="stop after this many seconds; 0 runs until killed")
    ap.add_argument("--selftest", action="store_true",
                    help="run the whole loop with a fake diarizer and no device")
    ap.add_argument("--capture-selftest", action="store_true",
                    help="run the REAL WASAPI tap with a fake diarizer: real "
                         "capture, real buffer, real publish, no model")
    ap.add_argument("--no-stable-slots", action="store_true",
                    help="publish the diarizer's LOCAL labels, unremapped. This "
                         "is the behaviour that shipped until the raw-label "
                         "flip was measured; kept so the fix can be turned off "
                         "and the old numbers reproduced")
    ap.add_argument("--watch-only", action="store_true",
                    help="FASE A: answer ONLY 'were two voices talking at the "
                         "same time?'. Loads the 5,7 MB segmentation model and "
                         "NOT the 37,8 MB embeddings one, so it can stay on "
                         "when the full attribution must not (MEASURED: RTF "
                         "0,0097 vs 0,503; 90,3 MB vs 135,4 MB). Writes "
                         "--watch-out, a file with NO `segments` key, so the "
                         "caption path cannot mistake it for a speaker list")
    ap.add_argument("--watch-out", default=DEFAULT_WATCH_OUT)
    ap.add_argument("--watch-save", default=DEFAULT_WATCH_SAVE,
                    help="keep the FLAGGED audio as 16 kHz mono WAV here, so "
                         "'process the voices later' has something to process. "
                         "MEASURED: the RingBuffer is in memory and slides -- a "
                         "window is freed 10 s after it is seen, so without "
                         "this the detection survives and the audio does not. "
                         "Empty = keep nothing (the default)")
    ap.add_argument("--watch-pad-s", type=float, default=DEFAULT_WATCH_PAD_S,
                    help="context kept around each flagged span; a diarizer "
                         "needs a few seconds to settle on a 2 s clip")
    ap.add_argument("--watch-save-max-mb", type=float, default=DEFAULT_WATCH_SAVE_MAX_MB,
                    help="FIFO cap on that directory; the oldest clip goes first")
    ap.add_argument("--watch-hold", type=int, default=DEFAULT_WATCH_HOLD,
                    help="frames a multi-voice run must last to count; %d = %.1f ms"
                         % (DEFAULT_WATCH_HOLD, DEFAULT_WATCH_HOLD * FRAME_S * 1000))
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(args)

    if args.capture_selftest:
        # Short periods on purpose: this is the OWNER'S audio while he is on a
        # call, and the point is to prove the capture works, not to diarize.
        if args.duration_s <= 0:
            args.duration_s = 8.0
        if args.every_s > args.duration_s / 3.0:
            args.every_s = 1.5
        if args.window_s > args.every_s:
            args.window_s = max(1.5, args.every_s * 1.5)
        return capture_selftest(args)

    # FASE A so precisa do modelo de segmentacao. Exigir aqui o de embeddings
    # seria exigir 37,8 MB que este processo nao vai ler.
    needed = [args.seg_model] if args.watch_only else [args.seg_model, args.emb_model]
    missing = [p for p in needed if not os.path.isfile(p)]
    if missing:
        print("sidecar: diarizer models are missing:\n  %s" % "\n  ".join(missing))
        return 2

    import wasapi_loopback                                           # noqa: PLC0415
    specs = wasapi_loopback.loopback_device_specs()
    chosen = _open_endpoint(specs, args.device)
    if chosen is None:
        print("sidecar: no render endpoint matches %r. Candidates:\n  %s"
              % (args.device,
                 "\n  ".join(str(s.get("name")) for s in specs)))
        return 2

    src_rate = int(chosen.get("rate") or args.rate)
    buf = RingBuffer(rate=args.rate, window_s=args.window_s)

    def sink(block):
        mono = to_mono16k(block, src_rate, args.rate)
        if mono.size:
            buf.push(mono.tolist(), time.time())

    out_path = args.watch_out if args.watch_only else args.out
    print("sidecar: capturing %r  %d Hz -> %d Hz mono into %s every %.0f s"
          % (chosen.get("name"), src_rate, args.rate, out_path, args.every_s))
    tap = _tap_for(chosen, sink)
    if args.watch_only:
        sess = _load_powerset(args.seg_model, args.threads)
        slots = None
        print("sidecar: FASE A -- so 'duas vozes ao mesmo tempo?', classes %s, "
              "hold %d frames (%.1f ms). Nao carrega embeddings, nao da nomes."
              % (list(MULTI_CLASSES), args.watch_hold,
                 args.watch_hold * FRAME_S * 1000))
    else:
        sess = None
        diarize = _make_live_diarizer(args)
        slots = None if args.no_stable_slots else StableSpeakerSlots()
        if args.window_s > SAFE_WINDOW_S:
            # AVISO, e nao recusa: quem escolheu uma janela maior pode ter
            # motivos que eu nao vejo, e um portao que se recusa a arrancar
            # impede a pessoa de corrigir o que fez. Mas o numero e' o mesmo
            # em qualquer caso, e o custo e' dele saber.
            print("sidecar: AVISO -- janela de %.0f s ACIMA de %.0f s. MEDIDO: a "
                  "separacao de vozes passa de RTF 0,042 aos 10 s para RTF 0,668 "
                  "aos 11 s, e a RTF 1,69 aos 14 s -- mais lenta do que o tempo "
                  "real durante a call inteira. So a segmentacao (--watch-only) "
                  "e' plana em todo o intervalo. Se a unica razao para a janela "
                  "grande era 'dar mais contexto', 10 s com sobreposicao da mais."
                  % (args.window_s, SAFE_WINDOW_S))
        if slots is None:
            print("sidecar: AVISO -- publicando as etiquetas LOCAIS do diarizador, "
                  "sem remapear. A MESMA pessoa pode trocar de `source` a cada "
                  "janela (medido: 25,0 % de acordo cru num par de janelas da call "
                  "real). Use --no-stable-slots so para reproduzir esse numero.")
    tap.stream.start()
    started = time.time()
    next_tick = started + args.every_s
    # O acumulado de audio perdido, ao longo do processo. Vive AQUI e nao no
    # payload porque o payload e' reescrito a cada janela: sem isto, o total
    # de clips apagados so existia no log, e quem viesse a correr a Fase B
    # depois da call nao tinha como saber que o directorio estava incompleto.
    #
    # E RECOMEÇA DO PAYLOAD JA EXISTENTE, e nao de zero -- ver
    # `resume_evicted_total`, que e' quem explica o porque.
    evicted_total = resume_evicted_total(out_path)
    if evicted_total:
        print("sidecar: a retoma com clips_evicted_total=%d (ja perdidos antes "
              "deste arranque)" % evicted_total)
    try:
        while True:
            now = time.time()
            if args.duration_s and now - started >= args.duration_s:
                break
            if now >= next_tick:
                if args.watch_only:
                    state = watch_tick(buf, sess, out_path, args.watch_hold,
                                       save_dir=args.watch_save,
                                       pad_s=args.watch_pad_s,
                                       max_mb=args.watch_save_max_mb,
                                       evicted_before=evicted_total)
                    evicted_total = int(state.get("n_clips_evicted_total")
                                        or evicted_total)
                    line = ("sidecar: %s spans=%s multi=%.2fs clips=%s "
                            "window=%.1fs"
                            % (state.get("state"), state.get("n_spans"),
                               state.get("multivoice_s", 0.0),
                               state.get("n_clips", 0),
                               buf.window_duration_s()))
                    # `clips` e' o que SOBREVIVEU; `evicted` e' o que a fila
                    # levou. So o primeiro chegava ao log, e era por isso que
                    # numa call longa o audio do dono desaparecia sem ninguem
                    # dizer nada.
                    if state.get("n_clips_evicted"):
                        line += (" EVICTED=%d (fila cheia: o audio mais antigo "
                                 "foi apagado -- %s; total nesta sessao: %d)"
                                 % (state.get("n_clips_evicted"),
                                    ",".join(state.get("clips_evicted_names")
                                             or []),
                                    state.get("n_clips_evicted_total", 0)))
                    print(line)
                else:
                    state = tick(buf, diarize, out_path, args.threshold,
                                 args.num_speakers, slots=slots,
                                 min_speech_fraction=args.min_speech_frac)
                    if state.get("declined"):
                        print("sidecar: %s SEM ATRIBUICAO (fala %.0f%% < %.0f%%)"
                              % (state.get("state"),
                                 100 * state.get("speech_fraction", 0.0),
                                 100 * args.min_speech_frac))
                    else:
                        print("sidecar: %s segments=%s window=%.1fs"
                              % (state.get("state"), state.get("n_segments"),
                                 buf.window_duration_s()))
                next_tick = now + args.every_s
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        tap.stream.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())