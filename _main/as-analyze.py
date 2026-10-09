# -*- coding: utf-8 -*-
"""Analise: (a) ha som agora? (b) o UIA expoe algo sobre 'aba a soar'?"""
import json
import io
import sys

OUT = io.open(r"H:\sotto\_main\as-analysis.txt", "w", encoding="utf-8")


def w(s=""):
    OUT.write(s + "\n")


# ---- (a) estado do audio na amostra as-now ----
w("=== (a) amostra as-now: quem soa ===")
for ln in io.open(r"H:\sotto\_main\as-now.jsonl", encoding="utf-8"):
    r = json.loads(ln)
    if r.get("kind") == "probe-summary":
        continue
    for ep in r["endpoints"]:
        for s in ep["sessions"]:
            if s.get("peak") and s["peak"] > 0:
                w("  peak=%.6f pid=%s exe=%s dn=%r state=%s endpoint=%s"
                  % (s["peak"], s.get("pid"), s.get("exe_name"),
                     s.get("display_name"), s.get("state"), ep["name"]))
    w("  source=%s" % (r.get("source") or r.get("source_reason")))

# ---- (b) deep UIA ----
w()
w("=== (b) UIA profundo: o que existe por aba ===")
r = json.load(open(r"H:\sotto\_main\as-tabs-deep.json", encoding="utf-8"))
w("ts=%s n_windows=%s wall=%s cpu=%s rss=%s"
  % (r["ts"], r["n_windows"], r["wall_secs"], r["cpu_secs"], r["rss_mb"]))
pat = {}
for win in r["windows"]:
    w("--- janela pid=%s titulo=%r abas=%d" % (win["pid"], win["window_title"], win["n_tabs"]))
    for t in win["tabs"]:
        d = t.get("deep", {})
        for p in (d.get("supported_patterns") or []):
            pat[p] = pat.get(p, 0) + 1
        kids = d.get("children")
        leg = d.get("legacy")
        w("   sel=%-5s name=%r" % (t["is_selected"], t["name"]))
        w("        patterns=%s" % (d.get("supported_patterns"),))
        w("        children=%s" % (kids,))
        w("        legacy=%s" % (leg,))

w()
w("=== padroes UIA vistos (contagem de abas) ===")
for k, v in sorted(pat.items(), key=lambda x: -x[1]):
    w("  %-45s %d" % (k, v))
OUT.close()
print("written")
