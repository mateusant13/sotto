# -*- coding: utf-8 -*-
"""Censo do GetDisplayName em TODAS as amostras recolhidas: quem define nome?"""
import glob
import io
import json
import collections

OUT = io.open(r"H:\sotto\_main\as-displayname-census.txt", "w", encoding="utf-8")


def w(s=""):
    OUT.write(s + "\n")


files = [
    r"H:\sotto\_main\as-run1.jsonl",
    r"H:\sotto\_main\as-control.jsonl",
    r"H:\sotto\_main\as-corr.jsonl",
    r"H:\sotto\_main\as-once.jsonl",
    r"H:\sotto\_main\as-now.jsonl",
]
samples = 0
reads = 0
nonempty = collections.Counter()      # display_name nao vazio -> quantas sessoes
per_exe = collections.Counter()       # (exe, dn vazio?) contagem
chrome_dn = collections.Counter()
chrome_peak_dn = collections.Counter()
for f in files:
    try:
        fh = io.open(f, encoding="utf-8")
    except OSError:
        continue
    for ln in fh:
        r = json.loads(ln)
        if r.get("kind") in ("probe-summary",):
            continue
        samples += 1
        for ep in r.get("endpoints", []):
            for s in ep.get("sessions", []):
                if not s.get("peak_available"):
                    continue
                reads += 1
                dn = s.get("display_name")
                exe = s.get("exe_name") or ("<pid %s>" % s.get("pid"))
                per_exe[(exe, dn == "" if dn is not None else None)] += 1
                if dn:
                    nonempty[(exe, dn)] += 1
                if exe == "chrome.exe":
                    chrome_dn[repr(dn)] += 1
                    if s.get("peak"):
                        chrome_peak_dn[(repr(dn), s["peak"] > 0.001)] += 1
    fh.close()

w("ficheiros: %s" % ", ".join(f.split("\\")[-1] for f in files))
w("amostras=%d  leituras de meter=%d" % (samples, reads))
w()
w("=== TODOS os display_name NAO vazios vistos (exe, valor) -> leituras ===")
for k, v in nonempty.most_common():
    w("  %-28s %-60r %d" % (k[0], k[1], v))
w()
w("=== sessoes do chrome: display_name -> leituras ===")
for k, v in chrome_dn.most_common():
    w("  dn=%-8s %d" % (k, v))
w()
w("=== chrome: (display_name, peak>0.001) -> leituras ===")
for k, v in chrome_peak_dn.most_common():
    w("  dn=%-8s soando=%-5s %d" % (k[0], k[1], v))
w()
w("=== por exe: leituras com dn vazio / dn presente ===")
agg = collections.Counter()
for (exe, empty), c in per_exe.items():
    agg[(exe, "vazio" if empty else "presente")] += c
for k, v in sorted(agg.items()):
    w("  %-28s %-9s %d" % (k[0], k[1], v))
OUT.close()
print("written")
