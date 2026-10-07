#!/usr/bin/env python3
"""Sotto hourly title/summary for a window of the canonical transcript, on ORT-GenAI.

Reads a window of the owner's transcript (``history/<YYYY-MM-DD>/<HH>.md``), asks a local
Qwen model for one title + a 3-sentence summary, and prints exactly **one JSON line** on
stdout.  Everything else -- progress, timings, the language census, warnings -- goes to
stderr, so stdout stays a clean one-line contract (same grammar as ``worker/redux_batch.py``).

    {"type":"summary","hour":"2026-10-06T16:00:00-03:00","title":"...","summary":"...",
     "tokens_in":1234,"tokens_out":95,"model":"qwen3.5-2b-int4","language":"pt",
     "cached":false,"wall_s":42.1, ...}

The design is ``docs/qwen-hourly-plan.md`` (§5.1-§5.6); this file implements it.  The
numbers that matter are the plan's: **MIN 900 tokens** (below that there is not enough
content for a title plus a summary, so the run REFUSES and does not touch the model).

**Windowing, and why it is no longer the plan's 3,072.** The plan's CPU ceiling for one
request (§4.3) was derived from the **fp32** matmul throughput (47.95 GFLOPS).  The int4
path does not run that kernel -- measured on this box, ``MatMulNBits`` int4 on
``CPUExecutionProvider`` returns 557-617 GFLOP/s, ~12x more -- so the whole window goes into
**ONE request by default**, and the only hard ceiling is the model's own ``context_length``
read out of ``genai_config.json`` (the plan could not know it: its §4.3 Term 1 is UNKNOWN).
``--max-request-tokens N`` re-imposes a cap on demand, and only then is the window folded in
order (§5.2's documented fallback -- never a stitch of independent per-chunk summaries).
The plan's 3,072 is still reported as ``plan_reference_max_tokens`` so the correction is
visible in every result rather than quietly forgotten.

Usage
-----
    python worker/qwen_summary.py --hour 2026-10-06T16 [--json]
    python worker/qwen_summary.py --from 2026-10-06T16:00 --to 2026-10-06T16:40
    python worker/qwen_summary.py --now                 # the manual "use it now" window
    python worker/qwen_summary.py --hour ... --dry-run  # no model: window, tokens, chunks
    python worker/qwen_summary.py --hour ... --model-dir  worker/models/<other>

Flags that exist for measurement and for the failure arms: ``--dry-run`` (never loads the
model), ``--force`` (ignore the cache, still write it), ``--no-cache`` (ignore AND do not
write), ``--max-request-tokens``, ``--max-seconds``, ``--priority``, ``--trigger``.
``--model-dir`` picks the export, so an A/B of two candidate models on the SAME hour is a
one-flag change (use ``--force``: the cache key is hour+hash+partial and does NOT include
the model).

Contract details another lane parses
------------------------------------
* Success                -> ``{"type":"summary", ...}``          exit 0
* Refused below MIN      -> ``{"type":"summary-unavailable","reason":"below-min", ...}`` exit 2
* Model dir absent       -> ``{"type":"summary-unavailable","reason":"model-missing", ...}`` exit 3
* Generation failed/empty-> ``{"type":"summary-unavailable","reason":"generation-failed"|"empty-generation", ...}`` exit 3
* Bad arguments/window   -> nothing on stdout, message on stderr, exit 1

Every ``summary-unavailable`` line carries ``"downloads_attempted": false`` -- this file
never downloads anything, ever (the plan's §6.3: the acquisition path is not reachable from
the reading/generating path).  A missing model is reported, never fetched.

Cache (plan §5.3): a sibling ``history/<YYYY-MM-DD>/<HH>.summary.json``, keyed by
``hour`` + ``content_hash`` + ``partial``.  ``content_hash`` is a sha256 over the text that
was actually FED to the model (the recipe is stored in the file as
``content_hash_recipe``).  A cached record satisfies a request only when all three match,
so a ``partial:true`` record can never answer a full-hour request.

Language (plan §5.4): decided per window by a script census over the window's own text,
not by a config key -- this box's archive genuinely contains Devanagari emitted for English
audio (``history/2026-10-06/19.md``), so the census re-derives the answer per hour and
falls back to Portuguese when it is ambiguous.  The decision and its evidence are stored.

Hard rules this file obeys: no audio device is ever opened, no window ever appears (this
module prints; it never spawns a shell), and the process never writes the transcript -- the
only file it can create is the summary sidecar.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HISTORY = ROOT / "history"

# The model is a FLAG, never a path baked into the logic: the tier is still being chosen
# (the owner wants the smallest sufficient model), and an A/B on one real hour has to be a
# one-line change.  Precedence: --model-dir  >  $SOTTO_QWEN_MODEL_DIR  >  this constant.
DEFAULT_MODEL_DIR = HERE / "models" / "qwen3.5-2b-int4"

# ---- the plan's budgets, and the correction measured after the plan was written --------
# MIN is a property of the TEXT (not of the machine): below it there is not enough content
# for a title plus a summary.  Unchanged.
MIN_TOKENS = 900
# The plan's CPU-tier ceiling for ONE request (§4.3) was derived from the **fp32** matmul
# throughput (47.95 GFLOPS).  The int4 path does not run that kernel: measured on this box,
# MatMulNBits int4 on CPUExecutionProvider returns 557-617 GFLOP/s, ~12x more, so the plan's
# 3,072-token ceiling (and its "~5 min per hour") is almost certainly far too pessimistic.
# It is therefore reported as a REFERENCE ONLY and is NOT the window size: the whole window
# goes into ONE request by default, and the only hard ceiling is the model's own context
# length read out of its genai_config.json.  --max-request-tokens re-imposes a cap on demand.
PLAN_CPU_MAX_TOKENS = 3072
# Two greedy calls, zero retries (docs/harness-title-practice.md §5): the TITLE is written
# from the window's first characters only, the SUMMARY over the whole window.  A single
# combined prompt was the earlier design and is gone: the title call's input is deliberately
# small and its output deliberately short, which is also what bounds the loop risk.
TITLE_MAX_NEW_TOKENS = 48     # the title call's hard output ceiling
SUMMARY_MAX_NEW_TOKENS = 256  # the summary call's hard output ceiling
TITLE_INPUT_CHARS = 1200      # the title sees only the first 1200 characters of the window
TITLE_MAX_WORDS = 12          # above this the answer is REJECTED (answer-shaped), never cut down
TITLE_MAX_CHARS = 80
SUMMARY_MAX_WORDS = 90
SUMMARY_MAX_SENTENCES = 6
RUNNING_RESERVE = 260         # the fold's running summary, reserved out of the request budget

SCHEMA = 1
ENGINE = "onnxruntime-genai 0.17.1"

TAG_RE = re.compile(r"<!--.*?-->")
LINE_RE = re.compile(r"^-\s*\[(\d{1,2}):(\d{2}):(\d{2})\]\s*(.*?)\s*$")
THINK_RE = re.compile(r"<think\b[^>]*>.*?(?:</think\s*>|</｜end▁of▁thinking｜>)", re.S | re.I)
# Qwen spells the same two tokens two ways depending on how the template is written: the plain
# HTML-ish pair (``<think>...</think>``) and the full-width form the tokenizer displays
# (``<｜end▁of▁thinking｜>``).  Both are handled -- the first measured run is what found the gap.
THINK_TAIL_RE = re.compile(r"(?:</think\s*>|</｜end▁of▁thinking｜>|<｜end▁of▁thinking｜>)", re.I)
THINK_OPEN_RE = re.compile(r"<think\b[^>]*>", re.I)

# ---------------------------------------------------------------------------
# stdout/stderr plumbing
# ---------------------------------------------------------------------------


def _utf8_streams() -> None:
    """Pin stdout/stderr to UTF-8, whatever the console code page is.

    Same convention as ``sotto_worker.py`` and ``worker/redux_batch.py``.  It matters more
    here than there: the transcript is Portuguese/English/Devanagari and the model's own
    summary must reach the panel byte-identical, so a redirect must not re-encode it into
    the host locale.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (ValueError, OSError):
                pass


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _emit(line: dict) -> None:
    """The one JSON line on stdout.  ``ensure_ascii=False`` keeps it UTF-8 readable."""
    print(json.dumps(line, ensure_ascii=False, default=str), flush=True)


# ---------------------------------------------------------------------------
# process facts (peak RSS, priority) -- measured, never assumed
# ---------------------------------------------------------------------------


def process_cpu_s() -> float | None:
    """This process' cumulative CPU time (user + kernel), in seconds.

    The instrument that turns an unexplained wall-clock number into a measured one: a run whose
    WALL time greatly exceeds its CPU time was not computing -- it was suspended, preempted or
    blocked.  That distinction matters on this box, where lanes run memory-reclaim and census
    tooling that has already suspended one of these runs mid-generation (measured: 56 of 56
    threads ``Wait, Suspended``, CPU frozen at 146.4 s while the wall clock kept going).
    """
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
        kernel32.GetProcessTimes.restype = ctypes.c_int

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                        ("dwHighDateTime", ctypes.c_ulong)]

        creation, exit_, kernel, user = (FILETIME() for _ in range(4))
        ok = kernel32.GetProcessTimes(kernel32.GetCurrentProcess(), ctypes.byref(creation),
                                      ctypes.byref(exit_), ctypes.byref(kernel),
                                      ctypes.byref(user))
        if not ok:
            return None
        kern = (kernel.dwHighDateTime << 32) | kernel.dwLowDateTime
        usr = (user.dwHighDateTime << 32) | user.dwLowDateTime
        return round((kern + usr) / 1e7, 3)
    except Exception:  # noqa: BLE001
        return None


