#!/usr/bin/env python
"""Prepare a tiny, content-addressed two-speaker Certas Palavras mixture.

This helper is intentionally separate from model execution. It validates the
already-acquired local references, normalizes only two bounded WAVs to 16 kHz
mono, creates clean controls plus one deterministic overlap mix, and writes no
transcript text to generated artifacts or stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_MANIFEST = REPO / ".agent-work" / "asr-cache" / "certas-palavras-small" / "manifest.json"
OUTPUT_ROOT = REPO / ".agent-work" / "asr-cache" / "certas-palavras-small" / "overlap"
EXPECTED_MANIFEST_SHA256 = "eb5cd7915543817b6d02dd1d2705143ffe143477fb13fb58b5e6706fd80a2a47"
EXPECTED_REVISION = "18e4cffc2e335156ac7341a95591dce8a793176c"
EXPECTED_RECORDS = {
    "a3e60c8a811db684": {
        "audio_file": "speaker_a-df8d5d6fa8663543.wav",
        "audio_bytes": 135208,
        "audio_sha256": "df8d5d6fa8663543a33b62da0657b432e7c0daa00fb510f8df290dff3ce71cce",
        "reference_sha256": "f35bd842bc62fb86bbaec84ce37ba4a65df7f24a9bc401592a304bcf68096607",
        "reference_word_count": 10,
    },
    "eceb99b403277625": {
        "audio_file": "speaker_b-c7463582d5d1fb65.wav",
        "audio_bytes": 80808,
        "audio_sha256": "c7463582d5d1fb6565efa71d9f3eb30e5558d6e2144d52baf6ceeaf81583f158",
        "reference_sha256": "f4a0e81dc7d2fee1f1063a2edaa5e70c653b98c2534abaa5f3fd063193895e35",
        "reference_word_count": 5,
    },
}
TARGET_RATE = 16000
MAX_MANIFEST_BYTES = 64 * 1024
MAX_SOURCE_BYTES = 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 2 * 1024 * 1024
MAX_SOURCE_SECONDS = 10.0
MAX_SOURCE_TOTAL_SAMPLES = TARGET_RATE * 15
MAX_MIX_SECONDS = 10.0
MAX_WAV_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MIX_PEAK_LIMIT = 0.95
ALGORITHM = "certas-two-source-overlap-v2"


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _contains_transcript_field(value) -> bool:
    if isinstance(value, dict):
        return any(str(key).casefold() in {"reference_text", "transcript", "transcription"}
                   or _contains_transcript_field(item)
                   for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_transcript_field(item) for item in value)
    return False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_digest_matches(raw: bytes, expected: str = EXPECTED_MANIFEST_SHA256) -> bool:
    return len(raw) <= MAX_MANIFEST_BYTES and _sha256(raw) == expected


def _require_digest(raw: bytes, expected: str, label: str) -> None:
    if not isinstance(expected, str) or _sha256(raw) != expected:
        raise ValueError("Certas %s checksum mismatch" % label)


def _require_wav_size(size: int) -> None:
    if size < 44 or size > MAX_WAV_BYTES:
        raise ValueError("prepared Certas WAV exceeds the 1 MiB file cap")


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _read_manifest(path: Path) -> tuple[dict, bytes, list[dict]]:
    if not _inside(REPO, path) or path.is_symlink():
        raise ValueError("reference manifest must be a regular H: project file")
    raw = path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("reference manifest exceeds its byte cap")
    digest = _sha256(raw)
    if not _manifest_digest_matches(raw):
        raise ValueError("Certas reference manifest digest does not match the pinned cohort")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Certas reference manifest is invalid JSON") from exc
    if (not isinstance(manifest, dict)
            or manifest.get("schema") != 1
            or manifest.get("dataset") != "nilc-nlp/certas_palavras"
            or manifest.get("dataset_revision") != EXPECTED_REVISION
            or manifest.get("split") != "dev"
            or manifest.get("license") != "CC BY-NC 4.0; local noncommercial evaluation with attribution"):
        raise ValueError("Certas manifest identity, split, schema, or local-use license differs")
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 2:
        raise ValueError("Certas manifest must contain exactly two pinned records")
    rows = []
    seen_speakers = set()
    total_audio_bytes = 0
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Certas record has an invalid shape")
        speaker_hash = record.get("speaker_hash")
        expected = EXPECTED_RECORDS.get(speaker_hash)
        if expected is None or speaker_hash in seen_speakers:
            raise ValueError("Certas speaker identity is unknown or duplicated")
        seen_speakers.add(speaker_hash)
        for key, value in expected.items():
            if record.get(key) != value:
                raise ValueError("Certas record failed pinned %s validation" % key)
        audio_name = record.get("audio_file")
        if (not isinstance(audio_name, str) or Path(audio_name).name != audio_name
                or not audio_name.lower().endswith(".wav")):
            raise ValueError("Certas audio filename is not canonical")
        reference = record.get("reference_text")
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Certas reference text is missing")
        reference_bytes = reference.encode("utf-8")
        _require_digest(reference_bytes, expected["reference_sha256"], "reference")
        if len(reference.split()) != expected["reference_word_count"]:
            raise ValueError("Certas reference word count mismatch")
        audio_path = path.parent / audio_name
        if audio_path.is_symlink() or not audio_path.is_file():
            raise ValueError("Certas source WAV is missing or not a regular file")
        audio_bytes = audio_path.stat().st_size
        if audio_bytes != expected["audio_bytes"] or audio_bytes > MAX_SOURCE_BYTES:
            raise ValueError("Certas source WAV size mismatch or cap exceeded")
        raw_audio = audio_path.read_bytes()
        _require_digest(raw_audio, expected["audio_sha256"], "source WAV")
        total_audio_bytes += audio_bytes
        row = dict(record)
        row["_audio_path"] = audio_path
        rows.append(row)
    if seen_speakers != set(EXPECTED_RECORDS):
        raise ValueError("Certas manifest does not contain the exact two-source cohort")
    if total_audio_bytes > MAX_SOURCE_TOTAL_BYTES:
        raise ValueError("Certas source bytes exceed the aggregate cap")
    # Speaker IDs remain anonymous and stable in generated ordering.
    rows.sort(key=lambda row: row["speaker_hash"])
    return manifest, raw, rows


def _runtime_audio_modules():
    # Bound every numeric pool before importing audio libraries.
    _set_single_thread_environment()
    import numpy as np
    import scipy
    import soundfile as sf
    from scipy.signal import resample_poly
    return np, scipy, sf, resample_poly


def _set_single_thread_environment() -> None:
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[name] = "1"


def _normalize_source(path: Path, np, sf, resample_poly) -> tuple[object, dict]:
    info = sf.info(str(path))
    if (info.format != "WAV" or info.subtype not in ("PCM_16", "PCM_24", "PCM_32")
            or info.channels not in (1, 2) or info.samplerate < 8000
            or info.samplerate > 48000 or info.frames <= 0
            or info.frames > int(info.samplerate * MAX_SOURCE_SECONDS)):
        raise ValueError("Certas WAV must be bounded PCM mono/stereo at 8-48 kHz")
    samples, rate = sf.read(str(path), dtype="float32", always_2d=True)
    if (int(rate) != int(info.samplerate) or samples.shape != (info.frames, info.channels)
            or not np.isfinite(samples).all()):
        raise ValueError("Certas WAV decode metadata or sample values are invalid")
    mono = samples.mean(axis=1, dtype=np.float32) if info.channels == 2 else samples[:, 0]
    if rate != TARGET_RATE:
        divisor = int(np.gcd(int(rate), TARGET_RATE))
        mono = resample_poly(mono, TARGET_RATE // divisor, int(rate) // divisor)
    mono = np.ascontiguousarray(mono, dtype=np.float32)
    if (mono.size <= 0 or mono.size > int(TARGET_RATE * MAX_SOURCE_SECONDS)
            or float(np.max(np.abs(mono))) > 1.0001):
        raise ValueError("normalized Certas source exceeds sample or amplitude cap")
    return mono, {"source_rate": int(rate), "source_channels": int(info.channels),
                  "normalized_samples": int(mono.size)}


def _encode_wav(samples, np, sf) -> bytes:
    stream = io.BytesIO()
    sf.write(stream, np.ascontiguousarray(samples, dtype=np.float32), TARGET_RATE,
             format="WAV", subtype="PCM_16")
    data = stream.getvalue()
    _require_wav_size(len(data))
    return data


def _mix_arrays(source_rows: list[dict], arrays: list[object], np) -> tuple[list[object], dict]:
    if len(source_rows) != 2 or len(arrays) != 2:
        raise ValueError("exactly two anonymous Certas sources are required")
    if any(array.ndim != 1 or array.size <= 0 for array in arrays):
        raise ValueError("Certas normalized sources must be nonempty mono arrays")
    if sum(int(array.size) for array in arrays) > MAX_SOURCE_TOTAL_SAMPLES:
        raise ValueError("normalized Certas source samples exceed the aggregate cap")
    # Center the shorter source in the longer one. This guarantees complete
    # deterministic overlap while preserving any unmatched longer-source audio.
    longer = 0 if arrays[0].size >= arrays[1].size else 1
    shorter = 1 - longer
    offset = max(0, (int(arrays[longer].size) - int(arrays[shorter].size)) // 2)
    starts = [0, 0]
    starts[shorter] = offset
    total = max(starts[i] + int(arrays[i].size) for i in range(2))
    if total > int(TARGET_RATE * MAX_MIX_SECONDS):
        raise ValueError("Certas overlap mixture exceeds the 10 s sample cap")
    mix = np.zeros(total, dtype=np.float32)
    for index, array in enumerate(arrays):
        start = starts[index]
        mix[start:start + array.size] += array
    peak_before = float(np.max(np.abs(mix))) if mix.size else 0.0
    gain = min(1.0, MIX_PEAK_LIMIT / peak_before) if peak_before > 0.0 else 1.0
    if gain < 0.0 or not np.isfinite(gain):
        raise ValueError("Certas mixture gain is invalid")
    mix *= np.float32(gain)
    peak_after = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak_after > MIX_PEAK_LIMIT + 1e-6:
        raise ValueError("Certas overlap mixture clipping guard failed")
    overlap = max(0, min(starts[0] + int(arrays[0].size),
                         starts[1] + int(arrays[1].size)) - max(starts[0], starts[1]))
    if overlap <= 0:
        raise ValueError("Certas deterministic placement produced no speech overlap")
    return [arrays[0], arrays[1], np.ascontiguousarray(mix)], {
        "source_order": [row["speaker_hash"] for row in source_rows],
        "source_offsets_samples": starts,
        "overlap_samples": int(overlap),
        "mixture_samples": int(total),
        "peak_before_gain": round(peak_before, 8),
        "gain": round(float(gain), 8),
        "peak_after_gain": round(peak_after, 8),
    }


def _verify_cache(directory: Path, expected_key: str) -> dict:
    required = {"mix.wav", "clean_0.wav", "clean_1.wav", "manifest.json"}
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("content-addressed Certas cache is not a regular directory")
    entries = set(os.listdir(directory))
    if entries != required:
        raise ValueError("content-addressed Certas cache has missing or extra files")
    meta_path = directory / "manifest.json"
    if meta_path.is_symlink() or meta_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("prepared Certas manifest is invalid or oversized")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("prepared Certas manifest is invalid JSON") from exc
    manifest_digest = meta.get("manifest_sha256") if isinstance(meta, dict) else None
    digest_payload = dict(meta) if isinstance(meta, dict) else {}
    digest_payload.pop("manifest_sha256", None)
    if (not isinstance(meta, dict) or meta.get("schema") != 1
            or meta.get("key") != expected_key or meta.get("algorithm") != ALGORITHM
            or _contains_transcript_field(meta)
            or manifest_digest != _sha256(_canonical(digest_payload))
            or meta.get("source_manifest_sha256") != EXPECTED_MANIFEST_SHA256
            or meta.get("code_sha256") != _sha256(Path(__file__).read_bytes())
            or meta.get("sample_rate") != TARGET_RATE
            or meta.get("channels") != 1 or meta.get("subtype") != "PCM_16"):
        raise ValueError("prepared Certas manifest identity or privacy check failed")
    try:
        key_data = {
            "algorithm": meta["algorithm"],
            "source_manifest_sha256": meta["source_manifest_sha256"],
            "sources": meta["sources"],
            "source_offsets_samples": meta["mixture"]["source_offsets_samples"],
            "target_rate": meta["sample_rate"],
            "mix_peak_limit": meta["mix_peak_limit"],
            "scipy_version": meta["audio_library_versions"]["scipy"],
            "soundfile_version": meta["audio_library_versions"]["soundfile"],
            "libsndfile_version": meta["audio_library_versions"]["libsndfile"],
            "code_sha256": meta["code_sha256"],
            "files": meta["files"],
        }
    except (KeyError, TypeError):
        raise ValueError("prepared Certas manifest lacks content-key inputs")
    if _sha256(_canonical(key_data)) != expected_key:
        raise ValueError("prepared Certas content key does not match its manifest")
    files = meta.get("files")
    if not isinstance(files, dict) or set(files) != {"mix.wav", "clean_0.wav", "clean_1.wav"}:
        raise ValueError("prepared Certas file inventory is invalid")
    total = meta_path.stat().st_size
    audio_total = 0
    for name in sorted(files):
        path = directory / name
        row = files[name]
        if path.is_symlink() or not path.is_file() or not isinstance(row, dict):
            raise ValueError("prepared Certas WAV is missing or unsafe")
        size = path.stat().st_size
        try:
            _require_wav_size(size)
        except ValueError as exc:
            raise ValueError("prepared Certas WAV size or cap differs") from exc
        if (type(row.get("bytes")) is not int or size != row.get("bytes")
                or not isinstance(row.get("sha256"), str)
                or len(row["sha256"]) != 64):
            raise ValueError("prepared Certas WAV size or cap differs")
        if _sha256(path.read_bytes()) != row.get("sha256"):
            raise ValueError("prepared Certas WAV content hash differs")
        total += size
        audio_total += size
    if type(meta.get("total_audio_bytes")) is not int or meta["total_audio_bytes"] != audio_total:
        raise ValueError("prepared Certas aggregate audio byte count differs")
    if total > MAX_OUTPUT_BYTES:
        raise ValueError("prepared Certas cache exceeds its aggregate artifact cap")
    return meta


def load_reference_bundle(prepared_dir: Path) -> dict:
    """Validate a prepared artifact and return private refs only to its caller."""
    directory = Path(prepared_dir)
    if (not _inside(OUTPUT_ROOT, directory) or directory.is_symlink()
            or directory.name != directory.resolve().name
            or len(directory.name) != 64):
        raise ValueError("Certas prepared directory is outside its content cache")
    meta = _verify_cache(directory, directory.name)
    _manifest, _raw, rows = _read_manifest(SOURCE_MANIFEST)
    sources = meta.get("sources")
    if not isinstance(sources, list) or len(sources) != 2:
        raise ValueError("prepared Certas artifact does not attest two references")
    private_rows = []
    for index, row in enumerate(rows):
        src = sources[index]
        clean_name = "clean_%d.wav" % index
        if (not isinstance(src, dict)
                or src.get("source_index") != index
                or src.get("speaker_hash") != row["speaker_hash"]
                or src.get("source_audio_sha256") != row["audio_sha256"]
                or src.get("reference_sha256") != row["reference_sha256"]
                or src.get("reference_word_count") != row["reference_word_count"]
                or src.get("clean_wav") != clean_name
                or src.get("clean_wav_sha256") != meta["files"][clean_name]["sha256"]):
            raise ValueError("prepared Certas source/reference binding differs")
        private_rows.append({
            "reference_text": row["reference_text"],
            "reference_sha256": row["reference_sha256"],
            "reference_word_count": row["reference_word_count"],
            "clean_wav": directory / clean_name,
        })
    return {"meta": meta, "records": private_rows,
            "mix_wav": directory / "mix.wav", "directory": directory}


def prepare(manifest_path: Path = SOURCE_MANIFEST, output_root: Path = OUTPUT_ROOT) -> dict:
    if not _inside(REPO, output_root) or output_root.drive.lower() != REPO.drive.lower():
        raise ValueError("Certas output must remain on the H: project volume")
    manifest, manifest_bytes, rows = _read_manifest(manifest_path)
    np, scipy, sf, resample_poly = _runtime_audio_modules()
    arrays = []
    normalization = []
    for row in rows:
        array, info = _normalize_source(row["_audio_path"], np, sf, resample_poly)
        arrays.append(array)
        normalization.append(info)
    if sum(int(array.size) for array in arrays) > MAX_SOURCE_TOTAL_SAMPLES:
        raise ValueError("Certas normalized source sample cap exceeded")
    prepared_arrays, mix_info = _mix_arrays(rows, arrays, np)
    wav_data = [_encode_wav(array, np, sf) for array in prepared_arrays]
    names = ("clean_0.wav", "clean_1.wav", "mix.wav")
    payloads = dict(zip(names, wav_data))
    file_rows = {name: {"bytes": len(data), "sha256": _sha256(data)}
                 for name, data in payloads.items()}
    source_rows = [{
        "source_index": index,
        "speaker_hash": row["speaker_hash"],
        "source_audio_sha256": row["audio_sha256"],
        "source_audio_bytes": row["audio_bytes"],
        "reference_sha256": row["reference_sha256"],
        "reference_word_count": row["reference_word_count"],
        "clean_wav": "clean_%d.wav" % index,
        "clean_wav_sha256": file_rows["clean_%d.wav" % index]["sha256"],
        **normalization[index],
    } for index, row in enumerate(rows)]
    code_hash = _sha256(Path(__file__).read_bytes())
    key_data = {
        "algorithm": ALGORITHM,
        "source_manifest_sha256": _sha256(manifest_bytes),
        "sources": source_rows,
        "source_offsets_samples": mix_info["source_offsets_samples"],
        "target_rate": TARGET_RATE,
        "mix_peak_limit": MIX_PEAK_LIMIT,
        "scipy_version": scipy.__version__,
        "soundfile_version": sf.__version__,
        "libsndfile_version": sf.__libsndfile_version__,
        "code_sha256": code_hash,
        "files": file_rows,
    }
    key = _sha256(_canonical(key_data))
    output_root.mkdir(parents=True, exist_ok=True)
    prefix = output_root / key[:2]
    prefix.mkdir(parents=True, exist_ok=True)
    target = prefix / key
    if target.exists():
        meta = _verify_cache(target, key)
        return {"state": "CACHE HIT", "key": key, "manifest_sha256": meta["manifest_sha256"],
                "artifact_dir": str(target),
                "audio_bytes": sum(meta["files"][name]["bytes"] for name in meta["files"]),
                "reference_count": 2, "reference_words": sum(r["reference_word_count"] for r in rows)}
    artifact_total = sum(len(data) for data in payloads.values())
    if artifact_total > MAX_OUTPUT_BYTES:
        raise ValueError("prepared Certas audio artifacts exceed the 2 MiB cap")
    generated = {
        "schema": 1,
        "algorithm": ALGORITHM,
        "key": key,
        "source_manifest_sha256": _sha256(manifest_bytes),
        "dataset_revision": manifest["dataset_revision"],
        "split": manifest["split"],
        "license": manifest["license"],
        "sample_rate": TARGET_RATE,
        "channels": 1,
        "subtype": "PCM_16",
        "sources": source_rows,
        "mixture": mix_info,
        "mix_peak_limit": MIX_PEAK_LIMIT,
        "files": file_rows,
        "total_audio_bytes": artifact_total,
        "code_sha256": code_hash,
        "audio_library_versions": {
            "scipy": scipy.__version__, "soundfile": sf.__version__,
            "libsndfile": sf.__libsndfile_version__,
        },
    }
    generated["manifest_sha256"] = _sha256(_canonical(generated))
    stage = prefix / (".stage-" + key)
    if stage.exists():
        if (stage.is_symlink() or not stage.is_dir()
                or not _inside(prefix, stage) or stage.parent.resolve() != prefix.resolve()):
            raise ValueError("stale Certas staging path is unsafe")
        shutil.rmtree(stage)
    stage.mkdir()
    if not _inside(prefix, stage) or stage.parent.resolve() != prefix.resolve():
        raise ValueError("prepared Certas staging path escaped its H: cache")
    try:
        for name, data in payloads.items():
            (stage / name).write_bytes(data)
        (stage / "manifest.json").write_bytes(_canonical(generated))
        _verify_cache(stage, key)
        try:
            os.rename(stage, target)
        except FileExistsError:
            _verify_cache(target, key)
            shutil.rmtree(stage)
    except Exception:
        if stage.exists() and stage.parent.resolve() == prefix.resolve():
            shutil.rmtree(stage)
        raise
    return {"state": "ACQUIRED", "key": key,
            "manifest_sha256": generated["manifest_sha256"],
            "artifact_dir": str(target),
            "audio_bytes": artifact_total, "reference_count": 2,
            "reference_words": sum(r["reference_word_count"] for r in rows)}


def _selftest() -> int:
    # The model-free controls operate only on synthetic metadata and arrays.
    _set_single_thread_environment()
    import numpy as np
    fake_rows = [{"speaker_hash": "a"}, {"speaker_hash": "b"}]
    arrays = [np.asarray([0.8, 0.7, 0.6, 0.5], dtype=np.float32),
              np.asarray([0.9, 0.8], dtype=np.float32)]
    clean, info = _mix_arrays(fake_rows, arrays, np)
    ok = len(clean) == 3 and clean[2].ndim == 1
    ok = ok and float(np.max(np.abs(clean[2]))) <= MIX_PEAK_LIMIT + 1e-6
    ok = ok and info["overlap_samples"] == 2
    for bad_rows, bad_arrays in ((fake_rows[:1], arrays[:1]), (fake_rows, arrays[:1])):
        try:
            _mix_arrays(bad_rows, bad_arrays, np)
            ok = False
        except ValueError:
            pass
    try:
        _mix_arrays(fake_rows, [np.zeros(MAX_SOURCE_TOTAL_SAMPLES, np.float32), arrays[1]], np)
        ok = False
    except ValueError:
        pass
    # The manifest gate rejects changed bytes before audio libraries are imported.
    ok = ok and not _manifest_digest_matches(b"wrong manifest")
    for digest in (EXPECTED_RECORDS["a3e60c8a811db684"]["audio_sha256"],
                   EXPECTED_RECORDS["eceb99b403277625"]["reference_sha256"]):
        try:
            _require_digest(b"changed private input", digest, "synthetic")
            ok = False
        except ValueError:
            pass
    try:
        _require_wav_size(MAX_WAV_BYTES + 1)
        ok = False
    except ValueError:
        pass
    private = "synthetic private reference text"
    public_meta = {"schema": 1, "reference_sha256": _sha256(private.encode("utf-8"))}
    leaked_meta = {"sources": [{"reference_text": private}]}
    ok = (ok and not _contains_transcript_field(public_meta)
          and _contains_transcript_field(leaked_meta)
          and private not in _canonical(public_meta).decode("utf-8"))
    print("CERTAS_OVERLAP_SELFTEST %s controls=9" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true",
                        help="run model-free synthetic guard controls")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    result = prepare()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
