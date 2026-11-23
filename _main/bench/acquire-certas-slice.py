#!/usr/bin/env python3
"""Fetch at most two tiny, anonymized Certas Palavras references into H: cache."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


REPO = "nilc-nlp/certas_palavras"
SPLIT = "dev"
ROWS_API = "https://datasets-server.huggingface.co/rows"
MAX_ROWS = 100
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_CLIP_BYTES = 1024 * 1024
MAX_TOTAL_AUDIO_BYTES = 2 * 1024 * 1024
MAX_TEXT_BYTES = 16 * 1024
TIMEOUT_S = 12
USER_AGENT = "sotto-benchmark-slice/1.0"
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".agent-work" / "asr-cache" / "certas-palavras-small"
MANIFEST = CACHE / "manifest.json"


class Refusal(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_url(value: str) -> str:
    parsed = urlparse(value)
    match = re.fullmatch(
        r"/cached-assets/nilc-nlp/certas_palavras/--/([0-9a-f]{40})/--/"
        r"default/dev/(\d+)/audio/audio\.wav",
        parsed.path,
    )
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (parsed.scheme != "https" or parsed.hostname != "datasets-server.huggingface.co"
            or parsed.port is not None or parsed.username or parsed.password
            or parsed.fragment or match is None
            or set(query) != {"Expires", "Key-Pair-Id", "Signature"}
            or any(len(values) != 1 or not values[0] for values in query.values())):
        raise Refusal("dataset audio URL is outside the approved HTTPS source")
    return value


def _source_path_identity(value: str) -> tuple[str, int]:
    parsed = urlparse(_safe_url(value))
    match = re.fullmatch(
        r"/cached-assets/nilc-nlp/certas_palavras/--/([0-9a-f]{40})/--/"
        r"default/dev/(\d+)/audio/audio\.wav",
        parsed.path,
    )
    if match is None:
        raise Refusal("dataset audio URL identity is malformed")
    return match.group(1), int(match.group(2))


def _extension(data: bytes) -> str:
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return ".wav"
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF
                                    and data[1] & 0xE0 == 0xE0):
        return ".mp3"
    raise Refusal("dataset audio format is not WAV or MP3")


def _fetch_json() -> dict:
    params = urlencode({
        "dataset": REPO,
        "config": "default",
        "split": SPLIT,
        "offset": 0,
        "length": MAX_ROWS,
    })
    request = Request(ROWS_API + "?" + params, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT_S) as response:
        length = response.headers.get("Content-Length")
        if length is not None and int(length) > MAX_METADATA_BYTES:
            raise Refusal("dataset metadata response exceeds its 4 MiB budget")
        payload = response.read(MAX_METADATA_BYTES + 1)
    if len(payload) > MAX_METADATA_BYTES:
        raise Refusal("dataset metadata response exceeds its 4 MiB budget")
    try:
        result = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Refusal("dataset metadata response is not valid JSON") from exc
    if not isinstance(result, dict) or not isinstance(result.get("rows"), list):
        raise Refusal("dataset metadata response has no row list")
    if len(result["rows"]) > MAX_ROWS:
        raise Refusal("dataset metadata returned more than 100 rows")
    return result


def _select(payload: dict) -> list[dict]:
    selected = []
    used_speakers = set()
    dataset_revision = None
    for index, wrapped in enumerate(payload["rows"]):
        row = wrapped.get("row") if isinstance(wrapped, dict) else None
        if not isinstance(row, dict):
            continue
        speaker = str(row.get("speaker_name") or "").strip()
        text = str(row.get("text") or "").strip()
        if (not speaker or not text or len(text.encode("utf-8")) > MAX_TEXT_BYTES
                or len(text.split()) < 5):
            continue
        folded = speaker.casefold()
        if (folded.startswith(("musica", "música")) or "comercial" in folded
                or folded in used_speakers):
            continue
        audio_rows = row.get("audio")
        if (not isinstance(audio_rows, list) or not audio_rows
                or not isinstance(audio_rows[0], dict)
                or not isinstance(audio_rows[0].get("src"), str)):
            continue
        src = _safe_url(audio_rows[0]["src"])
        row_revision, source_row_index = _source_path_identity(src)
        row_index = int(wrapped.get("row_idx", index))
        if row_index != source_row_index:
            continue
        if dataset_revision is not None and row_revision != dataset_revision:
            raise Refusal("selected rows resolve to different dataset revisions")
        dataset_revision = row_revision
        speaker_hash = _sha256(speaker.encode("utf-8"))[:16]
        selected.append({
            "source_label": "speaker_%s" % ("ab"[len(selected)]),
            "speaker_hash": speaker_hash,
            "row_index": row_index,
            "dataset_revision": row_revision,
            "word_count": len(text.split()),
            "reference_text": text,
            "reference_sha256": _sha256(text.encode("utf-8")),
            "src": src,
        })
        used_speakers.add(folded)
        if len(selected) == 2:
            return selected
    raise Refusal("first 100 development rows did not contain two distinct speech sources")


def _download(selected: list[dict]) -> tuple[list[dict], int]:
    total = 0
    records = []
    for item in selected:
        head = Request(item["src"], method="HEAD", headers={"User-Agent": USER_AGENT})
        with urlopen(head, timeout=TIMEOUT_S) as response:
            size_header = response.headers.get("Content-Length")
            if response.status != 200 or size_header is None:
                raise Refusal("audio size could not be checked before download")
            expected_size = int(size_header)
        if not 0 < expected_size <= MAX_CLIP_BYTES:
            raise Refusal("selected clip exceeds the 1 MiB per-file ceiling")
        total += expected_size
        if total > MAX_TOTAL_AUDIO_BYTES:
            raise Refusal("selected clips exceed the 2 MiB total audio ceiling")
        request = Request(item["src"], headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=TIMEOUT_S) as response:
            if response.status != 200:
                raise Refusal("audio source did not return HTTP 200")
            data = response.read(MAX_CLIP_BYTES + 1)
        if len(data) != expected_size or len(data) > MAX_CLIP_BYTES:
            raise Refusal("downloaded clip size differs from its bounded HEAD result")
        suffix = _extension(data)
        audio_sha = _sha256(data)
        records.append({
            "source_label": item["source_label"],
            "speaker_hash": item["speaker_hash"],
            "row_index": item["row_index"],
            "dataset_revision": item["dataset_revision"],
            "reference_text": item["reference_text"],
            "reference_sha256": item["reference_sha256"],
            "reference_word_count": item["word_count"],
            "audio_file": item["source_label"] + "-" + audio_sha[:16] + suffix,
            "audio_sha256": audio_sha,
            "audio_bytes": len(data),
            "audio_format": suffix[1:],
            "audio_source": "datasets-server row audio",
        })
        item["data"] = data
    return records, total


def _cache_hit() -> bool:
    if CACHE.is_symlink() or not CACHE.is_dir() or MANIFEST.is_symlink() or not MANIFEST.is_file():
        return False
    try:
        if MANIFEST.stat().st_size > 64 * 1024:
            return False
        entries = list(CACHE.iterdir())
        if (len(entries) > 3 or any(item.is_symlink() or not item.is_file()
                                     for item in entries)):
            return False
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        records = manifest["records"]
        if (manifest.get("schema") != 1 or manifest.get("dataset") != REPO
                or manifest.get("split") != SPLIT
                or not re.fullmatch(r"[0-9a-f]{40}", manifest.get("dataset_revision", ""))
                or len(records) != 2):
            return False
        total = 0
        expected_files = {MANIFEST.name}
        speaker_hashes = set()
        for record in records:
            if record.get("dataset_revision") != manifest["dataset_revision"]:
                return False
            audio_name = record["audio_file"]
            if (not isinstance(audio_name, str) or Path(audio_name).name != audio_name
                    or not re.fullmatch(r"speaker_[ab]-[0-9a-f]{16}\.(?:wav|mp3)", audio_name)):
                return False
            expected_files.add(audio_name)
            if record.get("speaker_hash") in speaker_hashes:
                return False
            speaker_hashes.add(record.get("speaker_hash"))
            candidate = CACHE / audio_name
            if candidate.is_symlink():
                return False
            path = candidate.resolve()
            if path.parent != CACHE.resolve() or not path.is_file():
                return False
            data = path.read_bytes()
            if (len(data) != record["audio_bytes"]
                    or _sha256(data) != record["audio_sha256"]
                    or _sha256(record["reference_text"].encode("utf-8"))
                    != record["reference_sha256"]):
                return False
            total += len(data)
        return total <= MAX_TOTAL_AUDIO_BYTES and {item.name for item in entries} == expected_files
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def _write(records: list[dict], selected: list[dict]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    if CACHE.drive.upper() != "H:":
        raise Refusal("benchmark cache must remain on H:")
    if next(CACHE.iterdir(), None) is not None:
        raise Refusal("cache has partial or unexpected files; refusing to accumulate data")
    CACHE.resolve().relative_to(ROOT.resolve())
    audio_payloads = [item["data"] for item in selected]
    written = []
    try:
        for record, data in zip(records, audio_payloads):
            destination = CACHE / record["audio_file"]
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            written.append(destination)
        manifest = {
            "schema": 1,
            "dataset": REPO,
            "dataset_revision": selected[0]["dataset_revision"],
            "split": SPLIT,
            "source_page": "https://huggingface.co/datasets/nilc-nlp/certas_palavras",
            "source_paper": "https://aclanthology.org/2026.propor-1.81.pdf",
            "license": "CC BY-NC 4.0; local noncommercial evaluation with attribution",
            "attribution": "Araújo et al., Certas Palavras, PROPOR 2026; NILC/C4AI-USP",
            "redistribution": "Do not redistribute source audio or references.",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "selection": "first 100 dev rows; first two distinct non-music speakers; >=5 words",
            "limits": {"rows": MAX_ROWS, "clip_bytes": MAX_CLIP_BYTES,
                       "total_audio_bytes": MAX_TOTAL_AUDIO_BYTES},
            "records": records,
        }
        encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")) + "\n").encode("utf-8")
        temporary = MANIFEST.with_suffix(".json.tmp")
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, MANIFEST)
    except BaseException:
        for path in written:
            path.unlink(missing_ok=True)
        raise


def _selftest() -> None:
    if _extension(b"RIFF" + b"\0\0\0\0" + b"WAVE") != ".wav":
        raise AssertionError("WAV signature control failed")
    if _extension(b"ID3" + b"\0" * 8) != ".mp3":
        raise AssertionError("MP3 signature control failed")
    try:
        _extension(b"not-an-audio-file")
    except Refusal:
        pass
    else:
        raise AssertionError("unknown audio format was accepted")
    for bad in ("http://datasets-server.huggingface.co/assets/x",
                "https://huggingface.co/assets/x",
                "https://datasets-server.huggingface.co/rows?x=1",
                "https://datasets-server.huggingface.co/cached-assets/nilc-nlp/certas_palavras/--/"
                + "a" * 40 + "/--/default/dev/0/audio/audio.wav?Expires=1",
                "https://datasets-server.huggingface.co.evil/cached-assets/nilc-nlp/certas_palavras/--/"
                + "a" * 40 + "/--/default/dev/0/audio/audio.wav?Expires=1&Key-Pair-Id=2&Signature=3"):
        try:
            _safe_url(bad)
        except Refusal:
            continue
        raise AssertionError("unapproved source URL was accepted")
    revision = "a" * 40
    def row_url(row_index):
        return ("https://datasets-server.huggingface.co/cached-assets/" + REPO
                + "/--/" + revision + "/--/default/dev/%d/audio/audio.wav"
                "?Expires=1&Key-Pair-Id=2&Signature=3") % row_index

    payload = {"rows": [
        {"row_idx": 4, "row": {"speaker_name": "source one", "text": "one two three four five", "audio": [{"src": row_url(4)}]}},
        {"row_idx": 5, "row": {"speaker_name": "source one", "text": "duplicate speaker row six seven", "audio": [{"src": row_url(5)}]}},
        {"row_idx": 6, "row": {"speaker_name": "source two", "text": "six seven eight nine ten", "audio": [{"src": row_url(6)}]}},
    ]}
    selected = _select(payload)
    if (len(selected) != 2 or selected[0]["row_index"] != 4
            or selected[1]["row_index"] != 6
            or any(item["dataset_revision"] != revision for item in selected)
            or selected[0]["speaker_hash"] == selected[1]["speaker_hash"]
            or any("speaker_name" in item for item in selected)):
        raise AssertionError("selection did not produce two distinct anonymous references")
    try:
        _select({"rows": payload["rows"][:2]})
    except Refusal:
        pass
    else:
        raise AssertionError("duplicate-speaker-only cohort was accepted")
    mixed = {"rows": [payload["rows"][0], dict(payload["rows"][2], row={
        **payload["rows"][2]["row"], "audio": [{"src": row_url(6).replace(revision, "b" * 40)}]})]}
    try:
        _select(mixed)
    except Refusal:
        pass
    else:
        raise AssertionError("mixed dataset revisions were accepted")
    print("SELFTEST PASS: source allowlist, format checks, two distinct anonymous references")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if CACHE.drive.upper() != "H:":
        raise Refusal("benchmark cache must remain on H:")
    if _cache_hit():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        print("CACHE HIT records=2 audio_bytes=%d reference_words=%d manifest_sha256=%s"
              % (sum(row["audio_bytes"] for row in manifest["records"]),
                 sum(row["reference_word_count"] for row in manifest["records"]),
                 _sha256(MANIFEST.read_bytes())))
        return 0
    payload = _fetch_json()
    selected = _select(payload)
    records, audio_bytes = _download(selected)
    _write(records, selected)
    print("ACQUIRED records=2 audio_bytes=%d reference_words=%d manifest_sha256=%s"
          % (audio_bytes, sum(row["reference_word_count"] for row in records),
             _sha256(MANIFEST.read_bytes())))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refusal as exc:
        print("REFUSED: %s" % str(exc), file=sys.stderr)
        sys.exit(2)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        print("REFUSED: %s" % type(exc).__name__, file=sys.stderr)
        sys.exit(2)
