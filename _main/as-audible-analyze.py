# -*- coding: utf-8 -*-
"""O UIA consegue dizer QUAL aba soa? Correlaciona, amostra a amostra, o meter
WASAPI da sessao do navegador com as abas cujo indicador de audio esta LAYOUTADO."""
import io
import json

OUT = io.open(r"H:\sotto\_main\as-audible-analysis.txt", "w", encoding="utf-8")


def w(s=""):
    OUT.write(s + "\n")


recs = []
for ln in io.open(r"H:\sotto\_main\as-audible.jsonl", encoding="utf-8"):
    r = json.loads(ln)
    if r.get("kind") == "audible-probe-summary":
        w("SUMMARY %s" % json.dumps(r))
        continue
    recs.append(r)

w("amostras=%d" % len(recs))
w()
w("seq | ts | browser_peak | abas com indicador layoutado (w>0)")
w("-" * 120)
sounding = 0
for r in recs:
    laid = []
    for win in r["windows"]:
        for t in win["tabs"]:
            ind = t.get("ind")
            if isinstance(ind, list) and len(ind) == 6 and ind[4] > 0 and ind[5] > 0:
                laid.append("%s%s" % ("*" if t["is_selected"] else "", t["name"][:58]))
    if r["browser_peak"] > 0.001:
        sounding += 1
    w("%4d | %s | %.6f | %d: %s" % (r["seq"], r["ts"][11:23], r["browser_peak"],
                                    len(laid), " | ".join(laid)))
w("-" * 120)
w("amostras com browser_peak>0.001 : %d de %d" % (sounding, len(recs)))
# quantas abas layoutadas em amostras sem som vs com som
import collections
c = collections.Counter()
for r in recs:
    laid = 0
    for win in r["windows"]:
        for t in win["tabs"]:
            ind = t.get("ind")
            if isinstance(ind, list) and len(ind) == 6 and ind[4] > 0 and ind[5] > 0:
                laid += 1
    c[(r["browser_peak"] > 0.001, laid)] += 1
w()
w("(soando?, n_abas_com_indicador_layoutado) -> amostras")
for k, v in sorted(c.items()):
    w("  %s -> %d" % (k, v))
OUT.close()
print("written")
