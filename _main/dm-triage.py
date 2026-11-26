#!/usr/bin/env python3
"""dm-triage - triage ONE watcher DM by re-measuring it, not by restating it.

Usage:
    python _main/dm-triage.py <dm-file> > reply.md
    python _main/dm-triage.py <dm-file> --window 5 --facts-only

The reply body goes to stdout (so it can be fed straight to
`herdr-dm.py --body-file`). Machine facts go to stderr. Nothing is written
to the mailbox: this tool only READS one DM file and the live process table.

Classes: STUTTER-cpu | STUTTER-io | COMMIT-pressure | RELIEF/refutation.
Every non-refusal body carries: identity (parent chain), the ceiling quoted
with its source line, the measured pair (DM number vs measured number with a
declared window), the mechanism, what was done, and one explicit verdict.

Refusals (exit 3, no body):
    DM-TRIAGE CANNOT-MEASURE why=dead-pid|unparsed-section|counters-unreadable
A foreign tree is a SOFT refusal (exit 0): the metric cannot be measured on a
process I do not own, so the body refuses by name and ends MISATTRIBUTED.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

MB = 1024.0 * 1024.0
GIB = 1024.0**3

FIELD_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_ .]*?)\s*=\s*(.*)$")
PID_RE = re.compile(r"([A-Za-z0-9_.-]+\.(?:exe|EXE))\((\d+)\)")
NUM_RE = r"([0-9]+(?:\.[0-9]+)?)"

DEFAULT_ROOT = r"H:\sotto"
MAX_TREE = 64


class Refusal(Exception):
    """A named, non-conversational refusal to answer a DM."""

    def __init__(self, why: str, detail: str = "") -> None:
        self.why = why
        self.detail = detail
        super().__init__(why)


@dataclass
class Claim:
    metric: str  # "io" | "cpu" | "commit"
    value: float
    unit: str
    raw: str
    window_s: float
    source_line: int


@dataclass
class Ceiling:
    text: str
    source: str  # "DM line N" or "NOT DECLARED in DM"


@dataclass
class Sample:
    pid: int
    name: str
    read: int
    write: int
    read_ops: int
    write_ops: int
    cpu_s: float
    private: int
    rss: int
    thread_cpu: dict[int, float] | None


@dataclass
class Measurement:
    elapsed_s: float
    pids: list[int]
    read_mb_s: float
    write_mb_s: float
    ops_s: float
    cpu_pct: float
    private_gib: float
    rss_gib: float
    cumulative_read_mb: float
    cumulative_write_mb: float
    cumulative_ops: int
    top_threads: list[tuple[int, float]]
    dropped: list[int] = field(default_factory=list)


def parse_fields(text: str) -> tuple[dict[str, str], dict[str, int]]:
    """Every `key = value` line, including indented multi-line continuations."""
    lines = text.splitlines()
    fields: dict[str, str] = {}
    at: dict[str, int] = {}
    i = 0
    while i < len(lines):
        m = FIELD_RE.match(lines[i])
        if not m:
            i += 1
            continue
        key, value = m.group(1).strip(), m.group(2).strip()
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if (
                not nxt.strip()
                or FIELD_RE.match(nxt)
                or not nxt[:1].isspace()
                or nxt.lstrip().startswith(("#", "->", "=>", "---"))
            ):
                break
            value += " " + nxt.strip()
            j += 1
        fields.setdefault(key, value)
        at.setdefault(key, i + 1)
        i = j
    return fields, at


def parse_chain(value: str) -> list[tuple[str, int]]:
    seen: set[int] = set()
    out: list[tuple[str, int]] = []
    for name, pid in PID_RE.findall(value or ""):
        n = int(pid)
        if n not in seen:
            seen.add(n)
            out.append((name, n))
    return out


def first_line_with(lines: list[str], needle: str) -> int:
    """1-based line number of the first line containing `needle` (0 when absent)."""
    low = needle.lower()
    for i, line in enumerate(lines, 1):
        if low in line.lower():
            return i
    return 0


def classify(subject: str, text: str) -> str:
    s = subject.lower()
    head = text[:2000].lower()
    if (
        s.startswith("relief")
        or s.startswith("re:")
        or s.startswith("measured:")
        or "refuted" in s
        or "## answer: refuted" in head
        or "## advisory" in head
    ):
        return "RELIEF/refutation"
    if s.startswith("commit") or "private-commit reservation" in head:
        return "COMMIT-pressure"
    if s.startswith("stutter") or "stutter" in s:
        # A DM QUE SE DECLARA CANNOT-MEASURE NAO TEM TAXA (medido 2026-11-26,
        # dm-81956dec: `signals: tick-gap, not-scheduled`). O numero amostrado e'
        # uma POSICAO NA FILA, e o proprio watcher diz isso. Inventar uma taxa
        # aqui seria a mentira que a DM recusa; o que sobra e' a IDENTIDADE.
        if "cannot-measure" in s:
            return "STUTTER-unmeasured"
        io_marks = ("mb/s", "ops/s", " io ", "logical i/o")
        return "STUTTER-io" if any(x in s for x in io_marks) else "STUTTER-cpu"
    return ""


def find_claim(class_name: str, subject: str, fields: dict[str, str], at: dict[str, int],
               lines: list[str]) -> Claim:
    subj_line = first_line_with(lines, "subject:") or 1
    if class_name == "COMMIT-pressure":
        numbers = fields.get("numbers", "")
        m = re.search(r"private\s*=\s*" + NUM_RE + r"\s*(GB|GiB)", numbers, re.I)
        if not m:
            raise Refusal("unparsed-section", f"line={at.get('numbers', 0)} text={numbers!r}")
        return Claim("commit", float(m.group(1)), m.group(2).upper(), numbers.strip(),
                     0.0, at.get("numbers", 0))

    if class_name in ("STUTTER-io", "RELIEF/refutation"):
        m = re.search(r"\b(?:io\s+)?" + NUM_RE + r"\s*MB/s", subject, re.I)
        if m:
            window = parse_window(subject, fields)
            return Claim("io", float(m.group(1)), "MB/s", m.group(0).strip(), window, subj_line)
        m = re.search(r"\b" + NUM_RE + r"\s*% of (?:one core|machine)", subject, re.I)
        if m:
            unit = "% " + m.group(0).split("%", 1)[1].strip()
            return Claim("cpu", float(m.group(1)), unit, m.group(0).strip(),
                         parse_window(subject, fields), subj_line)

    if class_name == "STUTTER-unmeasured":
        return Claim("identity", 0.0, "unmeasured", subject.strip(), 0.0, subj_line)

    if class_name == "STUTTER-cpu":
        m = re.search(r"\bcpu\s+" + NUM_RE + r"\s*%", subject, re.I)
        if m:
            return Claim("cpu", float(m.group(1)), "% of one core", m.group(0).strip(),
                         parse_window(subject, fields), subj_line)

    raise Refusal("unparsed-section", f"line={subj_line} text={subject!r}")


def parse_window(subject: str, fields: dict[str, str]) -> float:
    for text in (subject, fields.get("window", "")):
        m = re.search(NUM_RE + r"\s*s\b", text, re.I)
        if m:
            return float(m.group(1))
    return 60.0


def find_ceiling(lines: list[str], fields: dict[str, str], at: dict[str, int]) -> Ceiling:
    if "ceiling" in fields and fields["ceiling"].strip():
        return Ceiling(fields["ceiling"].strip(), f"DM line {at['ceiling']}")
    # Some DMs (COMMIT, cooperative RELIEF) carry no `ceiling =` field. Quote the
    # strongest cap line the DM actually has, with its line number; never invent one.
    for i, line in enumerate(lines, 1):
        if re.search(r"--cpu\s+\d+|--io\s+[a-z-]+|--jobs|OMP_NUM_THREADS|budget_", line, re.I):
            return Ceiling(line.strip(), f"DM line {i}")
    return Ceiling("NOT DECLARED in this DM (no `ceiling =` field and no cap token in argv)",
                   "DM: no ceiling line")


def live_chain(pid: int, limit: int = 10) -> list[tuple[str, int, str]]:
    """name, pid, cwd (or an AccessDenied marker) from the live parent chain."""
    out: list[tuple[str, int, str]] = []
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return out
    for _ in range(limit):
        try:
            name, ppid = proc.name(), proc.pid
            try:
                cwd = proc.cwd()
            except (psutil.AccessDenied, psutil.Error) as exc:
                cwd = f"UNREADABLE({type(exc).__name__})"
            out.append((name, ppid, cwd))
            parent = proc.parent()
            if parent is None or parent.pid == ppid:
                break
            proc = parent
        except psutil.NoSuchProcess:
            break
    return out


def owns(chain: list[tuple[str, int, str]], root: str) -> bool:
    """One owning predicate: a live name/pid/cwd/cmdline must name the project root."""
    r = root.replace("/", "\\").rstrip("\\").casefold()
    if not r:
        return False
    for name, pid, cwd in chain:
        if r in cwd.casefold():
            return True
        try:
            cmd = " ".join(psutil.Process(pid).cmdline())
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
            cmd = ""
        if r in cmd.casefold():
            return True
    return False


def my_pid_owned(root: str) -> tuple[int, list[tuple[str, int, str]]]:
    chain = live_chain(os.getpid())
    return os.getpid(), chain


def named_owned_pid(chain: list[tuple[str, int, str]], root: str, mine: int,
                    oldest: bool = False) -> int:
    """An owned pid from the chain. `oldest` selects a stable ancestor, not this run's pid."""
    r = root.replace("/", "\\").rstrip("\\").casefold()
    for name, pid, cwd in (list(reversed(chain)) if oldest else chain):
        if r in cwd.casefold():
            return pid
        try:
            if r in " ".join(psutil.Process(pid).cmdline()).casefold():
                return pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
            pass
    return mine


