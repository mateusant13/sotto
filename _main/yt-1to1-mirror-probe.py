"""A PROVA 1:1 AO VIVO -- a nossa linha e a linha que o YouTube esta a pintar.

Duas leituras independentes, no MESMO instante:

  A) O QUE O PLAYER PINTA -- as palavras da caption-window do player
     (UI Automation), lidas pelo proprio probe.

  B) O QUE A NOSSA APP DECIDIU -- as linhas `YOUTUBE_CAPTION` do log da app,
     que carregam a cue, o instante e a faixa que a app escolheu.

E o que se compara e o que o dono vai comparar com os olhos: as palavras que
o YouTube esta a pintar tem de ser o COMECO da linha que a nossa app
mostrou nesse instante.

PORQUE ISTO E NECESSARIO (medido 2026-10-20, no Chrome do dono):
  * o relogio do player esta GELADO (+0.00 s em 8.35 s de relogio de
    parede) -- a app lia t=2.0 com o video em t=530;
  * a caption-window nao expoe idioma (0 de 448 elementos com UIA 30007), e
    a app servia a faixa pela preferencia de idioma: `pt-orig` enquanto o
    player pintava `en-orig`.

So a linha tem de vir da PINTURA, e a faixa tem de ser a que CONTEM a
pintura. Este probe fecha o circulo com numeros.

Read-only: nao lanca a app, nao abre o browser, nao renderiza audio.

Uso:
    python _main/yt-1to1-mirror-probe.py --log I:\\cc-tmp\\sotto-XXXXXX.log --seconds 60
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))

#: A LINHA QUE A APP DECIDIU. O formato e o que a shell escreve (ver
#: `sotto_webview.py`, o caminho-espelho).
DECIDED = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+) sotto: YOUTUBE_CAPTION "
    r"video_id=(\S+) cue=(\S+) t=(\S+) track=(\S+) words=(\S+) text=(?P<text>.*)$")


def newest_log():
    """The app's own log, newest first."""
    pats = [os.path.join("I:\\cc-tmp", "sotto-*.log")]
    for pat in pats:
        files = sorted(glob.glob(pat), key=lambda p: os.path.getmtime(p))
        if files:
            return files[-1]
    return ""


def read_decided(path):
    """[(when, video_id, cue, t, track, words, text)] from the app's log."""
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = DECIDED.match(line.rstrip("\n"))
                if not m:
                    continue
                try:
                    when = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    continue
                try:
                    # A shell escreve `%r` (o repr do Python), nao JSON.
                    text = ast.literal_eval(m.group("text"))
                except Exception:
                    try:
                        text = json.loads(m.group("text"))
                    except Exception:
                        text = m.group("text")
                out.append((when.timestamp(), m.group(2), m.group(3), m.group(4),
                            m.group(5), m.group(6), text))
    except OSError:
        pass
    return out


def norm_words(text):
    return str(text or "").split()


def prefix_ok(painted, text):
    """Are `painted` the BEGINNING of `text`?

    The player types a cue word by word, so the last painted word may be a
    PREFIX of the cue's word ('t' for 'the'). Everything else has to match.
    """
    p = [w.lower() for w in painted]
    t = [w.lower() for w in norm_words(text)]
    if not p or len(p) > len(t):
        return False
    for i, w in enumerate(p):
        if w == t[i]:
            continue
        if i == len(p) - 1 and t[i].startswith(w):
            continue
        return False
    return True


def suffix_ok(painted, text):
    """Are `painted` the END of `text`? (the rollup's older line)"""
    p = [w.lower() for w in painted]
    t = [w.lower() for w in norm_words(text)]
    if not p or len(p) > len(t):
        return False
    return p == t[-len(p):]