class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def peak_rss_mb() -> float | None:
    """This process' PEAK working set, in MiB, from the OS.

    The plan asks for peak RSS as a measured output, and on Windows the honest source is
    ``GetProcessMemoryInfo``.  Returns ``None`` (and the caller reports ``null``) rather
    than a guess if the call is unavailable -- a fabricated memory figure is the failure
    mode this repo keeps paying for.

    ``argtypes``/``restype`` are set EXPLICITLY, and that is not decoration: with ctypes'
    default ``c_int`` return type, ``GetCurrentProcess()`` arrives as ``-1`` instead of the
    pseudo-handle ``(HANDLE)-1``, the process handle is then truncated to 32 bits when it is
    passed back, and the call fails silently.  Measured: this instrument returned ``None`` on
    every run until it was given the right types.
    """
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        counters = _PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(),
                                        ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        return round(counters.PeakWorkingSetSize / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001 - a measurement must never take the run down
        return None


_PRIORITY_CLASSES = {"normal": 0x20, "below-normal": 0x4000, "idle": 0x40}


def set_priority(name: str) -> bool:
    """``SetPriorityClass`` on this process.  Returns whether it took.

    Plan §5.6: the hourly pass must not starve the live ASR worker, so the default here is
    ``below-normal``.  It is a real OS call, and the JSON records whether it succeeded --
    a priority claim that silently did nothing would make every timing a lie.  Same
    explicit-types trap as ``peak_rss_mb``: with the default ``c_int`` restype the handle is
    truncated and the call returns false.
    """
    flags = _PRIORITY_CLASSES.get(name)
    if flags is None:
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel32.SetPriorityClass.restype = ctypes.c_int
        return bool(kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), flags))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# the archive: reading a window
# ---------------------------------------------------------------------------


def parse_archive_file(path: Path, day: tuple[int, int, int]) -> list[tuple[datetime, str]]:
    """Return ``[(datetime, text), ...]`` for one ``<HH>.md`` file, sorted by time.

    The line grammar is fixed by the store (``app/electron/history-store.js``) and every
    one of the 2,072 archived lines matches it:

        - [HH:MM:SS] the closed line's text <!-- route=final reason=... -->
    """
    entries: list[tuple[datetime, str]] = []
    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entries
    for raw in raw_text.splitlines():
        if not raw.startswith("-"):
            continue
        body = TAG_RE.sub("", raw).strip()
        hit = LINE_RE.match(body)
        if not hit:
            continue
        hh, mm, ss = int(hit.group(1)), int(hit.group(2)), int(hit.group(3))
        text = hit.group(4)
        if not text:
            continue
        try:
            entries.append((datetime(day[0], day[1], day[2], hh, mm, ss), text))
        except ValueError:
            continue
    entries.sort(key=lambda e: e[0])
    return entries


def _day_and_hour(path: Path) -> tuple[tuple[int, int, int], int] | None:
    try:
        year, month, day = (int(x) for x in path.parent.name.split("-"))
        hour = int(path.stem)
    except (ValueError, IndexError):
        return None
    return (year, month, day), hour


def read_window(from_dt: datetime, to_dt: datetime) -> tuple[list[tuple[datetime, str]], list[str]]:
    """All closed lines in ``[from_dt, to_dt)``, across the hour files it touches.

    Returns ``(entries, files_read)``.  Only files whose hour overlaps the window are read,
    so a 40-minute manual window touches one file and an hour touches one file.
    """
    entries: list[tuple[datetime, str]] = []
    files: list[str] = []
    cursor = from_dt.replace(minute=0, second=0, microsecond=0)
    last = (to_dt - timedelta(seconds=1)).replace(minute=0, second=0, microsecond=0) \
        if to_dt > from_dt else from_dt.replace(minute=0, second=0, microsecond=0)
    guard = 0
    while cursor <= last and guard < 48:
        guard += 1
        path = HISTORY / cursor.strftime("%Y-%m-%d") / f"{cursor.hour:02d}.md"
        if path.is_file():
            files.append(str(path.relative_to(ROOT)).replace("\\", "/"))
            for dt, text in parse_archive_file(path, (cursor.year, cursor.month, cursor.day)):
                if from_dt <= dt < to_dt:
                    entries.append((dt, text))
        cursor += timedelta(hours=1)
    entries.sort(key=lambda e: e[0])
    return entries, files


