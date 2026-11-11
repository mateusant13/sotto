#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: prova que a fonte CDP e' construida UMA vez por processo; nao mede o stutter da shell viva nem a CPU de 81,3 % que o originou.
"""UMA FONTE CDP POR PROCESSO -- o oraculo do defeito de 1,1 criacoes/s.

O QUE FOI MEDIDO (log do dono, 2026-11-09, janela de 600 s):

    YOUTUBE_CDP_SOURCE state=attached   675 linhas  (1.13/s) -- TODAS identicas
    YOUTUBE_TARGET pick=GRlcm3wmOqs ... 712 linhas  (1.19/s) -- TODAS identicas

As duas linhas sao deduplicadas DENTRO do objeto (`_publish` compara
`self._note`; `_log_target` compara `self._target_text`). Logo 675 copias da
MESMA linha nao sao um problema de throttle: sao 675 OBJETOS, cada um a
arrancar dois fios (`_run` + `_tid_run`) e a pagar a `/json/list` do arranque.
O stutter de 11:5x trouxe o numero do outro lado: 81,3 %c na shell python.

A CURA E' UM REGISTO NO MODULO, e este oraculo prova que a construcao passa a
ser UNICA mesmo quando N objetos diferentes pedem a fonte (o `self._yt_cdp_source`
morre com o objeto que o guarda; o watcher e a shell guardam o seu).

ARMS:
  A1 200 objetos-irmAOs, `_yt_cdp_ensure` REAL -> 1 construcao
  A2 (controlo) a mesma populacao, registo limpo entre as chamadas -> N construcoes
     (sem isto o contador podia estar a medir o vazio)
  A3 `live_source_clear` devolve a construcao seguinte
  A4 `start()` sobre a fonte adotada e' chamado (uma fonte que existe e nao corre
     e' o pior dos dois mundos)

O corpo executado e' o METODO REAL, extraido por `ast` de
`app/webview/sotto_webview.py` -- nunca uma copia que apodrece.
"""
import argparse
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.join(REPO, 'app', 'webview')
sys.path.insert(0, WEBVIEW)


def load_module():
    import youtube_cdp_source
    return youtube_cdp_source


#: O BRACO ANTES NAO SE LE' DO `HEAD` (2026-11-11, MEDIDO). Ele lia: enquanto a
#: cura estava so' no working tree, `git show HEAD:...` devolvia o codigo velho
#: e o braco reproduzia a multiplicacao; no dia em que a cura foi COMETIDA, HEAD
#: passou a conter a cura, o "antes" mediu `construcoes=1` e o `--neg-arm`
#: morreu em rc=0 com a mensagem certa -- um controlo que existe e nao controla.
#: A casa ja' pagou esta classe no `panel-history-wheel`. O "antes" passa a ser
#: uma MUTACAO CIRURGICA do fonte VIVO: a chamada ao registo de modulo
#: (`live_source(...)`) volta a ser uma construcao directa, que e' exactamente o
#: comportamento medido antes da cura (675 objetos/600 s no log do dono).
BEFORE_ANCHOR = (
    "        source = youtube_cdp_source.live_source(\n"
    "            lambda: youtube_cdp_source.CdpCaptionSource(log=log), log=log)\n")
BEFORE_BODY = "        source = youtube_cdp_source.CdpCaptionSource(log=log)\n"


def before_source():
    """O fonte VIVO com o registo de modulo removido -- o braco ANTES."""
    src = open(SHELL, encoding='utf-8', errors='replace').read()
    if BEFORE_ANCHOR not in src:
        raise SystemExit('ANCORA AUSENTE: o call site do `live_source` mudou; '
                         're-ancorar BEFORE_ANCHOR (um controlo que nao corre '
                         'nao e um controlo)')
    return src.replace(BEFORE_ANCHOR, BEFORE_BODY, 1)


def extract_ensure(src=None):
    """O corpo de `ExternalCaptionWatcher._yt_cdp_ensure`, compilado."""
    if src is None:
        src = open(SHELL, encoding='utf-8', errors='replace').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_yt_cdp_ensure':
            mod = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(mod)
            code = compile(mod, '<ensure>', 'exec')
            # O metodo referencia nomes do MODULO da shell (`os`, `log`,
            # `youtube_cdp_source`). O escopo tem de os ter, senao o oraculo mede
            # um `NameError` em vez do comportamento -- e um instrumento que
            # estoura por defeito proprio e' indistinguivel de "nao houve nada".
            mod = load_module()
            ns = {'os': os, 'youtube_cdp_source': mod,
                  'log': lambda _m: None}
            exec(code, ns)
            return ns['_yt_cdp_ensure']
    raise SystemExit('_yt_cdp_ensure nao encontrado em %s' % SHELL)


class FakeSource:
    """Duplo de `CdpCaptionSource`: conta construcoes e arranques."""
    built = 0
    started = 0

    def __init__(self, port=None, poll_s=None, log=None):
        FakeSource.built += 1
        self.log = log or (lambda _m: None)
        self.video_id = None

    def set_video_id(self, vid):
        self.video_id = vid

    def start(self):
        FakeSource.started += 1
        return self