def sample(pid: int) -> Sample:
    try:
        p = psutil.Process(pid)
        io = p.io_counters()
        cpu = p.cpu_times()
        mem = p.memory_info()
        private = int(getattr(mem, "private", 0) or 0)
        rss = int(getattr(mem, "rss", 0) or 0)
        try:
            threads = {t.id: t.user_time + t.system_time for t in p.threads()}
        except (psutil.AccessDenied, psutil.Error):
            threads = None
        read_ops = int(getattr(io, "read_count", getattr(io, "read_ops", 0)))
        write_ops = int(getattr(io, "write_count", getattr(io, "write_ops", 0)))
        return Sample(pid, p.name(), io.read_bytes, io.write_bytes,
                      read_ops, write_ops, cpu.user + cpu.system,
                      private, rss, threads)
    except psutil.NoSuchProcess as exc:
        raise Refusal("dead-pid", f"pid={pid}") from exc
    except psutil.AccessDenied as exc:
        raise Refusal("counters-unreadable", f"pid={pid} exception={type(exc).__name__}") from exc


def measure(pids: list[int], window_s: float) -> Measurement:
    if not pids:
        raise Refusal("counters-unreadable", "pid=none (no live pid in DM chain)")
    before = {pid: sample(pid) for pid in pids}
    t0 = time.monotonic()
    time.sleep(window_s)
    elapsed = time.monotonic() - t0

    read_d = write_d = ops_d = cpu_d = 0.0
    private = rss = cumulative_r = cumulative_w = 0
    cumulative_ops = 0
    top: list[tuple[int, float]] = []
    dropped: list[int] = []
    after_pids: list[int] = []
    for pid, b in before.items():
        try:
            a = sample(pid)
        except Refusal as exc:
            if exc.why == "dead-pid":
                dropped.append(pid)
                continue
            raise
        after_pids.append(pid)
        read_d += max(0, a.read - b.read)
        write_d += max(0, a.write - b.write)
        ops_d += max(0, (a.read_ops + a.write_ops) - (b.read_ops + b.write_ops))
        cpu_d += max(0.0, a.cpu_s - b.cpu_s)
        private += a.private
        rss += a.rss
        cumulative_r += a.read
        cumulative_w += a.write
        cumulative_ops += a.read_ops + a.write_ops
        if a.thread_cpu is not None and b.thread_cpu is not None:
            for tid, t_before in b.thread_cpu.items():
                t_after = a.thread_cpu.get(tid)
                if t_after is not None:
                    top.append((tid, max(0.0, t_after - t_before) / elapsed * 100.0))
    top.sort(key=lambda pair: pair[1], reverse=True)
    return Measurement(elapsed, after_pids, read_d / MB / elapsed, write_d / MB / elapsed,
                       ops_d / elapsed, cpu_d / elapsed * 100.0, private / GIB, rss / GIB,
                       cumulative_r / MB, cumulative_w / MB, cumulative_ops,
                       top[:3], dropped)


