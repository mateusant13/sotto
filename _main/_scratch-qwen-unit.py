#!/usr/bin/env python3
"""SCRATCH unit gate for worker/qwen_summary.py's model-independent logic. Deleted after the
receipt quotes it: it exists to prove the cache key, the answer parser, the chunker, the window
resolver and the language census behave, BEFORE any model lands. No model, no download, no audio
device, no window.
"""
import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("qs", r"H:\sotto\worker\qwen_summary.py")
qs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qs)

fails = []
checks = 0


def check(name, got, want):
    global checks
    checks += 1
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got={got!r} want={want!r}")
    if not ok:
        fails.append(name)


print("== parse_answer ==")
check("labels EN", qs.parse_answer("Title: Rindo do jogo\nSummary: a b c d e f."),
      ("Rindo do jogo", "a b c d e f."))
check("labels PT", qs.parse_answer("TÍTULO: Moderação do canal\nRESUMO: um dois três quatro cinco."),
      ("Moderação do canal", "um dois três quatro cinco."))
check("think block stripped",
      qs.parse_answer("Thinking Process:\nblah blah\n\nTitle: X Y\nSummary: one two three four."),
      ("X Y", "one two three four."))
check("unterminated think",
      qs.parse_answer("abc stuff\n</" "think>Title: Pos\nSummary: one two three four five."),
      ("Pos", "one two three four five."))
check("opener with no closer -> None (truncated generation is not a title)",
      qs.parse_answer("<" "think>still reasoning about the transcript and nothing else"),
      None)
check("no labels at all",
      qs.parse_answer("O streamer e a galinha\nprimeira frase segunda frase terceira aqui."),
      ("O streamer e a galinha", "primeira frase segunda frase terceira aqui."))
check("empty -> None", qs.parse_answer(""), None)
check("too-short summary -> None", qs.parse_answer("Title: X\nSummary: ok"), None)
check("12-word title cap",
      len(qs.parse_answer("Title: " + " ".join(f"w{i}" for i in range(20)) +
                          "\nSummary: one two three four five")[0].split()),
      12)
check("markdown bullets cleaned",
      qs.parse_answer("**Title:** Galinha\n**Summary:** one two three four five.")[0],
      "Galinha")
check("heading form '# TITLE' + '# SUMMARY' (this export's real shape; a title's trailing "
      "period is stripped on purpose)",
      qs.parse_answer("# TITLE\nO streamer promete moderadores VIP.\n\n"
                      "# SUMMARY\nO streamer promete botar moderadores VIP. Ele tambem pede "
                      "o link do Discord. E reclama da stream."),
      ("O streamer promete moderadores VIP",
       "O streamer promete botar moderadores VIP. Ele tambem pede o link do Discord. "
       "E reclama da stream."))
check("SUMARIO label is the summary, not part of the title",
      qs.parse_answer("O jogo e insano\nSUMARIO: o jogo e insano e o streamer reclama do "
                      "adversario e pede o link do Discord para a galera do chat.")[1],
      "o jogo e insano e o streamer reclama do adversario e pede o link do Discord para a "
      "galera do chat.")
check("think block stripped, then a single unlabelled line -> None (no summary at all)",
      qs.parse_answer("<" "think>raciocinio aqui</" "think>O streamer falou de moderadores "
                      "e pediu o link do Discord para a galera."), None)

print("\n== content_hash / cache key: hour + content_hash + partial ==")
h = "2026-10-06T16:00:00-03:00"
digest = qs.content_hash("some transcript text")
check("hash is stable + prefixed", qs.content_hash("some transcript text"), digest)
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "16.summary.json"
    record = {"schema": 1, "hour": h, "content_hash": digest, "partial": False,
              "title": "T", "summary": "S", "estimated": False, "model": "m1"}
    qs.write_cache(path, record)
    loaded = qs.read_cache(path)
    check("round trip", loaded["title"], "T")
    check("exact triple -> HIT", qs.cache_hit(loaded, h, digest, False), True)
    check("partial differs -> MISS", qs.cache_hit(loaded, h, digest, True), False)
    check("hash differs -> MISS", qs.cache_hit(loaded, h, "sha256:deadbeef", False), False)
    check("hour differs -> MISS", qs.cache_hit(loaded, "2026-10-06T17:00:00-03:00", digest, False), False)
    check("same model -> HIT", qs.cache_hit(loaded, h, digest, False, "m1"), True)
    check("DIFFERENT model -> MISS (one model's text is never served as another's)",
          qs.cache_hit(loaded, h, digest, False, "m2"), False)
    check("estimated record refused",
          qs.cache_hit({**loaded, "estimated": True}, h, digest, False), False)
    check("record without summary refused",
          qs.cache_hit({**loaded, "summary": ""}, h, digest, False), False)
    check("schema 0 refused", qs.cache_hit({**loaded, "schema": 0}, h, digest, False), False)
    check("unreadable file -> None", qs.read_cache(Path(td) / "nope.json"), None)
    print(f"      sidecar on disk: {path.name} ({path.stat().st_size} B)")

