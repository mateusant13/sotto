"""Capture the microphone and mix it into the PC's loopback stream.

OWNER ORDER, 2026-11-25, verbatim: *"its capture my mic and transcript it aswell,
in real time. and its any mic not just mine cause this will be a product"*.

WHY A MIX AND NOT A SECOND PIPELINE. The product already transcribes and diarizes
ONE stream: the render endpoint's loopback (what the PC plays -- the far side of
a call). The owner's own microphone is not in that stream, so his speech never
reaches the ASR and never gets a speaker slot. Running a second model beside the
first would double the ASR cost on a machine this repo treats as 10x weaker than
it looks; mixing the microphone into the SAME stream costs one PortAudio input
and no second model, and it keeps the diarizer's job unchanged -- it still sees
one conversation and still separates voices by what they sound like.

PRODUCT, NOT ONE MACHINE. The microphone is chosen by the OS's own capture
default (`sounddevice query_devices(kind="input")`), and the only names removed
are devices that cannot be a microphone in the first place: virtual cables, the
Sound Mapper redirect and Stereo Mix (which is a loopback and would put the PC's
audio into the conversation twice). Nothing here names a brand, a model or an
index, so it works on any machine that has a microphone at all, and a machine
without one loses nothing -- the loopback path is byte-identical.

PRIVACY. This opens the microphone the OS points at, which is what the owner
asked for. It never changes a default device, never selects a render endpoint and
never sets a volume -- the same rule the rest of the repo follows for his audio.
If the OS denies the microphone, the refusal is printed by name and the loopback
continues: a missing microphone is not a dead product.
"""

from __future__ import annotations

import collections
import threading

TARGET_SR = 16000

# A mix that does not clip: two full-scale sources summed at 1.0 would need 2.0
# of headroom, so each side is attenuated and the sum is clipped anyway. The ASR
# is far more sensitive to a drowned far side than to 3 dB of level.
LOOPBACK_GAIN = 0.75
MIC_GAIN = 0.75

# The microphone's backlog, bounded in SAMPLES (10 s at 16 kHz). A queue that
# grows with the process lifetime is the defect this ceiling exists to prevent;
# what it drops is counted and printed, never silently discarded.
MIC_BACKLOG_S = 10.0
MIC_BACKLOG_SAMPLES = int(TARGET_SR * MIC_BACKLOG_S)

# Devices that are not microphones: a virtual cable carries the render mix (a
# second copy of the far side), the Sound Mapper is a redirect, and Stereo Mix is
# a loopback of the output. Matched case-insensitively against the device name.
NOT_A_MICROPHONE = (
    "vb-audio", "voicemeeter", "cable input", "cable output", "cable out",
    "sound mapper", "mapeador de som", "driver de captura de som prim",
    "primary capture driver", "stereo mix", "mixagem estereo", "mixagem est",
)


def is_not_a_microphone(name: str) -> bool:
    low = str(name or "").lower()
    return any(pat in low for pat in NOT_A_MICROPHONE)