def tree_pids(pid: int) -> list[int]:
    """Culprit plus its live descendants (terminal HOSTs own their children's I/O)."""
    pids = [pid]
    try:
        children = psutil.Process(pid).children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
        return pids
    for child in children[:MAX_TREE]:
        if child.pid not in pids:
            pids.append(child.pid)
    return pids


def impossible(claim: Claim, m: Measurement) -> tuple[bool, str]:
    """A quoted rate cannot exceed what the process has EVER moved / burned."""
    if claim.metric == "io":
        needed = claim.value * MB * max(claim.window_s, 1.0)
        have = (m.cumulative_read_mb + m.cumulative_write_mb) * MB
        if needed > have * 1.05:
            return True, (f"{claim.value:g} MB/s x {claim.window_s:g} s = "
                          f"{needed / MB:,.0f} MB required against "
                          f"{have / MB:,.1f} MB ever moved by the live tree")
    if claim.metric == "cpu":
        needed = claim.value / 100.0 * max(claim.window_s, 1.0)
        # Cumulative CPU of the tree is not re-read here; only the windowed rate is
        # available, so a past spike is never called impossible on CPU alone.
        if needed <= 0:
            return True, "non-positive CPU claim"
    return False, ""


def culprit_from_body(lines: list[str]) -> tuple[str, int, int]:
    """Cooperative RELIEF cards use `Measured tree:`; advisories use a code block."""
    seps = [i for i, line in enumerate(lines) if line.strip() == "---"]
    start = seps[1] + 1 if len(seps) >= 2 else 0
    pat = re.compile(r"Measured tree:\s*([A-Za-z0-9_.-]+\.exe)\((\d+)\)", re.I)
    for i in range(start, len(lines)):
        m = pat.search(lines[i])
        if m:
            return m.group(1), int(m.group(2)), i + 1
    for i in range(start, len(lines)):
        m = PID_RE.search(lines[i])
        if m:
            return m.group(1), int(m.group(2)), i + 1
    return "", 0, 0


