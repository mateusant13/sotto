"""O PORTAO DA JANELA -- o display de duas linhas, contra o payload real.

O QUE JULGA, e de onde vem a verdade: o ficheiro `_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3`
e o json3 que o player do YouTube consome (19 linhas, `rcRows: 2`). A expectativa e
calculada AQUI, a partir dos EVENTOS CRUS -- nao a partir do parser que se esta a
julgar -- e depois comparada com `youtube_window.live_lines` sobre os cues que o
`youtube_captions.parse_json3` produz. Se os dois concordarem em todos os instantes
amostrados, a janela desenha o que o YouTube desenha.

ARM 1  o payload e o que julgamos: 19 linhas, janela rcRows=2 ccCols=40
ARM 2  em cada instante amostrado, as linhas vivas sao as MESMAS e na MESMA ordem
ARM 3  ha instantes com DUAS linhas (a janela rola) e instantes com UMA
ARM 4  a chave muda quando a janela muda e NAO muda quando ela repete
ARM 5  `history_line` nao repete um pedaco que ja esta na linha anterior

BRAcO NEGATIVO (`--neg-arm`): a MESMA bateria com a janela forcada a UMA linha --
ARM 2 e ARM 3 teem de ficar VERMELHOS e o processo sai 1 POR DESENHO. Sem isto o
portao nao provava que ve o defeito que o dono fotografou.

NAO LANCA NADA: le um ficheiro e corre python puro.

    python _main\\youtube-window-oracle.py
    python _main\\youtube-window-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))

FIXTURE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.en-orig.json3")
STEP = 0.1          # o passo da amostra, em segundos
WANT_ROWS = 19


def raw_rows(doc):
    """As linhas do payload, sem passar pelo parser que estamos a julgar."""
    out = []
    for ev in doc.get("events") or ():
        if not isinstance(ev, dict) or ev.get("aAppend"):
            continue
        text = "".join((s.get("utf8") or "") for s in (ev.get("segs") or []) if isinstance(s, dict))
        if not text.strip():
            continue
        out.append({
            "start": float(ev.get("tStartMs") or 0) / 1000.0,
            "end": (float(ev.get("tStartMs") or 0) + float(ev.get("dDurationMs") or 0)) / 1000.0,
            "text": text,
        })
    return out


def raw_window(rows, t, capacity):
    live = [r for r in rows if r["start"] <= t < r["end"]]
    live.sort(key=lambda r: r["start"])
    return [r["text"] for r in live[-capacity:]]


def main(argv=None):
    ap = argparse.ArgumentParser(description="a janela de duas linhas, contra o payload real")
    ap.add_argument("--neg-arm", action="store_true", help="forca a janela a UMA linha (tem de dar vermelho)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    import youtube_captions as yc
    import youtube_window as yw

    # A IMPLEMENTACAO e que e mutada no braco negativo; a EXPECTATIVA fica sempre
    # na capacidade que o payload declara. Se as duas descessem juntas, o mutante
    # passava no ARM 2 -- que e exactamente o defeito que este braco existe para
    # apanhar (uma bateria que se adapta ao mutante nao julga nada).
    capacity = 1 if args.neg_arm else yw.CAPACITY

    doc = json.loads(io.open(FIXTURE, encoding="utf-8").read())
    rows = raw_rows(doc)
    rc = cols = None
    for pos in doc.get("wpWinPositions") or ():
        if isinstance(pos, dict) and pos.get("rcRows"):
            rc, cols = int(pos["rcRows"]), int(pos.get("ccCols") or 0)
    want_capacity = rc or 2

    cues = yc.parse_json3(io.open(FIXTURE, encoding="utf-8").read())

    fails = []
    checks = 0

    def check(name, ok, detail=""):
        nonlocal checks
        checks += 1
        print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  -- " + detail) if detail else ""))
        if not ok:
            fails.append(name)
        return ok

    print("youtube-window-oracle%s" % (" -- NEG-ARM (janela forcada a 1 linha)" if args.neg_arm else ""))
    print("  fixture: %s" % os.path.basename(FIXTURE))
    print("")
    print("ARM 1  o payload e o que julgamos")
    check("1.1 %d linhas de legenda (sem os separadores)" % WANT_ROWS, len(rows) == WANT_ROWS, "got %d" % len(rows))
    check("1.2 o parser do repo ve as mesmas %d" % WANT_ROWS, len(cues) == WANT_ROWS, "got %d" % len(cues))
    check("1.3 janela declarada rcRows=2 ccCols=40", rc == 2 and cols == 40, "rcRows=%s ccCols=%s" % (rc, cols))
    print("")

    print("ARM 2  em cada instante, as mesmas linhas na mesma ordem")
    end = max(r["end"] for r in rows)
    bad = []
    t = 0.0
    n = 0
    while t < end:
        want = raw_window(rows, t, want_capacity)
        got = yw.live_lines(cues, t, capacity)
        n += 1
        if want != got:
            bad.append((round(t, 2), want, got))
        t += STEP
    check("2.1 %d instantes concordam" % n, not bad,
          "" if not bad else "%d divergem; primeiro em t=%.2f want=%r got=%r" % (len(bad), bad[0][0], bad[0][1], bad[0][2]))
    print("")

    print("ARM 3  a janela rola: ha instantes com duas linhas e com uma")
    with_two = sum(1 for i in range(n) if len(raw_window(rows, i * STEP, want_capacity)) >= 2)
    with_one = sum(1 for i in range(n) if len(raw_window(rows, i * STEP, want_capacity)) == 1)
    check("3.1 ha instantes com DUAS linhas (o ecra do YouTube)", with_two > 0,
          "%d de %d amostras (%.0f%%)" % (with_two, n, 100.0 * with_two / n))
    check("3.2 ha instantes com UMA", with_one > 0, "%d de %d" % (with_one, n))
    check("3.3 a primeira linha sozinha em t=0.50", yw.live_lines(cues, 0.50, capacity) == [rows[0]["text"]],
          repr(yw.live_lines(cues, 0.50, capacity)))
    print("")

    print("ARM 4  a chave muda quando a janela muda, e so entao")
    a = yw.window_key(["a", "b"])
    b = yw.window_key(["b", "a"])
    check("4.1 a ordem conta", a != b)
    check("4.2 a repeticao nao", yw.window_key(["a", "b"]) == a)
    keys = []
    t = 0.0
    while t < end:
        keys.append(yw.window_key(yw.live_lines(cues, t, capacity)))
        t += STEP
    distinct = len(set(keys))
    check("4.3 a janela muda %d vezes em %d amostras (nao uma por poll)" % (distinct, len(keys)),
          distinct < len(keys) / 2, "distinct=%d amostras=%d" % (distinct, len(keys)))
    print("")

    print("ARM 5  o historico nao repete o pedaco que ja esta na linha anterior")
    check("5.1 linha repetida entra uma vez", yw.history_line(["fine.", "fine."]) == "fine.",
          repr(yw.history_line(["fine.", "fine."])))
    check("5.2 duas linhas diferentes entram as duas",
          yw.history_line(["I'll be", "fine."]) == "I'll be fine.",
          repr(yw.history_line(["I'll be", "fine."])))
    print("")

    verdict = "PASS" if not fails else "FAIL"
    print("BATTERY-VERDICT youtube-window-oracle %s  checks=%d fail=%d" % (verdict, checks, len(fails)))
    if fails:
        for name in fails:
            print("  RED: %s" % name)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
