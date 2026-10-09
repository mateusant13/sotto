"""Census: is there a NOISE REMOVER anywhere in this repo's audio path?

WHY THIS EXISTS (lane MEDICAO, live-audio sweep)
------------------------------------------------
The owner asked: "garanta que o removedor de ruido esteja funcionando". Before
answering "it works" or "it is missing", the FIRST question is whether the thing
exists at all. This instrument answers that by SCANNING, and it is built so that
a zero result is a measurement rather than an impression:

  * every DENOISER pattern is scanned across the audio-path files;
  * the SAME instrument scans POSITIVE-CONTROL patterns -- stages that ARE known
    to live in those exact files (`SpeechMusicGate`, `AutoGain`, `AudioMeter`,
    `StreamAsr`, `resample_to_16k`, `CUDAExecutionProvider`). If a control comes
    back ZERO the instrument is broken and every other zero is void;
  * it also prints the ORDER of the stages it found, so the answer can say where
    a denoiser WOULD belong (before the VAD/gate? before the encoder?) instead of
    only that it is absent.

Read-only. Opens no device, writes nothing.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))

# The files the live audio actually travels through. `docs/` is excluded on
# purpose: prose ABOUT a denoiser is not a denoiser, and the question is about
# code that runs.
SCAN_DIRS = ["worker", "app"]
SCAN_EXT = (".py", ".js", ".json", ".html", ".css")
SKIP_DIR_PARTS = ("node_modules", "models", "__pycache__", ".git", "_legacy-electron")

DENOISER = [
    ("rnnoise", r"rnnoise|rn_noise"),
    ("deepfilter", r"deepfilter|deep_filter"),
    ("noise-suppress", r"noise_suppress|noisesuppress|noise_suppression"),
    ("webrtc-ns", r"webrtc|webrtcns|ns_level|nslevel"),
    ("speex", r"speex"),
    ("denoise", r"denois|de_noise|denoiser"),
    ("noise-reduction", r"noise_reduc|noisereduc|noiseReduction"),
    ("spectral-subtraction", r"spectral_sub|spectral_subtraction"),
    ("wiener", r"wiener"),
    ("noise-gate", r"noise_gate|noisegate"),
    ("ffmpeg-denoise-filters", r"afftdn|anlmdn|arnndn"),
    ("sox-noisered", r"noisered"),
]

CONTROLS = [
    ("SpeechMusicGate", r"SpeechMusicGate"),
    ("AutoGain", r"AutoGain"),
    ("AudioMeter", r"AudioMeter"),
    ("StreamAsr", r"StreamAsr"),
    ("resample_to_16k", r"resample_to_16k"),
    ("CUDAExecutionProvider", r"CUDAExecutionProvider"),
    ("Silero/VAD option", r"use_vad"),
]

# Stage markers, in the order the live path is believed to run them. The line
# numbers are PRINTED, not trusted -- they are how a reader re-checks the order.
STAGES = [
    ("AGC (gain only, not a denoiser)", r"class AutoGain"),
    ("per-window level for the panel", r"class AudioMeter"),
    ("speech/music GATE (selects, never cleans)", r"class SpeechMusicGate"),
    ("chunk -> 16 kHz", r"def resample_to_16k"),
    ("the decode", r"class StreamAsr"),
    ("chunk boundary -> word boundary fix", r"def join_fragments"),
    ("continuation read from TOKENS", r"def chunk_is_continuation"),
]


def iter_files():
    for d in SCAN_DIRS:
        root = os.path.join(REPO, d)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [x for x in dirnames
                           if not any(p in x for p in SKIP_DIR_PARTS)
                           and not any(p in os.path.join(dirpath, x) for p in SKIP_DIR_PARTS)]
            for fn in filenames:
                if fn.lower().endswith(SCAN_EXT):
                    yield os.path.join(dirpath, fn)


def main():
    files = sorted(iter_files())
    print(f"instrument : noise-remover-census.py")
    print(f"repo       : {REPO}")
    print(f"scope      : dirs={SCAN_DIRS} ext={SCAN_EXT} skipped={SKIP_DIR_PARTS}")
    print(f"files      : {len(files)}")
    print()

    # ── read every file ONCE ────────────────────────────────────────────────
    blobs = []
    for p in files:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                blobs.append((p, fh.read()))
        except OSError as e:
            print(f"UNREADABLE {p}: {e}")
    total_bytes = sum(len(t) for _p, t in blobs)
    print(f"bytes read : {total_bytes}")
    print()

    def scan(patterns, title):
        print(f"===== {title} =====")
        for label, pat in patterns:
            rx = re.compile(pat)
            hits = []
            for p, text in blobs:
                n = len(rx.findall(text))
                if n:
                    hits.append((os.path.relpath(p, REPO), n))
            if hits:
                print(f"  MATCH  {label:26s} {pat}")
                for rel, n in hits:
                    print(f"           {n:5d} x {rel}")
            else:
                print(f"  ZERO   {label:26s} {pat}")
        print()

    scan(DENOISER, "DENOISER PATTERNS (the question)")
    scan(CONTROLS, "POSITIVE CONTROLS (must NOT be zero -- else the scan is void)")

    print("===== STAGE MARKERS IN THE LIVE AUDIO PATH (order = line number) =====")
    for label, pat in STAGES:
        rx = re.compile(pat)
        found = []
        for p, text in blobs:
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    found.append((os.path.relpath(p, REPO), i))
        if found:
            for rel, i in found:
                print(f"  {rel}:{i}  {label}")
        else:
            print(f"  ZERO  {label}   ({pat})")
    print()

    # ── the encoder's own view of what it receives ──────────────────────────
    print("===== config.json audio/model keys =====")
    import json
    cfg_path = os.path.join(REPO, "worker", "config.json")
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    print("  audio keys :", sorted((cfg.get("audio") or {}).keys()))
    print("  model keys :", sorted((cfg.get("model") or {}).keys()))
    print("  use_vad    :", (cfg.get("model") or {}).get("use_vad"))
    print("  lang_id    :", (cfg.get("model") or {}).get("lang_id"))
    noise_keys = [k for k in list((cfg.get("audio") or {})) + list((cfg.get("model") or {}))
                  if re.search(r"denois|noise|rnnoise|deepfilter|ns_|suppress", k, re.I)]
    print(f"  noise-shaped keys: {noise_keys if noise_keys else 'NONE'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
