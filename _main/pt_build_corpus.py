"""Build the Portuguese ground-truth corpus for lane/ptquality.

Every clip here is SYNTHESIZED by Microsoft Edge neural TTS, EXCEPT
pt-br-sample.wav, which is ORGANIC broadcast audio already in the repo.

WHY SYNTHESIZED, stated plainly: the reference transcript of a TTS clip is the
exact string handed to the synthesizer, so ground truth is known with certainty
and no circularity. `pt-br-sample.wav` is real speech but has NO independent
transcript anywhere on this machine -- the only "transcripts" of it in
`docs/audit/*` are the WORKER'S OWN OUTPUT. Scoring the model against its own
output is circular, so that clip is carried as an UNSCORED probe: it proves the
model emits Portuguese tokens, and it cannot prove accuracy.

It is a lie to call these clips organic. They are clean, studio-grade, single-
utterance, noise-free neural TTS. They are the EASIEST case for an ASR model.
Any number computed on them is an UPPER BOUND on real-world Portuguese
accuracy, not an estimate of it.

Emits `_main/pt-corpus.json`.
"""

import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_main", "pt-corpus")
EDGE = r"C:\Users\Administrador\AppData\Local\hermes\hermes-agent\venv\Scripts\edge-tts.exe"
TARGET_SR = 16000

# (clip_id, voice, reference_text, note)
CLIPS = [
    (
        "pt01",
        "pt-BR-FranciscaNeural",
        "Boa tarde. Hoje o ceu esta nublado e existe uma chance grande de chuva a noite.",
        "pt-BR female",
    ),
    (
        "pt02",
        "pt-BR-AntonioNeural",
        "O ministro da saude anunciou que a vacina gratis estara disponivel em todas as escolas.",
        "pt-BR male",
    ),
    (
        "pt03",
        "pt-BR-ThalitaMultilingualNeural",
        "Eu comprei um pao de mel agora pouco e vou para casa porque a minha mae esta me esperando.",
        "pt-BR female #2",
    ),
    (
        "pt04",
        "pt-PT-RaquelNeural",
        "Boa tarde. Hoje o ceu esta encoberto e existe uma grande hipotese de chuva durante a noite.",
        "pt-PT female (European Portuguese)",
    ),
    (
        "pt05",
        "pt-PT-DuarteNeural",
        "O presidente negociou com o antigo amigo que morava perto da praia quando era crianca.",
        "pt-PT male (European Portuguese)",
    ),
    (
        "pt06",
        "pt-BR-FranciscaNeural",
        "A cidade construiu uma biblioteca nova no centro, e os estudantes ja podem consultar mais de dez mil livros.",
        "pt-BR female, longer utterance",
    ),
    (
        "pt07",
        "pt-BR-AntonioNeural",
        "A reuniao comeca as tres horas da tarde, na sala numero dois, ao lado da biblioteca.",
        "pt-BR male, time + number words",
    ),
]


def synth(clip_id, voice, text, dest):
    """edge-tts -> mp3 -> 16 kHz mono PCM_16 wav."""
    mp3 = dest + ".mp3"
    cmd = [
        EDGE,
        "--voice", voice,
        "--text", text,
        "--write-media", mp3,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not os.path.exists(mp3):
        raise RuntimeError(f"{clip_id}: edge-tts failed rc={r.returncode} {r.stderr[:400]}")

    pcm, sr = sf.read(mp3, dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    if sr != TARGET_SR:
        # linear resample, matching the worker's own non-integer np.interp branch
        n = int(round(len(pcm) * TARGET_SR / sr))
        pcm = np.interp(
            np.linspace(0.0, len(pcm) - 1, n, dtype=np.float64),
            np.arange(len(pcm), dtype=np.float64),
            pcm,
        ).astype(np.float32)
        sr = TARGET_SR
    peak = float(np.max(np.abs(pcm))) if len(pcm) else 0.0
    if peak > 0.0:
        pcm = (pcm / peak) * 0.9
    sf.write(dest, pcm, TARGET_SR, subtype="PCM_16")
    os.remove(mp3)


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []

    for clip_id, voice, ref, note in CLIPS:
        dest = os.path.join(OUT, clip_id + ".wav")
        synth(clip_id, voice, ref, dest)
        i = sf.info(dest)
        manifest.append(
            {
                "id": clip_id,
                "path": os.path.relpath(dest, ROOT).replace("\\", "/"),
                "bytes": os.path.getsize(dest),
                "duration_s": round(i.duration, 3),
                "sr": i.samplerate,
                "source": "synthesized",
                "synth": "edge-tts neural: " + voice,
                "voice": voice,
                "speaker": note,
                "reference": ref,
                "scored": True,
            }
        )
        print(f"{clip_id} {i.duration:6.3f}s {os.path.getsize(dest):>8}B {voice}")

    # The ORGANIC clip. Carried, reported, and NOT scored.
    organic = r"H:\sotto\_main\pt-br-sample.wav"
    oi = sf.info(organic)
    manifest.append(
        {
            "id": "org01",
            "path": organic,
            "bytes": os.path.getsize(organic),
            "duration_s": round(oi.duration, 3),
            "sr": oi.samplerate,
            "source": "organic",
            "synth": "",
            "voice": "unknown (broadcast)",
            "speaker": "real human, broadcast radio",
            "reference": "",
            "scored": False,
            "unscored_reason": (
                "No independent ground truth exists on this machine. The only "
                "transcripts of this clip in docs/audit/* are the WORKER'S OWN "
                "OUTPUT; scoring against them is circular."
            ),
        }
    )
    print(f"org01 {oi.duration:6.3f}s {os.path.getsize(organic):>8}B ORGANIC (unscored)")

    mpath = os.path.join(ROOT, "_main", "pt-corpus.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"\nmanifest -> {mpath}")
    scored = [m for m in manifest if m["scored"]]
    print(f"scored clips = {len(scored)} | organic unscored = {len(manifest) - len(scored)}")


if __name__ == "__main__":
    sys.exit(main())