def render_body(dm: dict, root: str, mine: int, my_chain: list[tuple[str, int, str]],
                verdict: str, measured: Measurement | None, soft_refusal: str,
                claim: Claim, ceiling: Ceiling, live: list[tuple[str, int, str]],
                culprit_pid: int, culprit_name: str, refute_basis: str) -> str:
    owned_pid = (named_owned_pid(live, root, mine) if verdict != "MISATTRIBUTED"
                 else named_owned_pid(my_chain, root, mine, oldest=True))
    out: list[str] = []
    out.append(f"RE: {dm['id']} — {dm['class']} — verdict {verdict}")
    out.append("")
    if soft_refusal:
        out.append(f"DM-TRIAGE CANNOT-MEASURE {soft_refusal}")
        out.append("")
        out.append("   (the refusal is to ownership; the numbers below are a read-only "
                   "re-measurement for the census.)")

    out.append("1. IDENTITY — is the pid mine (parent chain walked live)")
    if live:
        for name, pid, cwd in live:
            mark = " <— accused" if pid == culprit_pid else ""
            out.append(f"   {name}({pid}) cwd={cwd}{mark}")
    else:
        out.append(f"   {culprit_name}({culprit_pid}) GONE at read time")
    out.append(f"   owning predicate: cwd/cmdline contains {root}")
    out.append(f"   {'MINE' if verdict != 'MISATTRIBUTED' else 'FOREIGN TREE'}; "
               f"the pid I do own is {owned_pid} "
               f"({my_chain[-1][0]} is the root of this triage process's chain).")
    out.append("")

    out.append("2. CEILING — quoted, with its source")
    out.append(f"   {ceiling.text}")
    out.append(f"   source: {ceiling.source}")
    out.append("")

    out.append("3. MEASURED PAIR — the DM's number vs mine, declared window")
    out.append(f"   DM:     {claim.raw} [{claim.unit}, quoted window {claim.window_s:g} s] "
               f"(DM line {claim.source_line})")
    if "machine" in claim.unit:
        ncpu = psutil.cpu_count() or 1
        out.append(f"   NOTE: the DM's denominator is the whole machine ({ncpu} logical "
                   f"CPUs): {claim.value:g}% of machine = {claim.value * ncpu:.1f}% of one "
                   f"core; my row below is % of ONE core.")
    if measured is None:
        out.append("   mine:   NO READING — see the named refusal above; a dead/foreign "
                   "process cannot be re-measured.")
    else:
        if claim.metric == "io":
            out.append(f"   mine:   io {measured.read_mb_s:.3f} MB/s read + "
                       f"{measured.write_mb_s:.3f} MB/s write, "
                       f"{measured.ops_s:,.1f} ops/s over {measured.elapsed_s:.2f} s "
                       f"({len(measured.pids)} live pid(s))")
        elif claim.metric == "cpu":
            top = ", ".join(f"tid={tid} {pct:.2f}%" for tid, pct in measured.top_threads)
            out.append(f"   mine:   cpu {measured.cpu_pct:.2f}% of one core over "
                       f"{measured.elapsed_s:.2f} s ({len(measured.pids)} live pid(s)); "
                       f"per-thread: {top or 'UNREADABLE'}")
        else:
            out.append(f"   mine:   private {measured.private_gib:.3f} GiB, "
                       f"rss {measured.rss_gib:.3f} GiB over {measured.elapsed_s:.2f} s "
                       f"({len(measured.pids)} live pid(s))")
        out.append(f"   cumulative whole-life: read {measured.cumulative_read_mb:,.1f} MB, "
                   f"write {measured.cumulative_write_mb:,.1f} MB, "
                   f"ops {measured.cumulative_ops:,}")
        if measured.dropped:
            out.append(f"   died during the window: {measured.dropped} (not counted)")
        if refute_basis:
            out.append(f"   arithmetic check: {refute_basis}")
    out.append("")

    out.append("4. MECHANISM")
    out.append("   " + mechanism(dm, claim, measured))
    out.append("")

    out.append("5. WHAT I DID ABOUT IT")
    out.append("   " + action(verdict, owned_pid, ceiling))
    out.append("")

    out.append(f"6. VERDICT: {verdict}")
    out.append(f"   my pid: {owned_pid}; no DM was sent and no mailbox file was written by "
               "this tool.")
    return "\n".join(out) + "\n"


