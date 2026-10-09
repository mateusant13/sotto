# -*- coding: utf-8 -*-
"""O AlertIndicatorButton distingue a aba que SOA? Compara geometria/estado
entre abas, com controlo positivo (abas que nao podem soar: Nova guia / erro)."""
import io
import json

r = json.load(open(r"H:\sotto\_main\as-tabs-deep2.json", encoding="utf-8"))
OUT = io.open(r"H:\sotto\_main\as-indicator.txt", "w", encoding="utf-8")


def w(s=""):
    OUT.write(s + "\n")


w("aba (nome) | sel | indicador: nome / offscreen / rect / legacy_state")
w("=" * 130)
for win in r["windows"]:
    w("### janela pid=%s titulo=%r  abas=%d" % (win["pid"], win["window_title"], win["n_tabs"]))
    for t in win["tabs"]:
        kids = t.get("deep", {}).get("children")
        if not isinstance(kids, list):
            w("  %-70s sel=%-5s children=%s" % (t["name"][:70], t["is_selected"], kids))
            continue
        ind = [k for k in kids if k.get("class_name") == "AlertIndicatorButton"]
        close = [k for k in kids if k.get("class_name") == "TabCloseButton"]
        kind = "BROWSER-TAB" if close else "page-tab (sem TabCloseButton)"
        if not ind:
            w("  %-70s sel=%-5s [%s] SEM AlertIndicatorButton" % (t["name"][:70], t["is_selected"], kind))
        else:
            i = ind[0]
            w("  %-70s sel=%-5s [%s] ind=%r offscreen=%s rect=%s legacy_state=%s"
              % (t["name"][:70], t["is_selected"], kind, i["name"], i["is_offscreen"],
                 i["bounding_rect"], i["legacy_state"]))
OUT.close()
print("written")