print("\n== chunk_units respects the budget ==")
units = [(300, f"line{i}") for i in range(20)]
chunks = qs.chunk_units(units, 900)
check("chunk count for 6000 tokens @900", len(chunks), 7)
check("every chunk within budget", all(
    sum(c for c, _t in [(300, x) for x in ch]) <= 900 for ch in chunks), True)
check("no text lost", sum(len(ch) for ch in chunks), 20)
big = qs.chunk_units([(5000, "x" * 5000)], 1000)
check("single oversized line is split into SEPARATE chunks", len(big), 5)
check("each split piece is its own chunk", all(len(ch) == 1 for ch in big), True)
check("split pieces are non-empty", all(p for ch in big for p in ch), True)

print("\n== resolve_window ==")


class A:
    hour = "2026-10-06T16"
    now = False
    from_iso = None
    to_iso = None
    trigger = None


f, t, partial, trig = qs.resolve_window(A())
check("--hour whole hour", (f, t), (datetime(2026, 10, 6, 16), datetime(2026, 10, 6, 17)))
check("--hour past -> not partial", partial, False)
check("--hour default trigger", trig, "backfill")


class B:
    hour = None
    now = True
    from_iso = None
    to_iso = None
    trigger = None


f2, t2, partial2, trig2 = qs.resolve_window(B())
check("--now starts at the hour", f2.minute, 0)
check("--now is partial", partial2, True)
check("--now trigger", trig2, "manual")


class C:
    hour = None
    now = False
    from_iso = "2026-10-06T16:00"
    to_iso = "2026-10-06T17:00"
    trigger = None


f3, t3, partial3, trig3 = qs.resolve_window(C())
check("manual full hour -> not partial", partial3, False)


class D:
    hour = None
    now = False
    from_iso = "16:00"
    to_iso = "16:40"
    trigger = "manual"


f4, t4, partial4, _trig = qs.resolve_window(D())
check("bare HH:MM end", t4, datetime.now().replace(hour=16, minute=40, second=0, microsecond=0))
check("sub-hour window is partial", partial4, True)

print("\n== language census ==")
pt_text = ("o streamer falou que não vai liberar os comandos antigos para a galera, "
           "mas eu vou botar meus moderadores vip porque não trabalha muito bem isso aqui")
check("portuguese -> pt", qs.language_census(pt_text)[0], "pt")
en_text = ("so the model needs to run on the cpu and the latency is what we are trying to "
           "measure here, which is not something the plan could know before it ran")
check("english -> en", qs.language_census(en_text)[0], "en")
mix = ("इम्बेड िंग जमा टू सैट्स " + en_text)
check("devanagari for english audio -> en (script cannot name the language)",
      qs.language_census(mix)[0], "en")
check("empty -> pt/empty-window", qs.language_census("")[0], "pt")
lang, ev = qs.language_census("")
check("empty census has the full key set", sorted(ev), sorted(
    ["rule", "script_chars", "non_latin_share", "words", "pt_hits", "en_hits",
     "pt_diacritics", "pt_score", "en_score", "fallback"]))
check("ambiguous -> pt", qs.language_census("a b c d e f g h")[0], "pt")

print("\n== prompt builder ==")
prompt = qs.build_prompt("TRANSCRIPT BODY", "pt")
check("chatml markers", prompt.count("<|im_start|>"), 3)
check("assistant turn is last", prompt.rstrip().endswith("<|im_start|>assistant"), True)
check("language hint present", "Portuguese" in prompt, True)
fold = qs.build_prompt("NEXT", "en", running="SUMMARY SO FAR")
check("fold carries the running summary", "SUMMARY SO FAR" in fold and "English" in fold, True)

print(f"\n=== {checks} check(s), {len(fails)} failure(s) ===")
if fails:
    print("FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
