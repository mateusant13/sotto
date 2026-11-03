#!/usr/bin/env python
"""youtube-paint-first-oracle -- the caption appears WITH the page, not seconds later.

O DONO, 2026-10-22 09:35, verbatim: *"tu so viu carregar a pagina depois de varios
segundos de ja ter carregado? arruma isso."*

O DEFEITO ERA DE DESENHO, e por isso um oraculo pode apanha-lo sem lancar a app: o
caminho vivo (`ExternalCaptionWatcher`) ja LIA as palavras que o player esta a pintar
(`youtube_captions.painted_words` -> UI Automation, barato), mas so as mostrava
DEPOIS de o track do YouTube chegar -- e o extract mede segundos (um video novo
invalida a cache). Enquanto o track nao chegava, a funcao devolvia `track-pending` e a
legenda ficava VAZIA, com as palavras exatas que o dono ve no YouTube ja lidas em maos.

As armas:

  1  `paint_line` COMPORTA-SE: junta palavras, colapsa espacos, aceita uma string,
     e devolve "" quando nao ha nada -- nunca inventa texto.
  2  O SHELL USA-A ANTES DE DESISTIR: no ramo `track is None`, a chamada existe, a
     linha emitida e `external:youtube:track`, o motivo e `painted-untracked`, e o
     `track-pending` continua a ser o que acontece quando NAO ha palavras.
  3  NEG-ARM (mutante): apagar a chamada do shell tem de tornar a arma 2 RED. Sem
     isto, a arma 2 e uma afirmacao sobre bytes que ninguem testou.

    python _main\youtube-paint-first-oracle.py          # rc=0 verde
    python _main\youtube-paint-first-oracle.py --neg-arm # rc=1 POR DESENHO
"""
from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")
WINDOW = os.path.join(REPO, "app", "webview", "youtube_window.py")


def say(msg=""):
    print(msg)


def load_paint_line():
    sys.path.insert(0, os.path.join(REPO, "app", "webview"))
    import youtube_window  # noqa: WPS433 -- o modulo e puro (sem pywebview)
    return youtube_window.paint_line


def arm1():
    paint = load_paint_line()
    cases = [
        (["hello"], "hello", "uma palavra"),
        (["a", "b"], "a b", "duas palavras"),
        (["  a  ", " b "], "a b", "espacos a mais"),
        ([""], "", "uma palavra vazia"),
        ([], "", "lista vazia"),
        (None, "", "None"),
        ("solo", "solo", "uma string em vez de lista"),
        (["a", "", "b"], "a b", "buraco no meio"),
    ]
    bad = []
    for words, want, why in cases:
        got = paint(words)
        ok = got == want
        say("  %s  %-22s %r -> %r (esperado %r)" % ("ok  " if ok else "FAIL", why, words, got, want))
        if not ok:
            bad.append(why)
    # Um texto com quebras nao pode virar duas linhas por acidente: e UMA linha viva.
    got = paint(["a\nb"])
    say("  %s  quebra de linha dentro de uma palavra -> %r" % ("ok  " if "\n" not in got else "FAIL", got))
    if "\n" in got:
        bad.append("quebra de linha")
    return not bad, bad


def shell_source():
    return io.open(SHELL, encoding="utf-8", errors="replace").read()