def rollup_ok(painted, text, anteriores=()):
    """Is the painted rollup the line the app showed?

    THE ROLLUP HOLDS THE LAST CUES, so the painted words can START in a line
    BEFORE the one the app showed -- the rollup cuts its oldest line. MEASURED
    2026-10-20 on the owner's own Chrome: the painted words were the END of
    an older line plus the BEGINNING of the line the app showed, in 11 of 11
    decisions.

    So the property is: there is a cut `k` such that the painted words from
    `k` on are the BEGINNING of the app's line, and the words before the cut
    are the END of some EARLIER line.
    """
    p = [w.lower() for w in painted]
    if not p:
        return False
    for k in range(len(p), -1, -1):
        head, tail = p[:k], p[k:]
        if not prefix_ok(tail, text):
            continue
        if not head:
            return True
        if suffix_ok(head, text):
            return True
        for older in anteriores:
            if suffix_ok(head, older):
                return True
    return False


def tail_prefix_ok(painted, text):
    """Is there a cut of the paint whose tail is the BEGINNING of `text`?

    This is THE property: the words the player is painting are the start of
    the line the app showed.
    """
    p = [w.lower() for w in painted]
    for k in range(len(p), -1, -1):
        if prefix_ok(p[k:], text):
            return True
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="a prova 1:1 ao vivo")
    ap.add_argument("--log", default=None, help="o log da app")
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--interval", type=float, default=0.25)
    args = ap.parse_args(argv)

    log_path = args.log or newest_log()
    if not log_path or not os.path.exists(log_path):
        print("SEM LOG DA APP (%r)" % log_path)
        return 2
    print("log da app: %s" % log_path)

    import external_subs
    import youtube_captions as yc

    UIA, uia = external_subs._uia()
    hwnd = external_subs.find_player_window()
    if not hwnd:
        print("SEM JANELA DE PLAYER")
        return 2
    print("janela do player: %d | %s" % (hwnd, external_subs._window_title(hwnd)))

    # 1) as amostras da PINTURA, com o instante de cada uma
    samples = []
    started = time.time()
    janela_ini = started
    while time.time() - started < args.seconds:
        t_wall = time.time()
        got = yc.painted_words(uia, UIA, hwnd=hwnd)
        words = got.get("words") or []
        if words:
            samples.append((t_wall, list(words)))
        time.sleep(args.interval)
    janela_fim = time.time()
    print("amostras da pintura: %d (em %.1f s)" % (len(samples), janela_fim - janela_ini))

    # 2) as linhas que a APP decidiu
    decided = read_decided(log_path)
    print("linhas decididas pela app: %d" % len(decided))
    for row in decided[-6:]:
        print("   cue=%s t=%s track=%s words=%s %r"
              % (row[2], row[3], row[4], row[5], row[6][:70]))

    # 3) a comparacao: no instante de cada decisao, as palavras que o player
    #    pintava tem de ser o COMECO da linha que a app mostrou
    comparavel_n = 0
    iguais = 0
    for pos, (when, vid, cue, t, track, words, text) in enumerate(decided):
        if when < janela_ini - 1.0 or when > janela_fim + 1.0:
            continue
        near = [s for s in samples if abs(s[0] - when) <= 2.0]
        if not near:
            continue
        near.sort(key=lambda s: abs(s[0] - when))
        painted = near[0][1]
        # AS LINHAS ANTERIORES: o rollup pinta a ultima linha ANTES desta.
        anteriores = [row[6] for row in decided[:pos] if row[6] != text]
        if not rollup_ok(painted, text, anteriores):
            continue
        comparavel_n += 1
        if tail_prefix_ok(painted, text):
            iguais += 1
    print()
    print("AMOSTRAS COMPARAVEIS: %d" % comparavel_n)
    print("IGUAIS (1:1, a cauda do que o YouTube pinta e o inicio da nossa "
          "linha): %d" % iguais)
    if comparavel_n and iguais == comparavel_n:
        print("VERDICT: 1:1 -- a nossa legenda E a legenda que o YouTube pinta")
        return 0
    if comparavel_n:
        print("VERDICT: DIVERGEM")
        return 3
    print("VERDICT: SEM AMOSTRA COMPARAVEL")
    return 4


if __name__ == "__main__":
    sys.exit(main())