def collapse_runs(entries: list[tuple[datetime, str]]) -> list[str]:
    """Collapse the worker's CUMULATIVE hypotheses into readable lines.

    The archive is not a transcript of distinct sentences: the second pass re-emits the
    same hypothesis with a longer tail (measured on ``history/2026-10-06/16.md``: 560 lines
    carry far fewer utterances), so feeding it raw spends the context budget on repeats.
    The dedup predicate is the token-rate probe's own
    (``_main/_qwen-token-rate-probe.py``: a line continues the run when it starts with the
    first half -- at least 12 characters -- of the previous kept line), but instead of
    scoring only the novel *suffix* (which yields fragments like "ight open mo del") this
    keeps the LAST and therefore LONGEST text of each run.  Same deduplication, readable
    prose, still one deterministic rule.
    """
    kept: list[str] = []
    for _dt, text in entries:
        if kept:
            prev = kept[-1]
            if text == prev or text.startswith(prev[: max(12, len(prev) // 2)]):
                kept[-1] = text if len(text) >= len(prev) else prev
                continue
        kept.append(text)
    return kept


def novel_dedup_tokens(texts: list[str], count) -> int:
    """The probe's own dedup count, kept for comparability with the plan's 6,634/hour.

    ``count`` is a ``str -> int`` token counter.  Reported as a diagnostic so the plan's
    MIN/MAX arithmetic (which was measured on THIS number) can be compared with the token
    count our prompt actually feeds (``collapse_runs``' text).
    """
    kept: list[str] = []
    total = 0
    for text in texts:
        if kept and (text == kept[-1] or text.startswith(kept[-1][: max(12, len(kept[-1]) // 2)])):
            prev = kept[-1]
            novel = text[len(prev):] if text.startswith(prev) else text
            if len(novel.strip()) < 4:
                continue
            total += count(novel)
            kept[-1] = text
        else:
            total += count(text)
            kept.append(text)
    return total


# ---------------------------------------------------------------------------
# token counting -- exact when it can be, and it says which it was
# ---------------------------------------------------------------------------


class Tokenizer:
    """A token counter/encoder that reports its own provenance.

    Order of preference, best first:

    1. ``onnxruntime_genai.Tokenizer`` on the model directory or on ``tokenizer.json`` --
       the model's OWN tokenizer, constructed without loading a single weight, which is
       what lets the below-MIN arm refuse *without* touching the model (plan §4.2's gate is
       a token count, so the count must be exact before the model is loaded).
    2. ``tokenizers.Tokenizer.from_file(tokenizer.json)`` -- the same file, same merges.
    3. A script-aware character heuristic, loudly labelled ``heuristic``.

    ``kind`` is one of ``genai``/``tokenizers``/``heuristic`` and travels in the JSON, so
    no reader has to guess how ``tokens_in`` was obtained.
    """

    def __init__(self, model_dir: Path | None):
        self.kind = "heuristic"
        self.source: str | None = None
        self._enc = None
        self._dec = None
        self._og = None
        if model_dir is not None:
            self._try_genai(model_dir)
            if self._enc is None:
                self._try_tokenizers(model_dir)

    def _try_genai(self, model_dir: Path) -> None:
        candidates = [str(model_dir), str(model_dir / "tokenizer.json")]
        for cand in candidates:
            if not Path(cand).exists():
                continue
            try:
                import onnxruntime_genai as og

                tok = og.Tokenizer(cand)
                # Prove it encodes before trusting it (a constructor that succeeds is not
                # evidence -- this repo's own rule: perform the capability).
                probe = tok.encode("hello, mundo")
                if probe is None or len(probe) == 0:
                    continue
                self._og = tok
                self.kind, self.source = "genai", cand
                return
            except Exception as exc:  # noqa: BLE001
                _log(f"tokenizer: onnxruntime_genai path failed for {cand} ({type(exc).__name__})")

    def _try_tokenizers(self, model_dir: Path) -> None:
        path = model_dir / "tokenizer.json"
        if not path.is_file():
            return
        try:
            from tokenizers import Tokenizer as FastTokenizer

            tok = FastTokenizer.from_file(str(path))
            if not tok.encode("hello, mundo").ids:
                return
            self._enc = lambda text: tok.encode(text, add_special_tokens=False).ids
            self._dec = lambda ids: tok.decode(list(ids), skip_special_tokens=True)
            self.kind, self.source = "tokenizers", str(path)
        except Exception as exc:  # noqa: BLE001
            _log(f"tokenizer: tokenizers path failed ({type(exc).__name__}: {exc})")

    def encode(self, text: str) -> list[int]:
        if self.kind == "genai":
            return [int(x) for x in self._og.encode(text)]
        if self._enc is not None:
            return [int(x) for x in self._enc(text)]
        raise RuntimeError("heuristic tokenizer cannot encode")

    def decode(self, ids) -> str:
        if self.kind == "genai":
            import numpy as np

            return self._og.decode(np.asarray(ids, dtype=np.int32))
        if self._dec is not None:
            return self._dec(ids)
        raise RuntimeError("heuristic tokenizer cannot decode")

    def count(self, text: str) -> int:
        """Token count.  Character heuristic only when nothing exact is available."""
        if self.kind == "heuristic":
            return char_tokens(text)
        try:
            return len(self.encode(text))
        except Exception:  # noqa: BLE001
            return char_tokens(text)


def char_tokens(text: str) -> int:
    """Script-aware character heuristic (the probe's own, kept identical).

    Latin ~4.0 chars/token for Qwen's BPE; Devanagari/CJK/Hangul ~1 token/char because they
    are genuinely denser -- and this corpus really does contain them.
    """
    dense = 0
    for ch in text:
        o = ord(ch)
        if 0x0900 <= o <= 0x097F:      # Devanagari
            dense += 1
        elif 0x3000 <= o <= 0x9FFF:    # CJK / kana
            dense += 1
        elif 0xAC00 <= o <= 0xD7AF:    # Hangul
            dense += 1
    latin_chars = len(text) - dense
    return dense + max(0, round(latin_chars / 4.0))


# ---------------------------------------------------------------------------
# language census (plan §5.4)
# ---------------------------------------------------------------------------

_PT_STOPWORDS = frozenset(
    """a o as os um uma uns umas de do da dos das em no na nos nas por para com sem que
    se nao não e eh é mas como mais ja já foi ser estar esta está estou sao são tem tinha
    vai vou voce você ele ela isso isto aquilo aqui ali entao então tambem também muito
    pouco tudo nada bem mal meu minha seu sua nosso nossa ele eu tu nos nós eles elas
    porque quando onde qual quem der pau cara gente agora ainda depois antes pode posso
    quer quero fazer ta tá tava la lá so só bem""".split()
)
_EN_STOPWORDS = frozenset(
    """a an the and or but if then than that this these those is are was were be been being
    am do does did doing have has had having i you he she it we they me him her us them my
    your his its our their to of in on at by for with from about into over after before
    what which who whom when where why how not no yes can could should would will just
    there here very much more most some any all one two get got go going like really""".split()
)
_PT_DIACRITICS = frozenset("ãõçêôáéíóúâàªº")
_SCRIPT_RANGES = (
    ("latin", 0x0041, 0x007A),
    ("devanagari", 0x0900, 0x097F),
    ("cjk_kana", 0x3000, 0x9FFF),
    ("hangul", 0xAC00, 0xD7AF),
    ("cyrillic", 0x0400, 0x04FF),
    ("arabic", 0x0600, 0x06FF),
)


def language_census(text: str) -> tuple[str, dict]:
    """Decide the reply language from the window's own text; fall back to Portuguese.

    The rule, in order:

    1. Census the scripts by character.  A window dominated by a NON-Latin script is the
       measured Devanagari-for-English-audio case: the script cannot be trusted to name the
       language, so the decision falls through to the Latin remainder.
    2. On the Latin text (the phonetic spelling the ASR actually produces for speech, in
       whatever language it was) score Portuguese vs English with stopwords plus the
       Portuguese diacritic set -- words dominate over diacritics because diacritics arrive
       only when the ASR happens to emit them.
    3. Ambiguous (the two scores within 15% of each other, or no stopword evidence at all)
       -> **Portuguese**, the owner's own language, as the plan specifies.  The decision is
       stored with its evidence so it stays auditable.
    """
    if not text.strip():
        # An empty window is a real case (--now inside an hour with no file yet, or an hour
        # before the archive starts).  It returns the SAME shape as the real path so no
        # caller has to special-case it -- this was a crash until it was measured.
        return "pt", {
            "rule": "empty-window",
            "script_chars": {name: 0 for name, _lo, _hi in _SCRIPT_RANGES} | {"other": 0},
            "non_latin_share": 0.0,
            "words": 0,
            "pt_hits": 0,
            "en_hits": 0,
            "pt_diacritics": 0,
            "pt_score": 0,
            "en_score": 0,
            "fallback": "pt",
        }

    script_chars = {name: 0 for name, _lo, _hi in _SCRIPT_RANGES}
    script_chars["other"] = 0
    latin_chars_for_words: list[str] = []
    for ch in text:
        o = ord(ch)
        placed = False
        for name, lo, hi in _SCRIPT_RANGES:
            if lo <= o <= hi:
                script_chars[name] += 1
                placed = True
                if name == "latin" or (0x00C0 <= o <= 0x024F):
                    latin_chars_for_words.append(ch)
                break
        if not placed:
            if o < 0x0080 or 0x00C0 <= o <= 0x024F:
                script_chars["latin"] += 1
                latin_chars_for_words.append(ch)
            else:
                script_chars["other"] += 1

    latin_text = "".join(latin_chars_for_words)
    words = re.findall(r"[A-Za-zÀ-ÿ]+", latin_text.lower())
    pt_hits = sum(1 for w in words if w in _PT_STOPWORDS)
    en_hits = sum(1 for w in words if w in _EN_STOPWORDS)
    diacritics = sum(1 for ch in latin_text if ch in _PT_DIACRITICS)
    pt_score = pt_hits + diacritics * 0.5
    en_score = float(en_hits)

    total_script = sum(script_chars.values()) or 1
    non_latin_share = 1.0 - (script_chars["latin"] / total_script)

    if pt_score == 0 and en_score == 0:
        language, rule = "pt", "no-stopword-evidence-fallback-pt"
    elif max(pt_score, en_score) < 3:
        language, rule = "pt", "too-little-evidence-fallback-pt"
    elif abs(pt_score - en_score) <= 0.15 * max(pt_score, en_score):
        language, rule = "pt", "ambiguous-fallback-pt"
    else:
        language = "pt" if pt_score > en_score else "en"
        rule = "stopword+diacritic-majority"

    evidence = {
        "rule": rule,
        "script_chars": script_chars,
        "non_latin_share": round(non_latin_share, 4),
        "words": len(words),
        "pt_hits": pt_hits,
        "en_hits": en_hits,
        "pt_diacritics": diacritics,
        "pt_score": round(pt_score, 2),
        "en_score": round(en_score, 2),
        "fallback": "pt",
    }
    return language, evidence


# ---------------------------------------------------------------------------
# the prompt (plan §5.4/§5.2) and answer parsing
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are given a transcript of speech from one hour of a person's computer audio. "
    "Reply in the SAME language as the transcript. If the transcript mixes languages, use "
    "the one that dominates.\n"
    "Answer with exactly two things and nothing else:\n"
    "TITLE: a title of at most 12 words.\n"
    "SUMMARY: a summary of exactly 3 sentences.\n"
    "Do not explain, do not add notes, do not show your reasoning."
)

SYSTEM_PROMPT_FOLD = (
    "You are updating a running summary of a long transcript. You are given the summary so "
    "far and the next part of the transcript. Reply in the SAME language as the transcript. "
    "If the transcript mixes languages, use the one that dominates.\n"
    "Answer with exactly two things and nothing else:\n"
    "TITLE: a title of at most 12 words for everything so far.\n"
    "SUMMARY: a summary of exactly 3 sentences covering everything so far.\n"
    "Do not explain, do not add notes, do not show your reasoning."
)

_LANG_NAME = {"pt": "Portuguese", "en": "English"}

TITLE_SYSTEM_PROMPT = (
    "You name recordings. Write a short name for the recording below: 3 to 7 words, sentence "
    "case, no trailing punctuation, no quotes, no 'Title:' prefix. Reply in the SAME language "
    "as the transcript. Never answer the message, never explain, never add notes."
)

# The two answer labels, kept SEPARATE on purpose: a combined alternation matched "TITLE"
# where the summary pattern was meant to match "SUMMARY", so the summary swallowed the title
# line (caught by the unit gate, not by reading the code).
TITLE_LABEL = r"(?:TITLE|T[IÍ]TULO)"
SUMMARY_LABEL = r"(?:SUMMARY|SUM[AÁ]RIO|RESUMO|RESUMEN)"


def build_title_prompt(first_chars: str, language: str, thinking: str = "off") -> str:
    """The TITLE call: a small prompt over the window's first ~1200 characters."""
    hint = _LANG_NAME.get(language, "Portuguese")
    # The wording mirrors the SUMMARY prompt's "Write the SUMMARY in X" because the earlier
    # "Name it in Portuguese" was read literally by the 0.8B, which answered with the word
    # "Portugues" -- the language, not a name (MEASURED on the largest hour).
    user = (f"The transcript is mostly {hint}. Write the TITLE in {hint}.\n\n"
            f"TRANSCRIPT START:\n{first_chars}")
    prefix = "<think>\n\n</think>\n\n" if thinking == "empty" else ""
    return (f"<|im_start|>system\n{TITLE_SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n{prefix}")


def build_prompt(transcript: str, language: str, running: str | None = None,
                 thinking: str = "off") -> str:
    """The SUMMARY call's prompt (ChatML, Qwen's own template shape), built by hand.

    Hand-built on purpose: ``og.Tokenizer.apply_chat_template`` needs the export's
    ``chat_template.jinja`` and a JSON message list, which the runtime accepts but which
    exposes no knob for the thinking mode.  ``thinking="empty"`` reproduces the template's own
    non-thinking convention (``<think>\\n\\n</think>\\n\\n``); ``thinking="off"`` writes no
    think prefix at all, which is the form that MEASURED better on this export -- the model then
    opens and closes its own think block and answers cleanly, while the explicit empty block
    produced degenerate repetition in the same session on the same prompt.
    """
    hint = _LANG_NAME.get(language, "Portuguese")
    system = SYSTEM_PROMPT if running is None else SYSTEM_PROMPT_FOLD
    user = f"The transcript is mostly {hint}. Write the SUMMARY in {hint}.\n\n"
    if running:
        user += f"SUMMARY SO FAR:\n{running}\n\nNEXT PART OF THE TRANSCRIPT:\n{transcript}"
    else:
        user += f"TRANSCRIPT:\n{transcript}"
    prefix = "<think>\n\n</think>\n\n" if thinking == "empty" else ""
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n{prefix}"
    )


def _clean_line(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^[#>\-*\s]+", "", text)
    text = text.strip("*`_ ").strip()
    return text.strip()


# ---------------------------------------------------------------------------
# output sanitation -- an ORDERED pipeline, and it rejects rather than cuts
# ---------------------------------------------------------------------------

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]|\x1b\[[0-9;]*[A-Za-z]|\\u[0-9a-fA-F]{4}")
TRAILING_PUNCT_RE = re.compile(r"[\s.,;:!?…\-–—]+$")
QUOTES = "\"'“”‘’«»"


def _strip_common(raw: str) -> str:
    """control/escape strip -> thinking strip -> markdown strip (the pipeline's first stages)."""
    text = CONTROL_RE.sub("", raw or "")
    text = THINK_RE.sub("", text)
    tail = THINK_TAIL_RE.search(text)
    if tail:
        text = text[tail.end():]
    if THINK_OPEN_RE.search(text):
        # Generated without closing its thought: there is NO answer in this text.  Returning
        # empty here is what makes the caller reject instead of shipping half a sentence.
        return ""
    text = text.replace("<|im_end|>", "").replace("<|im_start|>", "")
    text = text.replace("*", "").replace("`", "").replace("__", "")
    return re.sub(r"^[ \t]*[#>\-]+[ \t]*", "", text, flags=re.M)


def sanitize_title(raw: str) -> tuple[str | None, str | None]:
    """``(title, None)`` or ``(None, why_it_was_rejected)``.

    Order (docs/harness-title-practice.md §5): common strip -> first non-empty line -> label
    strip -> quote strip -> markdown strip (in ``_strip_common``) -> trailing punctuation ->
    UTF-8-safe cap -> **reject if > 12 words**.  An answer-shaped output (a sentence, a list,
    an echo of the instruction) is REJECTED and the caller falls back to a derived title --
    cutting a bad answer down to 12 words would ship the bad answer.
    """
    text = _strip_common(raw).strip()
    if not text:
        return None, "empty (no answer in the generated text)"
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    line = re.sub(rf"^{TITLE_LABEL}\s*:?\s*", "", line, flags=re.I).strip()
    line = line.strip(QUOTES).strip()
    line = TRAILING_PUNCT_RE.sub("", line).strip()
    line = " ".join(line.split())
    if not line:
        return None, "empty after sanitation"
    words = line.split()
    if len(words) > TITLE_MAX_WORDS:
        return None, (f"answer-shaped: {len(words)} words > {TITLE_MAX_WORDS} "
                      f"({line[:80]!r})")
    if len(line) > TITLE_MAX_CHARS:
        line = " ".join(line[:TITLE_MAX_CHARS].split()[:-1])
        if not line:
            return None, f"{TITLE_MAX_CHARS}-character cap left nothing"
    return line, None


def sanitize_summary(raw: str) -> tuple[str | None, str | None]:
    """``(summary, None)`` or ``(None, why_it_was_rejected)``.

    The summary is capped by SENTENCE BOUNDARY and word count (never cut mid-sentence), and a
    too-short result is rejected outright -- an empty summary must surface as a failure, never
    as a silent empty success.
    """
    text = _strip_common(raw).strip()
    text = re.sub(rf"^[ \t]*{SUMMARY_LABEL}\s*:?\s*", "", text, flags=re.I).strip()
    text = " ".join(text.split())
    if len(text.split()) < 4:
        return None, f"too short to be a summary ({text[:60]!r})"
    sentences = [s for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    kept: list[str] = []
    words = 0
    for sentence in sentences:
        if kept and (len(kept) >= SUMMARY_MAX_SENTENCES
                     or words + len(sentence.split()) > SUMMARY_MAX_WORDS):
            break
        kept.append(sentence.strip())
        words += len(sentence.split())
    out = " ".join(kept).strip()
    return (out, None) if len(out.split()) >= 4 else (None, "too short after trimming")


def derived_title(texts: list[str]) -> str:
    """The deterministic fallback the harnesses all carry: a name from the first words.

    It exists so a REJECTED title still yields something the panel can show -- but a rejected
    title is reported (``title_source: derived-fallback`` plus the reason), never disguised as
    the model's own answer.
    """
    first = texts[0] if texts else ""
    words = re.findall(r"[\wÀ-ÿ']+", first)
    text = " ".join(words[:7]).strip()
    if not text:
        return "Gravação sem título" if not words else "Gravação"
    return text[0].upper() + text[1:]


def parse_answer(raw: str) -> tuple[str, str] | None:
    """``(title, summary)`` from the model's own text, or ``None`` if there is no answer.

    ``None`` is a first-class outcome: it becomes ``summary-unavailable`` with reason
    ``empty-generation``.  A silent empty summary is the one thing this file must never do.
    """
    if not raw:
        return None
    text = THINK_RE.sub("", raw)
    tail = THINK_TAIL_RE.search(text)
    if tail:
        # A closing token with no opener we could match: everything before it was reasoning.
        text = text[tail.end():]
    opener = THINK_OPEN_RE.search(text)
    if opener:
        # Generated with no closing token inside the budget: the answer never arrived, and
        # an unfinished thought is NOT a title.  Returning None makes the caller report
        # empty-generation instead of shipping half a sentence.
        return None
    # Markdown emphasis and heading markers are decoration the model adds on its own answer,
    # never content.  Both spellings were MEASURED as parser failures before this line
    # existed: ``**Title:** X`` sailed past the anchors and came out as a title of ``** X``,
    # and ``# TITLE`` (the heading form this export actually emits) was not matched at all.
    text = text.replace("*", "").replace("`", "").replace("__", "")
    text = re.sub(r"^[ \t]*[#>\-]+[ \t]*", "", text, flags=re.M)
    text = text.replace("<|im_end|>", "").replace("<|im_start|>", "")

    # A label ALONE on its own line is the form this export emits ("# TITLE\n<text>"); join it
    # with the line that follows, so one parser handles both "TITLE: x" and "TITLE\nx".
    joined: list[str] = []
    pending: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        head = re.fullmatch(r"(TITLE|T[IÍ]TULO|SUMMARY|SUM[AÁ]RIO|RESUMO|RESUMEN)\s*:?", stripped,
                            re.I)
        if head:
            pending = head.group(1)
            continue
        if pending:
            if stripped:
                joined.append(f"{pending}: {stripped}")
                pending = None
            continue
        joined.append(line)
    text = "\n".join(joined)

    title = summary = ""
    m = re.search(rf"^[ \t]*{TITLE_LABEL}\s*:?\s*(.+)$", text, re.I | re.M)
    if m:
        title = _clean_line(m.group(1))
    ms = re.search(rf"^[ \t]*{SUMMARY_LABEL}\s*:?\s*(.*)$", text, re.I | re.M | re.S)
    if ms:
        summary = _clean_line(ms.group(1).replace("\n", " "))
    if not title or not summary or summary == title:
        lines = [_clean_line(x) for x in text.splitlines()]
        lines = [x for x in lines if x]
        # The first label-bearing line is the TITLE, the next one starts the summary.
        if not title and lines:
            title = lines[0]
        if not summary and len(lines) > 1:
            summary = " ".join(lines[1:])

    title = re.sub(rf"^{TITLE_LABEL}\s*:?\s*", "", title, flags=re.I).strip()
    summary = re.sub(rf"^{SUMMARY_LABEL}\s*:?\s*", "", summary, flags=re.I).strip()
    title = " ".join(title.split()[:12]).strip(" .")
    summary = " ".join(summary.split())
    if len(title) < 2 or len(summary.split()) < 4:
        return None
    return title[:200], summary[:2000]


# ---------------------------------------------------------------------------
# chunking (plan §4.3 / §5.2)
# ---------------------------------------------------------------------------


def chunk_units(units: list[tuple[int, str]], budget: int) -> list[list[str]]:
    """Group ``(token_count, text)`` units into chunks of at most ``budget`` tokens.

    Chunk boundaries follow LINE boundaries wherever they can, so the fold never splits a
    sentence in half; a single line longer than the whole budget is the only case split, and
    then it is split by characters at the ratio the line's own token count implies.
    """
    chunks: list[list[str]] = []
    current: list[str] = []
    used = 0
    for count, text in units:
        if count > budget and not current:
            # A single monster line: split it proportionally, at the ratio its own token count
            # implies.  Each piece becomes ITS OWN chunk -- appending the pieces as one chunk
            # would re-create the over-budget request this branch exists to avoid (a real bug,
            # caught by the unit gate, not by reading the code).
            approx_chars = max(1, int(len(text) * (budget / max(1, count))))
            for start in range(0, len(text), approx_chars):
                chunks.append([text[start:start + approx_chars]])
            continue
        if used + count > budget and current:
            chunks.append(current)
            current, used = [], 0
        current.append(text)
        used += count
    if current:
        chunks.append(current)
    return chunks


# ---------------------------------------------------------------------------
# cache (plan §5.3)
# ---------------------------------------------------------------------------


def cache_path(hour_start: datetime) -> Path:
    return HISTORY / hour_start.strftime("%Y-%m-%d") / f"{hour_start.hour:02d}.summary.json"


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_cache(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def cache_hit(record: dict | None, hour_iso: str, want_hash: str, want_partial: bool,
              want_model: str | None = None) -> bool:
    """The key is ``hour`` + ``content_hash`` + ``partial`` -- all three, no shortcuts.

    A ``partial:true`` record must never answer a full-hour request, and a record whose hash
    differs means new speech arrived, so the model runs again.  ``estimated:true`` records
    (a hand-written placeholder) are refused too: they are not a measurement.

    **``want_model`` extends the plan's three-part key by one, deliberately.**  A summary is
    not a pure function of the text: it is the text *as read by a particular model*, so a
    record produced by model X must never be served as model Y's -- and an interactive
    ``--force`` is not a defence for the automatic hourly pass, which has nobody watching.
    ``None`` means "do not check", which is what the read-only callers use.
    """
    if not record:
        return False
    if record.get("schema") != SCHEMA:
        return False
    if record.get("hour") != hour_iso:
        return False
    if record.get("content_hash") != want_hash:
        return False
    if bool(record.get("partial")) != bool(want_partial):
        return False
    if record.get("estimated") is True:
        return False
    if want_model is not None and record.get("model") != want_model:
        return False
    return bool(record.get("title")) and bool(record.get("summary"))


def write_cache(path: Path, record: dict) -> None:
    """Write the sidecar atomically.  It is a NEW file next to the transcript: the
    transcript is never opened for writing by this module."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        _log(f"cache: write failed for {path} ({type(exc).__name__}: {exc})")


# ---------------------------------------------------------------------------
# the model (plan §7.2)
# ---------------------------------------------------------------------------


class GenerationFailure(RuntimeError):
    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def read_genai_context(model_dir: Path) -> tuple[int | None, str | None, object]:
    """The export's own context length, read from ``genai_config.json``.

    Returns ``(context_length, where_it_came_from, provider_options_requested)``.  Read
    rather than assumed: the plan's §4.3 Term 1 could not know it ("UNKNOWN until a built
    model is inspected"), and a quantised export routinely ships a much smaller default than
    the base model's 262,144.  This is the ONLY hard ceiling on a request; everything else
    is a latency choice the measurement decides.
    """
    path = model_dir / "genai_config.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None, None

    found: list[tuple[int, str]] = []

    def walk(node, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("context_length", "max_length", "n_ctx", "max_seq_len") \
                        and isinstance(value, int) and value > 256:
                    found.append((value, f"{trail}.{key}" if trail else key))
                walk(value, f"{trail}.{key}" if trail else key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{trail}[{index}]")

    walk(config, "")
    providers = None
    try:
        providers = config.get("model", {}).get("decoder", {}).get(
            "session_options", {}).get("provider_options")
    except AttributeError:
        providers = None
    if not found:
        return None, None, providers
    value, where = min(found, key=lambda pair: pair[0])
    return value, where, providers


def load_model(model_dir: Path, force_cpu: bool):
    """Load the ORT-GenAI model, CPU-bound, and return ``(model, reload_report)``.

    The provider is set through ``og.Config`` rather than left to the export's own
    ``genai_config.json``: measured on this box, ORT **advertises** CUDA and cannot bind it
    (``cublasLt64_13.dll`` missing, ORT 1.30 wants CUDA 13 / this box has 12.8), so an
    export that asks for CUDA would silently fall back to CPU while claiming otherwise.
    ``clear_providers()`` + ``append_provider("cpu")`` makes the request and the reality the
    same thing, and the report says exactly what was asked for.
    """
    import onnxruntime_genai as og  # imported late: --dry-run must not need it

    report: dict = {"force_cpu": force_cpu}
    config = og.Config(str(model_dir))
    if force_cpu:
        config.clear_providers()
        config.append_provider("cpu")
    model = og.Model(config)
    report["is_cuda_available_reported"] = bool(og.is_cuda_available())
    try:
        report["device_type"] = str(model.device_type)
    except Exception:  # noqa: BLE001
        report["device_type"] = None
    try:
        params = og.GeneratorParams(model)
        report["search_options_default"] = params.get_search_options()
    except Exception:  # noqa: BLE001
        report["search_options_default"] = None
    return model, report


def generate(model, text: str, max_new: int, deadline: float | None,
             request_max: int | None = None, repetition_penalty: float = 1.0,
             no_repeat_ngram_size: int = 0) -> tuple[str, dict]:
    """One greedy request.  Returns ``(raw_text, timing_report)``.

    Timing is split at the one boundary that matters for the plan's estimate: the FIRST
    ``generate_next_token()`` carries the prefill, so ``ttft_s`` is a measured
    prefill cost (the plan's ``0.05 s/token`` was an assumption, §8.2), and
    ``decode_tokens_per_s`` is the steady-state rate after it.

    ``request_max``, when given, is a CONTRACT that is verified on the built prompt rather
    than assumed from the chunk planner: if template + transcript + output room would exceed
    it, that is a hard failure (``context-overflow``), never a silent overrun.
    """
    import numpy as np
    import onnxruntime_genai as og

    tokenizer = og.Tokenizer(model)
    t_enc0 = time.perf_counter()
    ids = np.asarray(tokenizer.encode(text), dtype=np.int32)
    encode_s = time.perf_counter() - t_enc0
    prompt_len = int(ids.shape[0])
    if request_max is not None and prompt_len + int(max_new) > request_max:
        raise GenerationFailure(
            "context-overflow",
            f"prompt {prompt_len} + max_new {max_new} exceeds the {request_max}-token request "
            f"ceiling; the chunk planner and the tokenizer disagree",
        )
    t_init0 = time.perf_counter()
    params = og.GeneratorParams(model)
    search: dict = {"max_length": prompt_len + int(max_new), "do_sample": False}
    if repetition_penalty and repetition_penalty != 1.0:
        search["repetition_penalty"] = float(repetition_penalty)
    if no_repeat_ngram_size:
        search["no_repeat_ngram_size"] = int(no_repeat_ngram_size)
    params.set_search_options(**search)
    generator = og.Generator(model, params)
    generator_init_s = time.perf_counter() - t_init0
    t_append0 = time.perf_counter()
    generator.append_tokens(ids)
    append_s = time.perf_counter() - t_append0

    # WHERE THE PROMPT PROCESSING ACTUALLY HAPPENS — MEASURED, and it is not where the plan
    # assumed: `og.Generator(...)` + `append_tokens(ids)` run the prefill in THIS runtime, so
    # the first `generate_next_token()` call returns in ~0.0003 s.  Reporting that as TTFT
    # would have been a spectacular false (a 7.6k-token hour "prefilled" in 300 microseconds).
    # So: prompt_processing_s = init + append (the prefill), and ttft_s = that plus the first
    # decode step = time to the first generated token, end to end.
    steps = 0
    first_step_s = None
    decode_total_s = 0.0
    cpu_before = process_cpu_s()
    t0 = time.perf_counter()
    while not generator.is_done():
        step0 = time.perf_counter()
        generator.generate_next_token()
        step_s = time.perf_counter() - step0
        steps += 1
        if first_step_s is None:
            first_step_s = step_s
        else:
            decode_total_s += step_s
        if deadline is not None and time.perf_counter() > deadline:
            raise GenerationFailure(
                "generation-did-not-terminate",
                f"wall-clock ceiling of --max-seconds hit after {steps} token(s) of "
                f"{prompt_len + int(max_new)} allowed; the partial text is NOT a summary "
                f"and was discarded",
            )
    decode_wall_s = time.perf_counter() - t0
    cpu_after = process_cpu_s()
    cpu_used = (round(cpu_after - cpu_before, 3)
                if (cpu_after is not None and cpu_before is not None) else None)
    seq = generator.get_sequence(0)
    ids_out = [int(x) for x in list(seq)]
    gen_ids = ids_out[prompt_len:] if len(ids_out) > prompt_len else ids_out
    # DID IT STOP ON ITS OWN?  The vendor card warns that the 0.8B "is more prone to entering
    # thinking loops … which may prevent it from terminating generation properly", and for an
    # unattended hourly pass a loop is a CPU fire, not a quality quibble.  The predicate is
    # MEASURED against this runtime's own behaviour, not assumed: `get_sequence()` does not
    # include the EOS token, so a run that finished naturally takes ONE step more than the
    # tokens it returned (steps = generated + 1), while a run cut by the ceiling takes exactly
    # as many steps as tokens (steps = generated).  Verified on the installed wheel:
    # max_length=prompt+1 -> steps=1, generated=1; max_length=prompt+64 -> steps=8, generated=7.
    eos_ids = set()
    try:
        eos_ids = {int(x) for x in tokenizer.eos_token_ids}
    except Exception:  # noqa: BLE001
        eos_ids = set()
    ended_with_eos = steps > len(gen_ids)
    hit_token_cap = (steps >= int(max_new)) and not ended_with_eos
    raw = tokenizer.decode(np.asarray(gen_ids, dtype=np.int32))
    decode_tokens = max(0, steps - 1)
    prompt_processing_s = generator_init_s + append_s
    report = {
        "prompt_tokens": prompt_len,
        "generated_tokens": len(gen_ids),
        "max_output_tokens_allowed": int(max_new),
        "ended_with_eos": ended_with_eos,
        "hit_token_cap": hit_token_cap,
        "decode_steps": steps,
        "eos_token_ids_configured": sorted(eos_ids),
        "encode_s": round(encode_s, 4),
        "generator_init_s": round(generator_init_s, 4),
        "append_tokens_s": round(append_s, 4),
        "prompt_processing_s": round(prompt_processing_s, 3),
        "prompt_processing_ms_per_token": (round(prompt_processing_s / prompt_len * 1000, 4)
                                           if prompt_len else None),
        "first_decode_step_s": round(first_step_s, 4) if first_step_s is not None else None,
        "ttft_s": round(prompt_processing_s + (first_step_s or 0.0), 3),
        "decode_wall_s": round(decode_wall_s, 3),
        "decode_cpu_s": cpu_used,
        "decode_cpu_per_wall": (round(cpu_used / decode_wall_s, 3)
                                if (cpu_used is not None and decode_wall_s > 0) else None),
        "not_computing_s": (round(max(0.0, decode_wall_s - cpu_used), 3)
                            if cpu_used is not None else None),
        "decode_total_s": round(decode_total_s, 4),
        "decode_tokens_per_s": (round(decode_tokens / decode_total_s, 2)
                                if decode_total_s > 0 else None),
        "generation_s": round(prompt_processing_s + decode_wall_s, 3),
    }
    return raw, report


# ---------------------------------------------------------------------------
# window resolution
# ---------------------------------------------------------------------------


def _parse_iso(value: str, default_date: datetime | None) -> datetime:
    """``YYYY-MM-DDTHH:MM[:SS]``, or a bare ``HH:MM[:SS]`` on ``default_date``."""
    text = value.strip()
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
        if default_date is None:
            raise ValueError(f"{value!r}: a bare time needs --hour or a full date")
        hh, mm, ss = [int(x) for x in (text.split(":") + ["0"])[:3]]
        return default_date.replace(hour=hh, minute=mm, second=ss, microsecond=0)
    dt = datetime.fromisoformat(text)
    return dt.replace(tzinfo=None)


def _iso_hour(dt: datetime) -> str:
    """The plan's ``hour`` format: local ISO with an explicit UTC offset."""
    local = dt.astimezone()
    return local.replace(microsecond=0).isoformat()


def resolve_window(args) -> tuple[datetime, datetime, bool, str]:
    """``(from_dt, to_dt, partial, trigger)`` for the requested window.

    * ``--hour YYYY-MM-DDTHH`` -> the whole hour ``[HH:00:00, HH+1:00:00)``.
    * ``--from``/``--to``      -> the manual window; ``--to`` defaults to NOW, which is the
      "use it now" case (start of the hour -> now).
    * ``--now``                -> ``[start of the current hour, now)``.
    """
    now = datetime.now().replace(microsecond=0)
    if args.hour:
        hit = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T(\d{2})(?::(\d{2}))?", args.hour.strip())
        if not hit:
            raise ValueError(f"--hour must be YYYY-MM-DDTHH, got {args.hour!r}")
        if hit.group(3) and hit.group(3) != "00":
            raise ValueError("--hour means a whole hour; use --from/--to for a sub-window")
        start = datetime.fromisoformat(f"{hit.group(1)}T{hit.group(2)}:00:00")
        end = start + timedelta(hours=1)
        is_partial = end > now
        return start, end, is_partial, (args.trigger or "backfill")

    if args.now:
        start = now.replace(minute=0, second=0)
        return start, now + timedelta(seconds=1), True, (args.trigger or "manual")

    if not args.from_iso:
        raise ValueError("need --hour, --now or --from")
    base = None
    if args.hour:
        base = datetime.fromisoformat(args.hour[:13] + ":00:00")
    start = _parse_iso(args.from_iso, base or now)
    if args.to_iso:
        end = _parse_iso(args.to_iso, start)
    else:
        end = now + timedelta(seconds=1)
    if end <= start:
        raise ValueError("--to must be after --from")
    whole_hour = (
        start.minute == 0 and start.second == 0
        and end == start + timedelta(hours=1)
    )
    return start, end, (not whole_hour) or (end > now), (args.trigger or "manual")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qwen_summary.py",
        description="Title + 3-sentence summary for a window of the Sotto transcript "
                    "(ORT-GenAI, local, CPU). One JSON line on stdout; diagnostics on stderr.",
    )
    window = parser.add_argument_group("window (one of these)")
    window.add_argument("--hour", metavar="YYYY-MM-DDTHH",
                        help="the whole hour (the hourly boundary case)")
    window.add_argument("--from", dest="from_iso", metavar="ISO",
                        help="manual window start (YYYY-MM-DDTHH:MM or HH:MM)")
    window.add_argument("--to", dest="to_iso", metavar="ISO",
                        help="manual window end; defaults to now")
    window.add_argument("--now", action="store_true",
                        help="start of the current hour -> now (the manual 'use now' case)")
    window.add_argument("--trigger", choices=("hourly", "manual", "backfill"),
                        help="recorded in the sidecar; default hourly for --hour, manual otherwise")

    model = parser.add_argument_group("model")
    model.add_argument("--model-dir", type=Path,
                       default=Path(os.environ.get("SOTTO_QWEN_MODEL_DIR", str(DEFAULT_MODEL_DIR))),
                       help=f"ORT-GenAI export directory (default: {DEFAULT_MODEL_DIR})")
    model.add_argument("--model-name", default=None,
                       help="name recorded in the result (default: the directory name)")
    model.add_argument("--allow-gpu", action="store_true",
                       help="do NOT force the CPU provider (default: CPU is forced explicitly, "
                            "because ORT advertises CUDA here and cannot bind it)")

    behaviour = parser.add_argument_group("behaviour")
    behaviour.add_argument("--json", action="store_true",
                           help="no human-readable rendering; the JSON line is printed either "
                                "way and diagnostics stay on stderr")
    behaviour.add_argument("--max-request-tokens", type=int, default=0, metavar="N",
                           help="impose a ceiling of N tokens on ONE request and fold the "
                                "window in order if it exceeds it. Default 0 = no imposed "
                                "ceiling: the whole window goes in one request, bounded only "
                                "by the model's own context_length from genai_config.json. "
                                "The plan's 3,072 was derived from fp32 throughput and is kept "
                                "as a REFERENCE, not as a window size.")
    behaviour.add_argument("--dry-run", action="store_true",
                           help="window, tokens, chunks, language and cache state; NEVER loads the model")
    behaviour.add_argument("--force", action="store_true",
                           help="ignore a cached result, but still write the new one")
    behaviour.add_argument("--no-cache", action="store_true",
                           help="ignore AND do not write the sidecar")
    behaviour.add_argument("--max-output-tokens", type=int, default=SUMMARY_MAX_NEW_TOKENS,
                           metavar="N",
                           help=f"hard ceiling on tokens the model may WRITE for the SUMMARY "
                                f"(default {SUMMARY_MAX_NEW_TOKENS}). A run that reaches it "
                                f"without an end-of-sequence token is reported as "
                                f"summary-unavailable reason=generation-did-not-terminate, "
                                f"never as a summary.")
    behaviour.add_argument("--title-output-tokens", type=int, default=TITLE_MAX_NEW_TOKENS,
                           metavar="N",
                           help=f"hard ceiling on tokens the model may WRITE for the TITLE "
                                f"(default {TITLE_MAX_NEW_TOKENS}). A title is 3-7 words, so a "
                                f"model still writing after this many tokens is looping.")
    behaviour.add_argument("--max-seconds", type=float, default=None,
                           help="wall-clock ceiling for generation; on expiry the run reports "
                                "summary-unavailable reason=generation-did-not-terminate "
                                "instead of a half summary")
    behaviour.add_argument("--thinking", choices=("off", "empty"), default="off",
                           help="off (default): no think prefix -- MEASURED better on this "
                                "export, which opens and closes its own think block. empty: the "
                                "export's own template convention for disabling reasoning "
                                "(<think></think> with nothing in it), kept because the vendor "
                                "card names thinking loops as the 0.8B's failure mode.")
    behaviour.add_argument("--repetition-penalty", type=float, default=1.0,
                           help="ORT-GenAI search option; 1.0 is the runtime's own default "
                                "(greedy, no penalty). Raised to test whether a small model's "
                                "degenerate repetition is a decoding artefact.")
    behaviour.add_argument("--no-repeat-ngram-size", type=int, default=0,
                           help="ORT-GenAI search option; 0 is the runtime's own default "
                                "(off). A positive value forbids repeated n-grams outright.")
    behaviour.add_argument("--priority", choices=tuple(_PRIORITY_CLASSES), default="below-normal",
                           help="this process' OS priority class (default below-normal: the live "
                                "ASR worker is the primary job)")
    behaviour.add_argument("--quiet", action="store_true", help="suppress the stderr diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    _utf8_streams()
    args = build_parser().parse_args(argv)
    diagnostics: list[str] = []

    def note(message: str) -> None:
        diagnostics.append(message)
        if not args.quiet:
            _log(message)

    priority_ok = set_priority(args.priority)

    try:
        from_dt, to_dt, partial, trigger = resolve_window(args)
    except ValueError as exc:
        _log(f"qwen_summary: {exc}")
        return 1

    hour_start = from_dt.replace(minute=0, second=0, microsecond=0)
    hour_iso = _iso_hour(hour_start)
    window_hours = ((to_dt - from_dt).total_seconds() + 3599) // 3600
    spans_hours = window_hours > 1
    model_dir = Path(args.model_dir).resolve()
    model_name = args.model_name or model_dir.name

    t_start = time.perf_counter()
    entries, files = read_window(from_dt, to_dt)
    note(f"window: {from_dt.isoformat()} .. {to_dt.isoformat()} "
         f"({'partial' if partial else 'whole hour'}, trigger={trigger})")
    note(f"archive: {len(entries)} closed line(s) from {len(files)} file(s): "
         f"{', '.join(files) if files else '(none)'}")

    texts = collapse_runs(entries)
    # What the model is actually fed.  Collapsed runs, in order, one per line -- the
    # worker's cumulative re-emissions are NOT repeated to the model.
    fed_text = "\n".join(texts)
    tokenizer = Tokenizer(model_dir if model_dir.is_dir() else None)
    note(f"tokenizer: {tokenizer.kind}"
         + (f" ({tokenizer.source})" if tokenizer.source else
            " -- no tokenizer.json/model dir available, character heuristic in use"))

    tokens_in = tokenizer.count(fed_text) if fed_text else 0
    probe_equivalent = novel_dedup_tokens([t for _dt, t in entries], tokenizer.count)
    language, census = language_census(fed_text)
    note(f"language census: {language} ({census['rule']}; pt={census['pt_score']} "
         f"en={census['en_score']} non_latin_share={census['non_latin_share']})")
    note(f"tokens: fed={tokens_in} (novel-suffix dedup, the plan's comparable count="
         f"{probe_equivalent}) MIN={MIN_TOKENS} plan_reference_max={PLAN_CPU_MAX_TOKENS}")

    digest = content_hash(fed_text)

    # ---- the gate, BEFORE anything model-shaped is constructed ----------------------
    # Below MIN there is not enough content for a title plus a summary (plan §4.2); the run
    # refuses and reports, and this is the arm that must prove no model was touched.
    if tokens_in < MIN_TOKENS:
        note("gate: BELOW MIN -- refusing without loading or calling the model")
        _emit({
            "type": "summary-unavailable",
            "reason": "below-min",
            "detail": f"{tokens_in} token(s) of content, MIN is {MIN_TOKENS}; a title and a "
                      f"summary from less than that would be invented",
            "min_tokens": MIN_TOKENS,
            "tokens_in": tokens_in,
            "lines": len(entries),
            "window": {"from": from_dt.isoformat(sep=" "), "to": to_dt.isoformat(sep=" ")},
            "hour": hour_iso,
            "language": language,
            "model": model_name,
            "model_called": False,
            "tokenizer": tokenizer.kind,
            "downloads_attempted": False,
        })
        return 2

    # ---- cache ---------------------------------------------------------------------
    cpath = cache_path(hour_start)
    cacheable = (not args.no_cache) and (not spans_hours)
    record = read_cache(cpath) if cacheable else None
    hit = cacheable and not args.force and cache_hit(record, hour_iso, digest, partial, model_name)
    if hit:
        note(f"cache: HIT {cpath} (hour+content_hash+partial+model match)")
        _emit({
            "type": "summary",
            "hour": hour_iso,
            "title": record.get("title"),
            "summary": record.get("summary"),
            "tokens_in": record.get("input_tokens", tokens_in),
            "tokens_out": record.get("tokens_out"),
            "model": record.get("model", model_name),
            "language": record.get("language", language),
            "cached": True,
            "wall_s": round(time.perf_counter() - t_start, 3),
            "partial": bool(record.get("partial")),
            "trigger": trigger,
            "path": str(cpath.relative_to(ROOT)).replace("\\", "/"),
            "content_hash": digest,
            "peak_rss_mb": peak_rss_mb(),
        })
        return 0
    if cacheable and record and not args.force:
        reasons = []
        if record.get("hour") != hour_iso:
            reasons.append(f"hour={record.get('hour')!r}")
        if record.get("content_hash") != digest:
            reasons.append("content_hash differs (new speech in the window)")
        if bool(record.get("partial")) != bool(partial):
            reasons.append(f"partial={record.get('partial')!r}")
        if record.get("model") != model_name:
            reasons.append(f"model={record.get('model')!r} (this run is {model_name!r}; the "
                           f"model is part of the key so one model's summary is never served "
                           f"as another's)")
        if record.get("estimated") is True:
            reasons.append("record is marked estimated")
        note(f"cache: MISS {cpath} ({'; '.join(reasons) if reasons else 'record unusable'})")
    elif not cacheable:
        note("cache: not used for this request "
             f"({'--no-cache' if args.no_cache else 'window spans more than one hour file'})")

    # ---- the request plan: the WHOLE window in ONE request unless something forbids it --
    # The only hard ceiling is the model's own context length, read from its
    # genai_config.json (the plan could not know it: §4.3 Term 1).  The plan's 3,072-token
    # CPU figure is reported as a reference and applied ONLY if --max-request-tokens asks
    # for it -- measured after the plan, the int4 kernel is ~12x the fp32 throughput the
    # plan's latency model used, so splitting a real hour to fit 3,072 would be splitting
    # for a number that was never a property of this machine's int4 path.
    context_limit, context_where, providers_requested = read_genai_context(model_dir)
    template_overhead = tokenizer.count(build_prompt("", language, None, args.thinking)) if texts else 0
    reserve = args.max_output_tokens + template_overhead + RUNNING_RESERVE

    ceilings: list[tuple[int, str]] = []
    if args.max_request_tokens:
        ceilings.append((int(args.max_request_tokens), "--max-request-tokens"))
    if context_limit:
        ceilings.append((int(context_limit), f"genai_config.json {context_where}"))
    if ceilings:
        hard_ceiling, ceiling_where = min(ceilings, key=lambda pair: pair[0])
        transcript_budget = hard_ceiling - reserve
        if transcript_budget < 64:
            _log(f"qwen_summary: the {hard_ceiling}-token ceiling ({ceiling_where}) leaves no "
                 f"room for a transcript after {reserve} token(s) of template+output reserve")
            return 1
    else:
        hard_ceiling, ceiling_where, transcript_budget = None, None, None

    units = [(tokenizer.count(t) if tokenizer.kind != "heuristic" else char_tokens(t), t)
             for t in texts]
    if transcript_budget is None:
        chunks = [texts] if texts else []
        note(f"request plan: the WHOLE window in 1 request ({tokens_in} tokens) -- no ceiling "
             f"was found (no --max-request-tokens, no readable genai_config.json context_length)")
    else:
        chunks = chunk_units(units, transcript_budget)
        note(f"request plan: ceiling {hard_ceiling} ({ceiling_where}) - new {args.max_output_tokens} - "
             f"template {template_overhead} - running_reserve {RUNNING_RESERVE} -> transcript "
             f"budget {transcript_budget}; {tokens_in} token(s) -> {len(chunks)} chunk(s)")
    request_max = hard_ceiling  # verified per request in generate(); None means no contract

    if args.dry_run:
        _emit({
            "type": "summary-plan",
            "hour": hour_iso,
            "window": {"from": from_dt.isoformat(sep=" "), "to": to_dt.isoformat(sep=" ")},
            "lines": len(entries),
            "fed_lines": len(texts),
            "tokens_in": tokens_in,
            "tokens_in_novel_dedup": probe_equivalent,
            "min_tokens": MIN_TOKENS,
            "plan_reference_max_tokens": PLAN_CPU_MAX_TOKENS,
            "request_ceiling": hard_ceiling,
            "request_ceiling_source": ceiling_where,
            "genai_context_length": context_limit,
            "genai_context_source": context_where,
            "provider_options_in_export": providers_requested,
            "chunks": len(chunks),
            "chunk_tokens": [sum(c for c, _t in [(tokenizer.count(x), x) for x in ch])
                             for ch in chunks],
            "language": language,
            "language_census": census,
            "model": model_name,
            "model_dir": str(model_dir),
            "model_dir_present": model_dir.is_dir(),
            "tokenizer": tokenizer.kind,
            "cache_path": str(cpath.relative_to(ROOT)).replace("\\", "/"),
            "cache_state": ("hit" if (cacheable and cache_hit(record, hour_iso, digest, partial,
                                                              model_name))
                            else "miss" if cacheable else "unused"),
            "partial": partial,
            "content_hash": digest,
            "model_loaded": False,
            "downloads_attempted": False,
        })
        return 0

    # ---- the model -----------------------------------------------------------------
    if not model_dir.is_dir():
        note(f"model: {model_dir} does not exist -- reporting, NOT downloading")
        _emit({
            "type": "summary-unavailable",
            "reason": "model-missing",
            "detail": f"no model directory at {model_dir}; this tool never downloads "
                      f"(plan §6.3) -- the acquisition step is a separate, gated command",
            "model": model_name,
            "model_dir": str(model_dir),
            "hour": hour_iso,
            "tokens_in": tokens_in,
            "language": language,
            "model_called": False,
            "downloads_attempted": False,
        })
        return 3

    try:
        t_load = time.perf_counter()
        model, reload_report = load_model(model_dir, force_cpu=not args.allow_gpu)
    except Exception as exc:  # noqa: BLE001
        _emit({
            "type": "summary-unavailable",
            "reason": "model-load-failed",
            "detail": f"{type(exc).__name__}: {exc}",
            "model": model_name,
            "model_dir": str(model_dir),
            "hour": hour_iso,
            "tokens_in": tokens_in,
            "downloads_attempted": False,
        })
        return 3
    load_s = time.perf_counter() - t_load
    note(f"model: loaded in {load_s:.2f}s from {model_dir} "
         f"(device_type={reload_report.get('device_type')!r}, "
         f"cuda_reported_available={reload_report.get('is_cuda_available_reported')})")

    deadline = (time.perf_counter() + args.max_seconds) if args.max_seconds else None
    calls: list[dict] = []
    title = ""
    title_source = "model"
    title_rejection: str | None = None
    summary = ""
    try:
        # ---- CALL 1 of N: the TITLE, over the window's FIRST characters only ----------
        title_input = fed_text[:TITLE_INPUT_CHARS]
        t_raw, t_timing = generate(
            model, build_title_prompt(title_input, language, args.thinking),
            args.title_output_tokens, deadline, request_max=request_max,
            repetition_penalty=args.repetition_penalty,
            no_repeat_ngram_size=args.no_repeat_ngram_size,
        )
        calls.append({"call": "title", "tokens_in": t_timing["prompt_tokens"],
                      "tokens_out": t_timing["generated_tokens"], "raw": t_raw[:2000],
                      **{k: v for k, v in t_timing.items()
                         if k not in ("prompt_tokens", "generated_tokens")}})
        note(f"title call: in={t_timing['prompt_tokens']} out={t_timing['generated_tokens']} "
             f"prefill={t_timing['prompt_processing_s']}s ttft={t_timing['ttft_s']}s "
             f"ended_with_eos={t_timing['ended_with_eos']} raw={t_raw[:120]!r}")
        if t_timing["hit_token_cap"] or not t_timing["ended_with_eos"]:
            raise GenerationFailure(
                "generation-did-not-terminate",
                f"the TITLE call produced {t_timing['generated_tokens']} token(s) and stopped on "
                f"the {t_timing['max_output_tokens_allowed']}-token ceiling WITHOUT an end-of-"
                f"sequence token -- it did not finish: {t_raw[:200]!r}",
            )
        title, title_rejection = sanitize_title(t_raw)
        if title is None:
            title = derived_title(texts)
            title_source = "derived-fallback"
            note(f"title REJECTED by the sanitation pipeline ({title_rejection}) "
                 f"-> deterministic fallback title: {title!r}")

        # ---- CALLS 2..N: the SUMMARY over the whole window (folded only if a cap says so) --
        running: str | None = None
        for index, chunk in enumerate(chunks):
            chunk_text = "\n".join(chunk)
            prompt = build_prompt(chunk_text, language, running, args.thinking)
            raw, timing = generate(
                model, prompt, args.max_output_tokens, deadline,
                request_max=request_max,  # verified inside: perform, do not assume
                repetition_penalty=args.repetition_penalty,
                no_repeat_ngram_size=args.no_repeat_ngram_size,
            )
            calls.append({"call": "summary", "chunk": index + 1, "of": len(chunks),
                          "tokens_in": timing["prompt_tokens"],
                          "tokens_out": timing["generated_tokens"], "raw": raw[:4000],
                          **{k: v for k, v in timing.items()
                             if k not in ("prompt_tokens", "generated_tokens")}})
            note(f"summary call {index + 1}/{len(chunks)}: in={timing['prompt_tokens']} "
                 f"out={timing['generated_tokens']} prefill={timing['prompt_processing_s']}s "
                 f"ttft={timing['ttft_s']}s decode={timing['decode_tokens_per_s']} tok/s "
                 f"gen={timing['generation_s']}s ended_with_eos={timing['ended_with_eos']}")
            if timing["hit_token_cap"] or not timing["ended_with_eos"]:
                # A model that ran to the token ceiling without emitting EOS is the vendor's
                # documented 0.8B thinking-loop hazard actually happening.  The text IS returned
                # as evidence, but the message type says plainly that it is not a summary.
                raise GenerationFailure(
                    "generation-did-not-terminate",
                    f"summary chunk {index + 1}/{len(chunks)}: produced "
                    f"{timing['generated_tokens']} token(s) and stopped on the "
                    f"{timing['max_output_tokens_allowed']}-token ceiling WITHOUT an end-of-"
                    f"sequence token (ended_with_eos=false) -- it did not finish; the partial "
                    f"text is evidence, not a summary: {raw[:300]!r}",
                )
            cleaned, why = sanitize_summary(raw)
            if cleaned is None:
                raise GenerationFailure(
                    "empty-generation",
                    f"summary chunk {index + 1}/{len(chunks)}: no usable summary ({why}); "
                    f"raw={raw[:200]!r}",
                )
            summary = cleaned
            # The fold carries the PROSE forward, not the raw text: §5.2 keeps the fold
            # lossy in order, so the running summary is the reduction state.
            running = summary
    except GenerationFailure as exc:
        note(f"FAILED after {len(calls)} call(s): {exc.reason}: {exc.detail}")
        _emit({
            "type": "summary-unavailable",
            "reason": exc.reason,
            "detail": exc.detail,
            "hour": hour_iso,
            "model": model_name,
            "model_dir": str(model_dir),
            "tokens_in": tokens_in,
            "language": language,
            "calls_done": len(calls),
            "calls": [{"call": c["call"], "tokens_in": c["tokens_in"],
                       "tokens_out": c["tokens_out"]} for c in calls],
            "downloads_attempted": False,
        })
        return 3
    except Exception as exc:  # noqa: BLE001
        note(f"FAILED: {type(exc).__name__}: {exc}")
        _emit({
            "type": "summary-unavailable",
            "reason": "generation-failed",
            "detail": f"{type(exc).__name__}: {exc}",
            "hour": hour_iso,
            "model": model_name,
            "model_dir": str(model_dir),
            "tokens_in": tokens_in,
            "calls_done": len(calls),
            "calls_total": 1 + len(chunks),
            "downloads_attempted": False,
        })
        return 3

    wall_s = round(time.perf_counter() - t_start, 3)
    tokens_out = sum(c["tokens_out"] for c in calls)
    rss = peak_rss_mb()
    title_call = next((c for c in calls if c["call"] == "title"), {})
    summary_call = next((c for c in calls if c["call"] == "summary"), {})

    if not args.json:
        note("")
        note(f"TITLE: {title}" + (f"   [source={title_source}: {title_rejection}]"
                                  if title_rejection else ""))
        note(f"SUMMARY: {summary}")
        note(f"tokens in/out={tokens_in}/{tokens_out} wall={wall_s}s peak_rss={rss} MiB "
             f"language={language} model={model_name}")

    result = {
        "type": "summary",
        "hour": hour_iso,
        "title": title,
        "summary": summary,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": model_name,
        "language": language,
        "cached": False,
        "wall_s": wall_s,
        # ---- beyond the contract, for the receipt and for the scheduler ----------
        "partial": partial,
        "trigger": trigger,
        "path": str(cache_path(hour_start).relative_to(ROOT)).replace("\\", "/"),
        "cache_written": bool(cacheable),
        "content_hash": digest,
        "content_hash_recipe": "sha256 over the collapse_runs() text fed to the model, UTF-8",
        "lines": len(entries),
        "files": files,
        "window": {"from": from_dt.isoformat(sep=" "), "to": to_dt.isoformat(sep=" ")},
        "chunks": len(chunks),
        "calls": calls,
        "title_source": title_source,
        "title_rejection": title_rejection,
        "title_input_chars": min(len(fed_text), TITLE_INPUT_CHARS),
        "tokens_in_novel_dedup": probe_equivalent,
        "tokenizer": tokenizer.kind,
        "language_census": census,
        "engine": ENGINE,
        "model_dir": str(model_dir),
        "provider": reload_report,
        "decoding": {"do_sample": False, "temperature": 1.0,
                     "repetition_penalty": args.repetition_penalty,
                     "no_repeat_ngram_size": args.no_repeat_ngram_size,
                     "title_max_output_tokens": args.title_output_tokens,
                     "summary_max_output_tokens": args.max_output_tokens,
                     "calls": 1 + len(chunks)},
        "load_s": round(load_s, 3),
        "title_ttft_s": title_call.get("ttft_s"),
        "title_prefill_s": title_call.get("prompt_processing_s"),
        "ttft_s": summary_call.get("ttft_s"),
        "prompt_processing_s": summary_call.get("prompt_processing_s"),
        "decode_tokens_per_s": summary_call.get("decode_tokens_per_s"),
        "summary_words": len(summary.split()),
        "title_words": len(title.split()),
        "peak_rss_mb": rss,
        "priority": args.priority,
        "priority_applied": priority_ok,
        "estimated": False,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }

    if cacheable:
        write_cache(cpath, {
            "schema": SCHEMA,
            "hour": hour_iso,
            "window": {
                "from": from_dt.isoformat(sep=" "),
                "to": to_dt.isoformat(sep=" "),
                "minutes_covered": round((to_dt - from_dt).total_seconds() / 60.0, 1),
            },
            "content_hash": digest,
            "content_hash_recipe": result["content_hash_recipe"],
            "line_count": len(entries),
            "fed_line_count": len(texts),
            "input_tokens": tokens_in,
            "tokens_out": tokens_out,
            "title": title,
            "summary": summary,
            "language": language,
            "language_census": census,
            "model": model_name,
            "model_dir": str(model_dir),
            "engine": ENGINE,
            "provider": reload_report,
            "trigger": trigger,
            "partial": partial,
            "generated_at": result["generated_at"],
            "elapsed_seconds": wall_s,
            "load_seconds": round(load_s, 3),
            "chunks": len(chunks),
            "peak_rss_mb": rss,
            "estimated": False,
        })

    _emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
