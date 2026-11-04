"""Build the pt-BR/en-US fixture set for the Nemotron-Labs-Unified-ASR ladder.

Why TTS and not a random wav: a WER needs a reference nobody can argue about.
These clips are synthesised from the text in ``CLIPS`` with the Windows SAPI
voices that ship on this machine (Microsoft Maria Desktop, pt-BR; Microsoft
Zira Desktop, en-US); the reference IS the authored text, so it is
hand-written by construction. Diarisation fixtures (`_main/diar-mix/*.wav`)
carry no written reference and are not usable for WER.

Nothing is played: ``Speak`` writes into a ``SpFileStream``, the default audio
endpoint is never touched.

Usage (re-runnable, deterministic):
    python worker/unified_fixtures.py --out _main/fixtures/stack-compare/unified-tts
    python worker/unified_fixtures.py --selftest        # verifies the wavs on disk
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# SAFT22kHz16BitMono -- speech format SAPI renders natively; resampled to 16 kHz after.
SAPI_22K_16BIT_MONO = 22
SSFM_CREATE_FOR_WRITE = 3

VOICES = {
    "pt": "Microsoft Maria Desktop - Portuguese(Brazil)",
    "en": "Microsoft Zira Desktop - English (United States)",
}

# (id, language, target seconds, authored text)  -- text is the REFERENCE, verbatim.
CLIPS = [
    ("ptbr-tts-01", "pt", 10.0,
     "A reunião de amanhã foi adiada para sexta-feira, porque o diretor precisa "
     "revisar os números do trimestre."),
    ("ptbr-tts-02", "pt", 13.0,
     "O trânsito na avenida principal está completamente parado desde as sete "
     "horas da manhã, e os motoristas já estão procurando rotas alternativas "
     "para chegar ao centro."),
    ("ptbr-tts-03", "pt", 8.0,
     "Prefiro café sem açúcar, por favor, e um copo de água com gelo."),
    ("enus-tts-01", "en", 10.0,
     "The quarterly report shows that revenue grew eleven percent, while "
     "operating costs stayed almost flat."),
    ("enus-tts-02", "en", 8.0,
     "Please remind me to call the dentist on Thursday morning, before the "
     "meeting starts."),
]


def synth(text: str, voice_name: str, out_path: Path) -> None:
    """Render `text` to `out_path` through SAPI, writing straight to a file."""
    import win32com.client as win32  # noqa: PLC0415

    voice = win32.Dispatch("SAPI.SpVoice")
    picked = None
    tokens = voice.GetVoices()
    for i in range(tokens.Count):
        if tokens.Item(i).GetDescription() == voice_name:
            picked = tokens.Item(i)
            break
    if picked is None:
        raise SystemExit("voice not installed: %s" % voice_name)
    voice.Voice = picked

    stream = win32.Dispatch("SAPI.SpFileStream")
    fmt = win32.Dispatch("SAPI.SpAudioFormat")
    fmt.Type = SAPI_22K_16BIT_MONO
    stream.Format = fmt
    stream.Open(str(out_path), SSFM_CREATE_FOR_WRITE, False)
    try:
        voice.AudioOutputStream = stream
        voice.Speak(text)
    finally:
        stream.Close()


def to_16k_mono(src: Path, dst: Path) -> float:
    import numpy as np  # noqa: PLC0415
    import soundfile as sf  # noqa: PLC0415
    import soxr  # noqa: PLC0415

    data, sr = sf.read(str(src), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if sr != 16000:
        mono = soxr.resample(mono, sr, 16000).astype(np.float32)
    sf.write(str(dst), mono, 16000, subtype="PCM_16")
    return len(mono) / 16000.0


def normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse spaces -- accents preserved."""
    out = []
    for ch in text.lower():
        if ch.isalnum() or ch.isspace() or ch in "áàâãéêíóôõúüçñ":
            out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def build(out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for clip_id, lang, target_s, text in CLIPS:
        raw = out_dir / (clip_id + ".raw.wav")
        final = out_dir / (clip_id + ".wav")
        synth(text, VOICES[lang], raw)
        seconds = to_16k_mono(raw, final)
        raw.unlink()
        rows.append({
            "id": clip_id,
            "file": final.name,
            "lang": lang,
            "seconds": round(seconds, 2),
            "target_seconds": target_s,
            "reference": normalise(text),
            "reference_raw": text,
            "reference_words": len(normalise(text).split()),
            "origin": "SAPI TTS, voice %s; reference = authored text" % VOICES[lang],
        })
        print("BUILT %s %.2fs %d words" % (final.name, seconds, rows[-1]["reference_words"]),
              flush=True)
    (out_dir / "reference.json").write_text(
        json.dumps({
            "why": "Fixture set for the Nemotron-Labs-Unified-ASR streaming ladder: the "
                   "reference is authored text (hand-written by construction), not another "
                   "engine's output.",
            "wer_normalisation": "minusculas, sem pontuacao, espacos colapsados, acentos "
                                 "preservados",
            "clips": rows,
        }, indent=1, ensure_ascii=False), encoding="utf-8")
    return rows


def selftest(out_dir: Path) -> int:
    import soundfile as sf  # noqa: PLC0415

    meta = json.loads((out_dir / "reference.json").read_text(encoding="utf-8"))
    bad = 0
    for clip in meta["clips"]:
        path = out_dir / clip["file"]
        if not path.exists():
            print("MISSING %s" % path)
            bad += 1
            continue
        info = sf.info(str(path))
        ok = info.samplerate == 16000 and info.channels == 1
        print("FIXTURE %s %.2fs sr=%d ch=%d %s"
              % (clip["id"], info.frames / info.samplerate, info.samplerate,
                 info.channels, "OK" if ok else "BAD"))
        bad += 0 if ok else 1
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "_main" / "fixtures" /
                                         "stack-compare" / "unified-tts"))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    if args.selftest:
        return selftest(out_dir)
    build(out_dir)
    return selftest(out_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