class FakeWatcher:
    """O `self` do metodo: sem shell, sem fonte -- cada um pede a SUA."""
    def __init__(self, log=None):
        self.shell = None
        self._yt_cdp_source = None
        self._log = log or (lambda _m: None)


def run(n=200):
    mod = load_module()
    ensure = extract_ensure()
    fails = []

    os.environ['SOTO_YT_CDP_KEEP'] = '1'

    def call(fake_log=None):
        FakeWatcher.__init__.__globals__  # noqa: B018 -- so' para clareza
        w = FakeWatcher(fake_log)
        # o metodo resolve `youtube_cdp_source` no escopo do modulo da SHELL;
        # injetamos o mesmo modulo do processo, com o duplo ja' dentro.
        return ensure(w, 'grlc')

    # -- A1: N irmaos, registo limpo no inicio ------------------------------
    mod.live_source_clear()
    FakeSource.built = 0
    FakeSource.started = 0
    saved = mod.CdpCaptionSource
    mod.CdpCaptionSource = FakeSource
    try:
        outs = [call() for _ in range(n)]
    finally:
        mod.CdpCaptionSource = saved
    a1 = FakeSource.built == 1 and all(o is outs[0] for o in outs)
    print('%s A1 %d irmaos -> construcoes=%d (quer 1), mesma instancia=%s'
          % ('GREEN' if a1 else 'RED  ', n, FakeSource.built,
             all(o is outs[0] for o in outs)))
    if not a1:
        fails.append('A1')

    # -- A2 (controlo): registo limpo ENTRE as chamadas -> N construcoes -----
    FakeSource.built = 0
    mod.CdpCaptionSource = FakeSource
    try:
        for _ in range(n):
            mod.live_source_clear()
            call()
    finally:
        mod.CdpCaptionSource = saved
    a2 = FakeSource.built == n
    print('%s A2 controlo: registo limpo entre chamadas -> construcoes=%d (quer %d)'
          % ('GREEN' if a2 else 'RED  ', FakeSource.built, n))
    if not a2:
        fails.append('A2')

    # -- A3: clear devolve a construcao seguinte ----------------------------
    mod.live_source_clear()
    FakeSource.built = 0
    mod.CdpCaptionSource = FakeSource
    try:
        first = call()
        mod.live_source_clear()
        second = call()
    finally:
        mod.CdpCaptionSource = saved
    a3 = FakeSource.built == 2 and first is not second
    print('%s A3 clear -> nova construcao=%s (quer 2 construcoes, instancias distintas)'
          % ('GREEN' if a3 else 'RED  ', FakeSource.built))
    if not a3:
        fails.append('A3')

    # -- A4: o start corre sobre a fonte adotada ----------------------------
    mod.live_source_clear()
    FakeSource.built = 0
    FakeSource.started = 0
    mod.CdpCaptionSource = FakeSource
    try:
        call()
        call()
    finally:
        mod.CdpCaptionSource = saved
    a4 = FakeSource.started >= 1
    print('%s A4 start() chamado=%d (quer >=1 sobre a fonte unica)'
          % ('GREEN' if a4 else 'RED  ', FakeSource.started))
    if not a4:
        fails.append('A4')

    if fails:
        print('VERDICT: FAIL (%d/%d) %s' % (len(fails), 4, ','.join(fails)))
        return 1
    print('VERDICT: PASS (4/4) -- uma fonte por processo, e o controlo mostra '
          'que o contador nao esta a medir o vazio')
    return 0


def before(n=200):
    """O BRACO ANTES: a mesma populacao contra o metodo de `HEAD`."""
    mod = load_module()
    ensure = extract_ensure(before_source())
    saved = mod.CdpCaptionSource
    FakeSource.built = 0
    FakeSource.started = 0
    mod.CdpCaptionSource = FakeSource
    try:
        for _ in range(n):
            ensure(FakeWatcher(), 'grlc')
    finally:
        mod.CdpCaptionSource = saved
    # O ROTULO NAO DIZ `HEAD` (2026-11-11): o braco nao le' mais o commit --
    # le' o fonte vivo com o registo de modulo removido, e um rotulo que
    # nomeasse o commit seria a mentira que fez este controlo morrer em rc=0.
    print('ANTES (sem registo): %d irmaos -> construcoes=%d'
          % (n, FakeSource.built))
    # CONVENCAO DA CASA: o braco negativo devolve **1 quando APANHA** o defeito.
    # Aqui ele "apanha" quando a populacao de HEAD reproduz a multiplicacao --
    # e esse e' exactamente o defeito medido no log do dono (675 objetos/600 s).
    return 1 if FakeSource.built > 1 else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--before', '--neg-arm', action='store_true', dest='before',
                    help='roda a populacao contra o metodo de HEAD (o braco ANTES); '
                         'rc=1 quando ele reproduz a multiplicacao')
    args = ap.parse_args(argv)
    if args.before:
        return before(args.n)
    return run(args.n)


if __name__ == '__main__':
    sys.exit(main())