def pick_microphone(prefer: str | None = None, sd=None):
    """Choose the capture device, and say WHY in the same breath.

    Returns `(device, reason)`, where device is a spec dict with `index`,
    `name`, `max_input_channels` and `default_samplerate`, or `None` plus the
    reason nothing was chosen. An explicit `prefer` is honoured as given -- the
    filters protect the DEFAULT choice, they do not overrule a named one.
    """
    if sd is None:
        import sounddevice as sd

    try:
        devices = list(sd.query_devices())
    except Exception as exc:  # noqa: BLE001 -- no PortAudio is a named refusal
        return None, "no PortAudio device list: %s: %s" % (type(exc).__name__, exc)

    inputs = []
    for index, dev in enumerate(devices):
        if int(dev.get("max_input_channels") or 0) <= 0:
            continue
        entry = dict(dev)
        entry["index"] = index
        inputs.append(entry)
    if not inputs:
        return None, "no capture device on this machine"

    if prefer:
        low = prefer.strip().lower()
        for dev in inputs:
            if low and low in str(dev.get("name", "")).lower():
                return dev, "explicit %r" % prefer
        return None, "no capture device matches %r" % prefer

    physical = [d for d in inputs if not is_not_a_microphone(d.get("name"))]

    # 1. THE OS'S OWN ANSWER. A product does not outsmart the user's Windows
    #    setting; it reads it and only refuses a device that is not a mic.
    try:
        default_name = str(sd.query_devices(kind="input").get("name") or "")
    except Exception:  # noqa: BLE001 -- no default is not an error, just a fallback
        default_name = ""
    if default_name:
        for dev in physical:
            if str(dev.get("name")) == default_name:
                return dev, "os-default %r" % default_name

    # 2. A physical input that calls itself a microphone. Host API order is the
    #    list order, and WASAPI (1) comes before MME/WDM-KS on this host -- the
    #    loop keeps the first match, which is the one the OS itself prefers.
    for dev in physical:
        low = str(dev.get("name", "")).lower()
        if "micro" in low or "mic" in low:
            return dev, "name %r" % dev.get("name")

    # 3. Any physical input at all, so a rename does not cost the feature.
    if physical:
        return physical[0], "only physical input %r" % physical[0].get("name")

    return None, "only virtual capture devices (%r)" % (
        ", ".join(str(d.get("name")) for d in inputs[:3]))


