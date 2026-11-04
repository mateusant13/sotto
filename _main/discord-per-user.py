"""Ponte do capturador Discord para a stack do Sotto: censo por falante + WAV 16 kHz.

Le a arvore que `discord/src/receiver-core.js` escreve:

    <out>/<user_id>/<epoch_ms>.pcm    PCM s16le 16 kHz mono
    <out>/<user_id>/<epoch_ms>.jsonl  cabecalho, um registo por pacote, fecho

Nao estima falantes: cada pasta E' um user id do Discord. Mede o que esta no
disco (duracao, RMS lido dos bytes, pacotes do indice) e, com --wav, converte
cada segmento num WAV que os motores do repo ja' consomem.

Uso:
    python _main/discord-per-user.py                      # censo de discord/out
    python _main/discord-per-user.py --out _tmp/discord   # outra arvore
    python _main/discord-per-user.py --wav                # + WAV ao lado do .pcm
    python _main/discord-per-user.py --min-rms 200        # piso de silencio
"""
import argparse
import array
import json
import math
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "discord" / "out"
SAMPLE_RATE = 16000
CHANNELS = 1
READ_BYTES = 1 << 20


def read_index(jsonl_path):
    """(header, packets, closed) do indice; tolera um ficheiro a meio da escrita."""
    header, packets, closed = None, 0, None
    try:
        with open(jsonl_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                kind = row.get("type")
                if kind == "segment":
                    header = row
                elif kind == "packet":
                    packets += 1
                elif kind == "close":
                    closed = row
    except FileNotFoundError:
        pass
    return header, packets, closed


def pcm_stats(pcm_path):
    """Duracao/picos/RMS lidos dos BYTES, em blocos, sem carregar o ficheiro todo."""
    frames = 0
    sum_sq = 0.0
    peak = 0
    with open(pcm_path, "rb") as fh:
        while True:
            chunk = fh.read(READ_BYTES)
            if not chunk:
                break
            usable = len(chunk) - (len(chunk) % 2)
            samples = array.array("h")
            samples.frombytes(chunk[:usable])
            if sys.byteorder == "big":
                samples.byteswap()
            frames += len(samples)
            for s in samples:
                sum_sq += s * s
                magnitude = abs(s)
                if magnitude > peak:
                    peak = magnitude if magnitude <= 32767 else 32767
    duration_ms = frames * 1000.0 / SAMPLE_RATE if frames else 0.0
    rms = math.sqrt(sum_sq / frames) if frames else 0.0
    return {"frames": frames, "duration_ms": duration_ms, "rms": rms, "peak": peak}


def write_wav(pcm_path, wav_path):
    with wave.open(str(wav_path), "wb") as out:
        out.setnchannels(CHANNELS)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        with open(pcm_path, "rb") as src:
            while True:
                chunk = src.read(READ_BYTES)
                if not chunk:
                    break
                out.writeframes(chunk[: len(chunk) - (len(chunk) % 2)])


def main(argv=None):
    ap = argparse.ArgumentParser(description="censo por falante da captura Discord")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="raiz da captura (default discord/out); varre subpastas")
    ap.add_argument("--wav", action="store_true", help="escreve <segmento>.wav ao lado do .pcm")
    ap.add_argument("--min-rms", type=float, default=200.0, help="piso de RMS para 'nao silencioso'")
    args = ap.parse_args(argv)

    out_dir = Path(args.out).resolve()
    if not out_dir.is_dir():
        sys.stderr.write("sem captura em %s (o capturador ainda nao correu?)\n" % out_dir)
        return 2

    rows = []
    for pcm_path in sorted(out_dir.rglob("*.pcm")):
        user_dir = pcm_path.parent
        jsonl = pcm_path.with_suffix(".jsonl")
        header, packets, closed = read_index(jsonl)
        st = pcm_stats(pcm_path)
        wav_path = None
        if args.wav:
            wav_path = pcm_path.with_suffix(".wav")
            write_wav(pcm_path, wav_path)
        rows.append(
            {
                "user": header.get("user_id", user_dir.name) if header else user_dir.name,
                "ssrc": header.get("ssrc") if header else None,
                "pcm": str(pcm_path.relative_to(out_dir)),
                "wav": str(wav_path.relative_to(out_dir)) if wav_path else None,
                "packets": packets,
                "closed": bool(closed),
                **st,
            }
        )

    for row in rows:
        print(
            "discord-per-user user=%s ssrc=%s pcm=%s duration_ms=%.2f rms=%.1f peak=%d "
            "packets=%d bytes=%d silent=%s%s"
            % (
                row["user"],
                row["ssrc"] if row["ssrc"] is not None else "?",
                row["pcm"].replace("\\", "/"),
                row["duration_ms"],
                row["rms"],
                row["peak"],
                row["packets"],
                row["frames"] * 2,
                "yes" if row["rms"] < args.min_rms else "no",
                "" if row["wav"] is None else " wav=" + row["wav"].replace("\\", "/"),
            )
        )

    users = {row["user"] for row in rows}
    print(
        "discord-per-user TOTAL users=%d segments=%d duration_ms=%.2f silent_segments=%d"
        % (
            len(users),
            len(rows),
            sum(r["duration_ms"] for r in rows),
            sum(1 for r in rows if r["rms"] < args.min_rms),
        )
    )
    return 0 if rows else 3


if __name__ == "__main__":
    sys.exit(main())