def mechanism(dm: dict, claim: Claim, m: Measurement | None) -> str:
    if claim.metric == "identity":
        return ("the DM refuses its own rate (`CANNOT-MEASURE`), so no rate is judged. "
                "What the DM does assert is identity and chain, and that is what this "
                "tool checked against the owning tree.")
    if claim.metric == "commit":
        ratio = (claim.value / 0.16) if claim.value else 0.0
        return (f"private commit is a pagefile-backed reservation, not touched pages "
                f"(DM private/rss ratio {ratio:.1f}x); emptying the working set does not "
                f"release it. Only the owning process exiting or shrinking the pool "
                f"returns it; closing idle panes is the owner's decision.")
    if claim.metric == "cpu":
        if m and m.top_threads:
            return (f"cpu is billed per thread; the live top thread(s) are "
                    f"{', '.join(f'tid={t} {p:.2f}%' for t, p in m.top_threads)}. "
                    f"A detection-time ranking is not proof of cause: re-measure before "
                    f"refuting a past spike.")
        return ("cpu burn is per-thread and kernel-billed; psutil could not name the "
                "threads, so no per-thread claim is made.")
    if m and m.ops_s > 0:
        per_op = (m.read_mb_s + m.write_mb_s) * MB / m.ops_s
        if per_op < 2000:
            return (f"{per_op:,.0f} bytes/op — small-op page-cache and pipe traffic, not a "
                    "disk copy (compare the DM's DEVICE block: per-volume bytes are "
                    "machine-wide context, not this tree's counters).")
        return (f"{per_op:,.0f} bytes/op — large sequential I/O; the DEVICE block decides "
                "whether a volume was actually busy.")
    return "logical process I/O (page-cache hits and both pipe ends), not disk traffic."