def to_mono16k(block, src_rate: int):
    """numpy-only mono 16 kHz conversion, integer-ratio fast path first."""
    import numpy as np

    pcm = np.asarray(block, dtype=np.float32)
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    src_rate = int(src_rate or TARGET_SR)
    if src_rate == TARGET_SR or pcm.size == 0:
        return np.ascontiguousarray(pcm, dtype=np.float32)
    if src_rate > TARGET_SR and src_rate % TARGET_SR == 0:
        k = src_rate // TARGET_SR
        usable = (pcm.size // k) * k
        if not usable:
            return np.zeros(0, dtype=np.float32)
        return np.ascontiguousarray(pcm[:usable].reshape(-1, k).mean(axis=1),
                                    dtype=np.float32)
    n = int(pcm.size * TARGET_SR / src_rate)
    if n <= 1:
        return np.zeros(0, dtype=np.float32)
    # Linear interpolation on the source grid: adequate for a level mix, and it
    # never changes the length the caller asked for.
    src = np.linspace(0.0, pcm.size - 1, n, dtype=np.float32)
    return np.ascontiguousarray(
        np.interp(src, np.arange(pcm.size, dtype=np.float32), pcm),
        dtype=np.float32)


class MicTap:
    """A PortAudio input stream that publishes 16 kHz mono blocks.

    It is deliberately small: no ring buffer of its own, no thread beyond
    PortAudio's callback. `drain()` hands the caller everything captured since
    the last call, so the mix stays aligned with the loopback block that is
    being assembled instead of running a second clock.
    """

    def __init__(self, device, block_ms: int = 100):
        import numpy as np
        import sounddevice as sd

        self.np = np
        self.device = device
        self.requested = TARGET_SR
        self.rate = TARGET_SR
        try:
            sd.check_input_settings(device=device["index"], channels=1,
                                    dtype="float32", samplerate=TARGET_SR)
        except Exception:  # noqa: BLE001 -- the device converts, or we resample
            self.rate = int(device.get("default_samplerate") or TARGET_SR)
        self.block = max(1, int(self.rate * block_ms / 1000))
        self._lock = threading.Lock()
        self._backlog = []
        self._backlog_samples = 0
        self.dropped_samples = 0
        self.blocks = 0
        self.peak = 0.0
        self.stream = sd.InputStream(
            device=device["index"], channels=1, samplerate=self.rate,
            dtype="float32", blocksize=self.block, callback=self._cb)

    def _cb(self, indata, frames, time_info, status):  # noqa: ARG002
        pcm = to_mono16k(indata, self.rate)
        if not pcm.size:
            return
        with self._lock:
            self._backlog.append(pcm)
            self._backlog_samples += pcm.size
            self.blocks += 1
            self.peak = max(self.peak, float(abs(pcm).max()))
            while self._backlog_samples > MIC_BACKLOG_SAMPLES and self._backlog:
                lost = self._backlog.pop(0)
                self._backlog_samples -= lost.size
                self.dropped_samples += int(lost.size)

    def start(self):
        self.stream.start()
        return self

    def stop(self):
        try:
            self.stream.stop()
        except Exception:  # noqa: BLE001 -- idempotent stop, like the loopback tap
            pass

    def close(self):
        self.stop()
        try:
            self.stream.close()
        except Exception:  # noqa: BLE001
            pass

    def drain(self):
        with self._lock:
            if not self._backlog:
                return None
            pcm = self.np.concatenate(self._backlog)
            self._backlog = []
            self._backlog_samples = 0
        return pcm

    def push_back(self, pcm):
        """Return audio the mix could not consume, so the next block uses it."""
        if pcm is None or not pcm.size:
            return
        with self._lock:
            self._backlog.insert(0, pcm)
            self._backlog_samples += pcm.size
            while self._backlog_samples > MIC_BACKLOG_SAMPLES and self._backlog:
                lost = self._backlog.pop()
                self._backlog_samples -= lost.size
                self.dropped_samples += int(lost.size)


class ConversationTap:
    """The PC's loopback plus the owner's microphone, as ONE 16 kHz stream.

    The loopback is the clock: every block it delivers is converted, the
    microphone's audio captured since the previous block is added on top, and
    the sum is what the caller's sink sees. That keeps the worker and the
    diarizer on the single-stream contract they were written for, and a silent
    microphone degrades to exactly the old behaviour instead of a stutter.

    Built in two phases on purpose: the primary tap's callback is THIS object's
    `_on_primary`, so the primary cannot be constructed before it exists.
    """

    def __init__(self, mic, sink, note=""):
        self.mic = mic
        self.sink = sink
        self.note = note
        self.primary = None
        self.rate = TARGET_SR
        self.native_rate = TARGET_SR
        self.src_rate = TARGET_SR
        self.device = None
        self.endpoint_id = None
        self.block_ms = 100
        self.blocks = 0
        self.mic_blocks = 0
        self._silent_reported = False
        self.stream = self

    def attach(self, primary):
        self.primary = primary
        self.src_rate = int(getattr(primary, "rate", TARGET_SR) or TARGET_SR)
        self.device = getattr(primary, "device", None)
        self.endpoint_id = getattr(primary, "endpoint_id", None)
        self.block_ms = int(getattr(primary, "block_ms", 100) or 100)
        return self

    @property
    def name(self):
        return getattr(self.primary, "name", "WASAPI loopback + microphone")

    def __getattr__(self, name):
        """Everything else a tap owes the loop lives on the loopback tap.

        MEASURED 2026-11-25, and it cost a whole run: the worker read
        `tap.block` (frames per block) and died with
        `AttributeError: 'ConversationTap' object has no attribute 'block'` --
        the run printed zero captions and the join could not measure anything.
        The mix owns the rate and the callback; the block size, the channel
        count and the pump diagnostics belong to the endpoint it wraps.
        """
        primary = self.__dict__.get("primary")
        if primary is None:
            raise AttributeError(name)
        return getattr(primary, name)

    def start(self):
        self.mic.start()
        self.primary.stream.start()
        return self

    def stop(self):
        try:
            self.primary.stream.stop()
        except Exception:  # noqa: BLE001 -- stop is idempotent by contract
            pass
        self.mic.stop()

    def close(self):
        self.stop()
        try:
            self.primary.stream.close()
        except Exception:  # noqa: BLE001
            pass
        self.mic.close()

    def _on_primary(self, block):
        import numpy as np

        pcm = to_mono16k(block, self.src_rate)
        # THE LOOPBACK GAIN IS ALWAYS APPLIED, not only on blocks that happen to
        # carry microphone audio: a level that jumps 0.75 <-> 1.0 between blocks
        # is the AGC pumping that a fixed mix exists to avoid. Measured in the
        # first unit check: the same 0.4 block arrived as 0.45 with a mic block
        # and 0.4 without one.
        # NOT in place: `to_mono16k` returns the caller's own buffer when the
        # source is already 16 kHz, and the loopback pump owns that buffer.
        pcm = pcm * LOOPBACK_GAIN
        microphone = self.mic.drain()
        if microphone is not None and microphone.size:
            self.mic_blocks += 1
            n = min(pcm.size, microphone.size)
            pcm[:n] += microphone[:n] * MIC_GAIN
            if microphone.size > n:
                self.mic.push_back(microphone[n:])
        np.clip(pcm, -1.0, 1.0, out=pcm)
        self.blocks += 1
        # A MICROPHONE THAT DELIVERS ZEROS IS A FACT, NOT A QUIET STREAM. MEASURED
        # 2026-11-25: the owner's USB microphone returned a peak of 0.00003 on
        # MME and DirectSound and refused to open on WASAPI -- i.e. muted, at
        # level 0, or blocked by the microphone privacy setting. Without this
        # line the product looks like it is listening and simply hearing nobody,
        # which is the class of silence this repo already refuses to leave
        # unexplained. Reported ONCE per stream, so it cannot spam the log.
        if (not self._silent_reported and self.blocks >= 50
                and float(self.mic.peak) < 1e-4):
            self._silent_reported = True
            print("MIC_SILENT device=%r reason=digital-silence "
                  "(muted, level 0, or microphone permission denied) "
                  "blocks=%d peak=%.6f"
                  % (self.mic.device.get("name"), self.blocks, float(self.mic.peak)))
        self.sink(np.ascontiguousarray(pcm, dtype=np.float32))

    def summary(self) -> str:
        """One line a caller logs: what was mixed in, and what was dropped."""
        return ("device=%r rate=%d blocks=%d mic_blocks=%d peak=%.3f "
                "dropped_s=%.2f" % (self.mic.device.get("name"), self.mic.rate,
                                    self.blocks, self.mic_blocks, self.mic.peak,
                                    self.mic.dropped_samples / float(TARGET_SR)))


def _mic_or_refusal(prefer):
    """`(MicTap_or_None, note)` -- the note is printable in both directions."""
    try:
        mic_device, reason = pick_microphone(prefer)
    except Exception as exc:  # noqa: BLE001 -- a broken device list is not fatal
        return None, "device list failed: %s: %s" % (type(exc).__name__, exc)
    if mic_device is None:
        return None, "no microphone: %s" % reason
    try:
        mic = MicTap(mic_device, block_ms=100)
    except Exception as exc:  # noqa: BLE001 -- permission, busy device, no PortAudio
        return None, "microphone %r refused: %s: %s" % (
            mic_device.get("name"), type(exc).__name__, exc)
    return mic, "device=%r (%s) mixed into the loopback stream" % (
        mic_device.get("name"), reason)


def open_stream(make_primary, sink, prefer=None, enabled=True):
    """Always a tap plus the microphone note; the loopback path is unchanged.

    `make_primary(on_block)` builds the loopback tap. When a microphone is
    available it is mixed in; when it is not, the primary is built exactly as
    before and the note says why.
    """
    import os

    if not enabled or os.environ.get("SOTTO_MIC", "1").strip().lower() in (
            "0", "off", "no", "false"):
        return make_primary(sink), "disabled by SOTTO_MIC"
    mic, note = _mic_or_refusal(prefer)
    if mic is None:
        return make_primary(sink), note
    mixed = ConversationTap(mic, sink, note=note)
    return mixed.attach(make_primary(mixed._on_primary)), note