def arm2(src=None):
    """O ramo `track is None` usa as palavras do player antes de desistir."""
    s = shell_source() if src is None else src
    bad = []
    # o bloco, do `if track is None:` ate ao `track-pending`
    # A ancora e o `_yt_forget('track-pending'`, NAO a palavra `track-pending`: o
    # comentario que explica o ramo tambem a escreve, e a primeira versao deste
    # oraculo parava no comentario (ficou vermelho sobre codigo correto -- o defeito
    # classico de ancora gasta).
    m = re.search(r"thread\.request\(vid, painted=painted\)(.*?)_yt_forget\('track-pending'", s, re.S)
    if not m:
        say("  FAIL  nao ha ramo `if track is None:` antes de `track-pending`")
        return False, ["ramo ausente"]
    block = m.group(1)
    has_call = "youtube_window.paint_line(painted)" in block
    say("  %s  o ramo chama `youtube_window.paint_line(painted)`" % ("ok  " if has_call else "FAIL"))
    if not has_call:
        bad.append("sem a chamada a paint_line")
    has_route = "('external:youtube:track', [paint_text])" in block or \
                '("external:youtube:track", [paint_text])' in block
    say("  %s  emite a linha com a rota `external:youtube:track`" % ("ok  " if has_route else "FAIL"))
    if not has_route:
        bad.append("rota errada")
    has_reason = '"painted-untracked"' in block or "'painted-untracked'" in block
    say("  %s  marca o motivo `painted-untracked`" % ("ok  " if has_reason else "FAIL"))
    if not has_reason:
        bad.append("sem o motivo")
    # a ORDEM: a chamada tem de vir ANTES do `track-pending` (e dentro do ramo)
    i_call = block.find("paint_line(painted)")
    # O bloco termina EXACTAMENTE no `_yt_forget('track-pending'` (a regex usa-o como
    # delimitador), portanto o indice do fim e o comprimento do bloco. Procurar a
    # string dentro do bloco devolvia -1 -- e um `-1` fazia a comparacao de ordem
    # falhar sobre codigo correcto.
    i_forget = len(block)
    order = 0 <= i_call < i_forget
    say("  %s  a chamada vem ANTES do `track-pending`" % ("ok  " if order else "FAIL"))
    if not order:
        bad.append("ordem")
    # o caminho sem palavras continua a ser o de sempre
    tail = block[i_forget:]
    guard = "if paint_text:" in block
    say("  %s  sem palavras, cai no `track-pending` (guarda `if paint_text:`)" % ("ok  " if guard else "FAIL"))
    if not guard:
        bad.append("sem guarda")
    return not bad, bad


def mutant(src):
    """Apaga a chamada do shell -- e nada mais.

    A ANCORA MEDE A INDENTACAO (2026-11-03). Ela citava 16 espacos e o `try:`
    real, dentro do metodo, deixa a chamada em 12: a mutacao nao casava, a copia
    saia IDENTICA ao original e o `--neg-arm` publicava
    `MUTANTE aplicado=false` com `VERDICT: NEG-ARM FAIL` e rc=2 -- um controlo
    morto a dizer que nao apanhou nada, no passo `red-as-expected-youtube-paint-first`.
    Medido no log `_main/_audit-verify/youtube-paint-first-neg.log`.
    """
    real = "            paint_text = youtube_window.paint_line(painted)"
    dead = "            paint_text = ''"
    out = src
    for nl in ("\r\n", "\n"):
        out = out.replace(real + nl, dead + nl, 1)
    return out


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    neg = "--neg-arm" in argv
    say("youtube-paint-first-oracle | shell=%s" % os.path.basename(SHELL))
    say("")
    say("ARMA 1 -- paint_line")
    ok1, bad1 = arm1()
    say("")
    say("ARMA 2 -- o shell pinta antes de desistir")
    if neg:
        src = mutant(shell_source())
        changed = src != shell_source()
        say("  MUTANTE aplicado=%s (a chamada foi apagada da copia)" % str(changed).lower())
        ok2, bad2 = arm2(src)
        if ok2:
            say("")
            say("VERDICT: NEG-ARM FAIL -- o oraculo ficou VERDE sobre uma copia sem a chamada")
            return 2
        say("")
        say("VERDICT: NEG-ARM PASS -- a copia mutada foi apanhada (%d falha(s))" % len(bad2))
        return 1
    ok2, bad2 = arm2()
    say("")
    fails = bad1 + bad2
    say("VERDICT: %s%s" % ("PASS" if not fails else "FAIL",
                           "" if not fails else "  (%d falha(s): %s)" % (len(fails), fails[:4])))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
