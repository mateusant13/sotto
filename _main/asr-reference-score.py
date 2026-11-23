#!/usr/bin/env python3
"""Score ASR JSONL hypotheses against a pinned reference manifest.

Only aggregate metrics and hashes are printed; transcript text is never emitted.
Each JSONL row requires ``id``, ``text`` and the consumed WAV's SHA-256. Timing
is either present for every sample (``audio_s`` and ``inference_s``) or omitted
for every sample. Unicode punctuation is normalized to spaces for WER/CER;
CER then excludes whitespace. Accents remain significant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
import unicodedata
import wave
from pathlib import Path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _canonical(text: str) -> str:
    value = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", text)).casefold()
    # Convert all Unicode punctuation to a separator, matching common corpus WER
    # normalization while retaining accents and letters from non-Latin scripts.
    value = "".join(" " if unicodedata.category(char).startswith("P") else char
                    for char in value)
    return " ".join(value.split())


def _words(text: str) -> list[str]:
    return _canonical(text).split()


def _chars(text: str) -> list[str]:
    return [char for char in _canonical(text) if not char.isspace()]


def _distance(left: list[str], right: list[str]) -> int:
    """Levenshtein distance using O(min(n,m)) memory."""
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def _percentile(values: list[float], q: float):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return round(ordered[lo], 6)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo), 6)


def _read_hypotheses(path: Path):
    raw = path.read_bytes()
    rows = {}
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("hypothesis row must be an object")
        sample_id = str(row.get("id", ""))
        if not sample_id or sample_id in rows:
            raise ValueError("invalid or duplicate hypothesis id")
        if not isinstance(row.get("text"), str):
            raise ValueError("hypothesis text is missing")
        rows[sample_id] = row
    return rows, raw


def _wave_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        rate = audio.getframerate()
        if rate <= 0:
            raise ValueError("invalid reference WAV rate")
        return audio.getnframes() / rate


def score(manifest_path: Path, hypotheses_path: Path, model: str,
          expected_manifest_sha256: str):
    manifest_raw = manifest_path.read_bytes()
    manifest_sha256 = _sha256(manifest_raw)
    if manifest_sha256 != expected_manifest_sha256:
        raise ValueError("reference manifest does not match the pinned cohort hash")
    manifest = json.loads(manifest_raw.decode("utf-8"))
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("manifest has no reference records")
    transcript_hash = str(manifest.get("transcript_sha256", ""))
    if len(transcript_hash) != 64:
        raise ValueError("manifest transcript hash is invalid")
    transcript_file = manifest_path.with_name(transcript_hash + ".trans.txt")
    if not transcript_file.is_file():
        raise ValueError("pinned reference transcript sidecar is missing")
    actual_transcript_hash, _ = _sha256_file(transcript_file)
    if actual_transcript_hash != transcript_hash:
        raise ValueError("reference transcript sidecar hash mismatch")

    hypotheses, hypothesis_raw = _read_hypotheses(hypotheses_path)
    refs = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("manifest reference row must be an object")
        sample_id = str(record.get("id", ""))
        if not sample_id or sample_id in refs:
            raise ValueError("invalid or duplicate reference id")
        refs[sample_id] = record
    if hypotheses.keys() != refs.keys():
        raise ValueError("hypothesis/reference cohort mismatch")

    ref_words = hyp_words = word_edits = ref_chars = char_edits = 0
    audio_seconds = inference_seconds = 0.0
    timings = []
    timing_presence = []
    for sample_id, record in refs.items():
        reference = record.get("reference")
        if not isinstance(reference, str):
            raise ValueError("reference text is missing")
        if _sha256(reference.encode("utf-8")) != record.get("reference_sha256"):
            raise ValueError("reference text hash mismatch")

        audio_hash = str(record.get("audio_sha256", ""))
        audio_bytes = int(record.get("audio_bytes", 0))
        if len(audio_hash) != 64 or audio_bytes <= 0:
            raise ValueError("reference audio identity is invalid")
        audio_path = manifest_path.with_name(audio_hash + ".wav")
        if not audio_path.is_file():
            raise ValueError("reference audio file is missing")
        actual_audio_hash, actual_audio_bytes = _sha256_file(audio_path)
        if actual_audio_hash != audio_hash or actual_audio_bytes != audio_bytes:
            raise ValueError("reference audio bytes do not match the pinned manifest")

        hyp = hypotheses[sample_id]
        if hyp.get("audio_sha256") != actual_audio_hash:
            raise ValueError("hypothesis audio identity mismatch")
        expected_words, actual_words = _words(reference), _words(hyp["text"])
        ref_words += len(expected_words)
        hyp_words += len(actual_words)
        word_edits += _distance(expected_words, actual_words)
        expected_chars, actual_chars = _chars(reference), _chars(hyp["text"])
        ref_chars += len(expected_chars)
        char_edits += _distance(expected_chars, actual_chars)

        has_audio_s = "audio_s" in hyp
        has_inference_s = "inference_s" in hyp
        timing_presence.append(has_audio_s and has_inference_s)
        if has_audio_s != has_inference_s:
            raise ValueError("timing fields must be supplied as a pair")
        if has_audio_s:
            try:
                audio_s = float(hyp["audio_s"])
                inference_s = float(hyp["inference_s"])
            except (TypeError, ValueError, OverflowError):
                raise ValueError("timing fields must be finite numbers") from None
            actual_audio_s = _wave_seconds(audio_path)
            if (not math.isfinite(audio_s) or not math.isfinite(inference_s)
                    or audio_s <= 0 or inference_s < 0
                    or abs(audio_s - actual_audio_s) > 0.01):
                raise ValueError("timing fields are invalid or disagree with WAV duration")
            audio_seconds += audio_s
            inference_seconds += inference_s
            timings.append(inference_s)  # Zero is a valid measured latency.
    if any(timing_presence) and not all(timing_presence):
        raise ValueError("timing fields must cover every cohort sample")

    timed = bool(timing_presence and all(timing_presence))
    hypothesis_sha256 = _sha256(hypothesis_raw)
    return {
        "model": model,
        "dataset": manifest.get("dataset"),
        "manifest_sha256": manifest_sha256,
        "hypotheses_sha256": hypothesis_sha256,
        "cache_key": _sha256((model + "\0" + manifest_sha256 + "\0" +
                               hypothesis_sha256).encode("utf-8")),
        "samples": len(records),
        "coverage": "complete",
        "normalization": "NFKC+NFC casefold; Unicode punctuation to spaces; CER excludes whitespace",
        "reference_words": ref_words,
        "hypothesis_words": hyp_words,
        "word_edits": word_edits,
        "wer": round(word_edits / ref_words, 8) if ref_words else None,
        "reference_chars_no_whitespace": ref_chars,
        "char_edits": char_edits,
        "cer_no_whitespace": round(char_edits / ref_chars, 8) if ref_chars else None,
        "timing_samples": len(timings),
        "timing_complete": timed,
        "audio_seconds": round(audio_seconds, 6) if timed else None,
        "inference_seconds": round(inference_seconds, 6) if timed else None,
        "rtf": round(inference_seconds / audio_seconds, 8)
        if timed and audio_seconds else None,
        "inference_s_p50": _percentile(timings, 0.50),
        "inference_s_p95": _percentile(timings, 0.95),
        "inference_s_p99": _percentile(timings, 0.99),
    }


def selftest():
    # End-to-end fixture: actual tiny WAV bytes, manifest, transcript sidecar,
    # hash-bound hypotheses, timing edge cases, and fail-closed mutants.
    with tempfile.TemporaryDirectory(prefix="asr-score-selftest-",
                                     dir=Path(__file__).parent) as temp_name:
        root = Path(temp_name)
        records = []
        for index, (sample_id, reference) in enumerate((("a", "Olá, mundo!"),
                                                        ("b", "não sei"))):
            audio = root / (sample_id + ".wav")
            with wave.open(str(audio), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(bytes((index, 0)) * 160)
            audio_hash, audio_bytes = _sha256_file(audio)
            # Production cache filenames are content addressed.
            audio.rename(root / (audio_hash + ".wav"))
            records.append({"id": sample_id, "reference": reference,
                            "reference_sha256": _sha256(reference.encode("utf-8")),
                            "audio_sha256": audio_hash, "audio_bytes": audio_bytes})
        transcript_bytes = b"a\tref\nb\tref\n"
        transcript_hash = _sha256(transcript_bytes)
        (root / (transcript_hash + ".trans.txt")).write_bytes(transcript_bytes)
        manifest = {"dataset": "selftest", "transcript_sha256": transcript_hash,
                    "records": records}
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        manifest_hash, _ = _sha256_file(manifest_path)
        hypotheses_path = root / "hypotheses.jsonl"
        rows = [
            {"id": "a", "text": "“Olá” mundo", "audio_sha256": records[0]["audio_sha256"],
             "audio_s": 0.01, "inference_s": 0.0},
            {"id": "b", "text": "não muito sei", "audio_sha256": records[1]["audio_sha256"],
             "audio_s": 0.01, "inference_s": 1.0},
        ]
        hypotheses_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                                     for row in rows), encoding="utf-8")
        result = score(manifest_path, hypotheses_path, "fixture", manifest_hash)
        assert result["samples"] == 2 and result["coverage"] == "complete"
        assert result["wer"] == round(1 / 4, 8)  # one insertion in four reference words
        assert result["word_edits"] == 1 and result["char_edits"] > 0
        assert result["timing_samples"] == 2 and result["inference_s_p50"] == 0.5
        assert "Olá" not in json.dumps(result) and "muito" not in json.dumps(result)

        def must_refuse(mutant_manifest=manifest_path, mutant_hyp= None,
                        expected=manifest_hash):
            try:
                score(mutant_manifest, mutant_hyp or hypotheses_path, "fixture", expected)
            except (OSError, ValueError, KeyError):
                return
            raise AssertionError("adverse scorer input was accepted")

        (root / (transcript_hash + ".trans.txt")).unlink()
        must_refuse()
        (root / (transcript_hash + ".trans.txt")).write_bytes(transcript_bytes)

        reduced = dict(manifest)
        reduced["records"] = records[:1]
        reduced_path = root / "reduced.json"
        reduced_path.write_text(json.dumps(reduced), encoding="utf-8")
        must_refuse(mutant_manifest=reduced_path)

        partial_path = root / "partial.jsonl"
        partial_rows = [dict(row) for row in rows]
        del partial_rows[1]["inference_s"]
        partial_path.write_text("".join(json.dumps(row) + "\n" for row in partial_rows),
                                encoding="utf-8")
        must_refuse(mutant_hyp=partial_path)

        malformed_path = root / "malformed.jsonl"
        malformed_rows = [dict(row) for row in rows]
        malformed_rows[1]["inference_s"] = "TRANSCRIPT_SENTINEL"
        malformed_path.write_text("".join(json.dumps(row) + "\n" for row in malformed_rows),
                                   encoding="utf-8")
        try:
            score(manifest_path, malformed_path, "fixture", manifest_hash)
        except ValueError as exc:
            assert "TRANSCRIPT_SENTINEL" not in str(exc)
        else:
            raise AssertionError("malformed timing input was accepted")

        zero_timing_path = root / "zero-timing.jsonl"
        zero_rows = [dict(row) for row in rows]
        zero_rows[1]["inference_s"] = 0.0
        zero_timing_path.write_text("".join(json.dumps(row) + "\n" for row in zero_rows),
                                    encoding="utf-8")
        zero_result = score(manifest_path, zero_timing_path, "fixture", manifest_hash)
        assert zero_result["timing_samples"] == 2 and zero_result["inference_s_p50"] == 0.0

    print("SELFTEST PASS (8/8; cohort/hash/timing/punctuation controls; transcript output disabled)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--hypotheses", type=Path)
    parser.add_argument("--model", default="unspecified")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if not args.manifest or not args.hypotheses or not args.expected_manifest_sha256:
        parser.error("--manifest, --expected-manifest-sha256, and --hypotheses are required")
    try:
        report = score(args.manifest, args.hypotheses, args.model,
                       args.expected_manifest_sha256)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        # Never echo malformed JSON values, file content, or transcript text.
        print("REFUSED: invalid benchmark input or content hash mismatch", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