def action(verdict: str, owned_pid: int, ceiling: Ceiling) -> str:
    if verdict == "MISATTRIBUTED":
        return (f"no lever applied to a foreign tree; the census must be corrected with my "
                f"pid {owned_pid} and the live chain above. This tool only measured.")
    if verdict == "REFUTE":
        return ("no placement lever applied; the quoted rate is bounded by the accused's "
                "own cumulative counters and should be published as UNPROVEN, not halved.")
    return (f"no cap, trim, suspend or kill applied: the ceiling is already quoted above "
            f"({ceiling.source}). The remaining lever is at the source (fewer/cheaper "
            "steps), not in the governor; this tool only measured.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dm_file", type=Path, help="one herdr-inbox DM markdown file")
    ap.add_argument("--window", type=float, default=5.0,
                    help="declared re-measurement window in seconds (default 5)")
    ap.add_argument("--root", default=os.environ.get("DM_TRIAGE_ROOT", DEFAULT_ROOT),
                    help="project root used by the owning predicate")
    ap.add_argument("--facts-only", action="store_true",
                    help="print only parse-derived, deterministic facts (no live sampling)")
    args = ap.parse_args(argv)

    if args.window <= 0:
        print("DM-TRIAGE CANNOT-MEASURE why=unparsed-section detail=window-must-be-positive")
        return 3
    try:
        text = args.dm_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"DM-TRIAGE CANNOT-MEASURE why=unparsed-section detail=unreadable:{exc}")
        return 3

    lines = text.splitlines()
    fields, at = parse_fields(text)
    subject_match = re.search(r"^subject:\s*(.*)$", text, re.M)
    subject = subject_match.group(1).strip() if subject_match else ""
    dm_id = fields.get("id") or args.dm_file.stem
    class_name = classify(subject, text)
    if not class_name:
        line = first_line_with(lines, "subject:") or 1
        print(f"DM-TRIAGE CANNOT-MEASURE why=unparsed-section "
              f"line={line} text={subject!r}")
        return 3

    culprit = fields.get("culprit", "")
    chain_dm = parse_chain(culprit) or parse_chain(fields.get("chain", ""))
    culprit_line = at.get("culprit", 0)
    culprit_text = fields.get("culprit", "")
    if not chain_dm:
        name, pid, ln = culprit_from_body(lines)
        if name:
            chain_dm = [(name, pid)]
            culprit_line, culprit_text = ln, lines[ln - 1].strip()
    if not chain_dm:
        line = culprit_line or first_line_with(lines, "subject:") or 1
        print(f"DM-TRIAGE CANNOT-MEASURE why=unparsed-section "
              f"line={line} text={culprit_text!r}")
        return 3
    culprit_name, culprit_pid = chain_dm[0]
    chain_all = parse_chain(fields.get("chain", "")) or chain_dm

    try:
        claim = find_claim(class_name, subject, fields, at, lines)
    except Refusal as exc:
        print(f"DM-TRIAGE CANNOT-MEASURE why={exc.why} {exc.detail}")
        return 3
    ceiling = find_ceiling(lines, fields, at)

    mine, my_chain = my_pid_owned(args.root)
    live = live_chain(culprit_pid)
    mine_tree = bool(live) and owns(live, args.root)
    proof = "culprit-pid"
    if not live:
        # O CULPADO MORTO AINDA TEM DONO, e a prova esta na PROPRIA cadeia da DM:
        # os ancestrais declarados nela continuam vivos e dizem de quem era o
        # passo. MEDIDO 2026-11-26 (dm-81956dec): pid 72760 morto, e
        # `python.exe(52096)` (o ceiling que a DM cita) + `cmd.exe(92652)` = a
        # minha bateria. Sem esta metade um DM verdadeiro sai `owned=no` so'
        # porque o passo terminou antes da pergunta.
        for _n, _p in chain_all[1:]:
            _anc = live_chain(_p)
            if _anc and owns(_anc, args.root):
                mine_tree, live, proof = True, _anc, "ancestor-pid=%d" % _p
                break
    # UM PID MORTO NAO E' UM PID ALHEIO (medido 2026-11-26): `MISATTRIBUTED`
    # afirma que a arvore e' de outro; com o culpado morto e nenhum ancestral
    # vivo desse lado, essa afirmacao nao se prova e o nome honesto e' `UNKNOWN`.
    if mine_tree:
        verdict = "ACCEPT"
    else:
        verdict = "UNKNOWN" if not live else "MISATTRIBUTED"

    facts = [
        f"DM-TRIAGE dm={dm_id} class={class_name} culprit={culprit_name}({culprit_pid}) "
        f"alive={'yes' if live else 'no'} owned={'yes' if mine_tree else 'no'} "
        f"verdict-chain={verdict} proof={proof}",
        f"DM-TRIAGE claim={claim.raw!r} metric={claim.metric} window={claim.window_s:g}s "
        f"source=DM line {claim.source_line}",
        f"DM-TRIAGE ceiling={ceiling.text!r} source={ceiling.source}",
        f"DM-TRIAGE dm-chain=" + " <- ".join(f"{n}({p})" for n, p in chain_all),
        f"DM-TRIAGE live-chain=" + " <- ".join(f"{n}({p})" for n, p, _ in live),
        f"DM-TRIAGE my-pid={mine} my-chain=" + " <- ".join(f"{n}({p})" for n, p, _ in my_chain),
        f"DM-TRIAGE my-owned-pid={named_owned_pid(my_chain, args.root, mine, oldest=True)} "
        f"(stable ancestor in this tool's chain)",
    ]
    if args.facts_only:
        print("\n".join(facts[:5] + [facts[6]]))
        return 0

    if claim.metric == "identity":
        # A identidade E' a resposta que existe; a taxa fica RECUSADA pelo nome,
        # nunca um 0,0 disfarcado de medicao.
        print("\n".join(facts), file=sys.stderr)
        print(f"DM-TRIAGE CANNOT-MEASURE why=no-rate-in-claim class={class_name} "
              f"culprit={culprit_name}({culprit_pid}) "
              f"alive={'yes' if live else 'no'} owned={'yes' if mine_tree else 'no'} "
              f"verdict-chain={verdict} proof={proof} refute=nothing-to-refute")
        return 0

    if not live:
        print(f"DM-TRIAGE CANNOT-MEASURE why=dead-pid line={culprit_line} "
              f"text={culprit_text!r} pid={culprit_pid}")
        return 3

    soft = ""
    measured: Measurement | None = None
    refute_basis = ""
    try:
        measured = measure(tree_pids(culprit_pid), args.window)
    except Refusal as exc:
        print(f"DM-TRIAGE CANNOT-MEASURE why={exc.why} {exc.detail} "
              f"line={culprit_line} text={culprit_text!r}")
        return 3
    bad, refute_basis = impossible(claim, measured)
    if bad and mine_tree:
        verdict = "REFUTE"
    if bad:
        facts.append(f"DM-TRIAGE refute-basis={refute_basis}")
    if not mine_tree:
        soft = (f"why=foreign-tree line={culprit_line} pid={culprit_pid} "
                f"root={args.root}")

    dm = {"id": dm_id, "class": class_name}
    body = render_body(dm, args.root, mine, my_chain, verdict, measured, soft, claim,
                       ceiling, live, culprit_pid, culprit_name, refute_basis)
    print("\n".join(facts + ([f"DM-TRIAGE status={soft.split()[0]} {soft}"]
                             if soft else [f"DM-TRIAGE status=OK verdict={verdict}"])),
          file=sys.stderr)
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
