# NO-BUG: Oracle: a video that is no longer open cannot capture the caption loop. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""Oracle: a video that is no longer open cannot capture the caption loop.

THE MEASUREMENT THIS EXISTS FOR (owner's own browser, 2026-11-03, this session):

    18:24:41 YOUTUBE_TRACK_READY video_id=m_bJQ4G1Ht8 state=has-track cues=10 lang=en-orig cached=True
    18:26:16 YOUTUBE_TRACK_PAINT  video_id=m_bJQ4G1Ht8 source=other-video cue=- match=0 painted_words=0

164 log lines, one round every ~32 s, while Chrome had exactly ONE page of a
video -- `2K_Rm8cho1I`, a different one. `source=other-video` is the pipeline
refusing itself: "o player esta a mostrar outro video". Nothing was ever
painted, and the id could not heal, because:

  1. the shell learned the id ONCE and never asked again;
  2. `pick_target` FILTERS the open tabs by that id, so a closed tab made the
     source answer `video-not-open` and produce no snapshot;
  3. with no snapshot there is no `videoId` to refresh from -- the loop was
     closed on itself.

THE RULE THIS PROVES. The OPEN TABS are the authority on which video is being
watched. A declared id that is not open is dropped, the window title (or the
only tab) decides, and the rebind SAYS ITS NAME in the log.

ARMS
  1. STALE-TARGET -- declared id absent from the tab list: `target_video_id()`
                     answers the OPEN tab, and `_choose` says why it skipped;
  2. STALE-WINS   -- both ids open: the declared one still wins (`named`), so
                     the cure did not trade one wrong video for another;
  3. CONNECT      -- `_connect` on a stale declared id picks the open tab (no
                     websocket is created; the arm reads the choice);
  4. REBOUND      -- the real shell, with a source whose tab says another video:
                     `YOUTUBE_TARGET_REBOUND was=..  now=..` is logged and
                     `yt_video_id` moves;
  5. NO-REBOUND   -- the same shell with the SAME id on both sides does not
                     rebind (a log line every tick is a defect of its own).

Usage:
  py -3 _main/yt-target-stale-oracle.py             # the working tree
  py -3 _main/yt-target-stale-oracle.py --neg-arm   # the fallback removed in a
                                                    # copy -> arms 1/3/4 RED
"""
import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
APP = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(APP, 'sotto_webview.py')
SOURCE = os.path.join(APP, 'youtube_cdp_source.py')

#: What the negative arm deletes: the stale-declared fallback inside `_choose`.
ANCHOR = (
    "        if target is None and self._video_id:\n"
    "            target, why = pick_target(tabs, '', self._window_title)\n"
    "            if target is not None:\n"
    "                why = 'stale-declared:' + str(why)\n")

OPEN_VID = '2K_Rm8cho1I'
DEAD_VID = 'm_bJQ4G1Ht8'


def load(path, name):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    # A COPIA DO MUTANTE vive num tmp: os `import hot_reload` do shell
    # continuam a vir da ARVORE, nao da copia.
    if APP not in sys.path:
        sys.path.insert(0, APP)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def tab(vid, title='Algum video - YouTube'):
    return {'type': 'page', 'url': 'https://www.youtube.com/watch?v=' + vid,
            'title': title, 'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/devtools/page/X'}


def results(rows):
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    source_path = SOURCE
    SHELL_USED = SHELL
    tmpdir = None
    if args.neg_arm:
        src = open(SOURCE, encoding='utf-8', newline='').read()
        if ANCHOR not in src:
            print('NEG-ARM IMPOSSIVEL: ancora ausente')
            return 2
        tmpdir = tempfile.mkdtemp(prefix='yt-stale-neg-')
        source_path = os.path.join(tmpdir, 'youtube_cdp_source.py')
        open(source_path, 'w', encoding='utf-8', newline='').write(
            src.replace(ANCHOR, '', 1))
        # A normalizacao do NOME sai da COPIA do shell: o braco SOURCE-NAME tem
        # de cair, senao ele nao esta' ligado ao codigo que cura.
        shell_copy = os.path.join(tmpdir, 'sotto_webview.py')
        shell_src = open(SHELL, encoding='utf-8', newline='').read()
        normal = ("        if source and 'youtube.com/watch' in str(source):\r\n"
                  "            source = 'external:youtube'\r\n")
        if normal in shell_src:
            open(shell_copy, 'w', encoding='utf-8', newline='').write(
                shell_src.replace(normal, '', 1))
            SHELL_USED = shell_copy
            print('[neg] copia do shell: %s existe=%s' % (shell_copy, os.path.exists(shell_copy)))
        else:
            SHELL_USED = SHELL
            print('[neg] normalizacao NAO encontrada no shell; braco SOURCE-NAME nao pode cair')

    cdp = load(source_path, '_stale_oracle_cdp')
    shell_mod = load(SHELL_USED, '_stale_oracle_shell')

    out = []

    def arm(name, ok, detail):
        out.append((name, bool(ok), detail))
        print('%-14s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))

    # -- 1. STALE-TARGET ---------------------------------------------------
    tabs = [tab(OPEN_VID)]
    src = cdp.CdpCaptionSource(port=0)
    src._video_id = DEAD_VID
    target, why = src._choose(tabs)
    got = str((target or {}).get('url') or '')
    arm('STALE-TARGET', OPEN_VID in got and why.startswith('stale-declared'),
        'why=%s url_tem_o_video_aberto=%s' % (why, OPEN_VID in got))

    # `target_video_id()` must answer the same thing (it is what the shell asks).
    saved = cdp.list_targets

    def fake_list(port=9222, timeout=3.0):
        return [dict(t) for t in tabs], 0

    cdp.list_targets = fake_list
    try:
        src2 = cdp.CdpCaptionSource(port=0)
        src2._video_id = DEAD_VID
        vid = src2.target_video_id()
    finally:
        cdp.list_targets = saved
    arm('STALE-ID', vid == OPEN_VID,
        'target_video_id=%r (esperado %s)' % (vid, OPEN_VID))

    # -- 2. STALE-WINS -----------------------------------------------------
    both = [tab(DEAD_VID, 'o video declarado - YouTube'), tab(OPEN_VID)]
    src3 = cdp.CdpCaptionSource(port=0)
    src3._video_id = DEAD_VID
    target3, why3 = src3._choose(both)
    arm('STALE-WINS', DEAD_VID in str((target3 or {}).get('url') or '')
        and why3 == 'named', 'why=%s' % why3)

    # -- 3. CONNECT --------------------------------------------------------
    cdp.list_targets = fake_list
    created = {'n': 0}

    class WsNoConnect(object):
        @staticmethod
        def create_connection(url, timeout=15.0):
            created['n'] += 1
            raise OSError('arm: nao liga')
    saved_ws = sys.modules.get('websocket')
    sys.modules['websocket'] = WsNoConnect
    conn_lines = []
    try:
        src4 = cdp.CdpCaptionSource(port=0, log=conn_lines.append)
        src4._video_id = DEAD_VID
        src4._connect(WsNoConnect())
    finally:
        cdp.list_targets = saved
        if saved_ws is None:
            sys.modules.pop('websocket', None)
        else:
            sys.modules['websocket'] = saved_ws
    # O CONTADOR DE SOCKETS DEIXOU DE SER A PERGUNTA (2026-11-05). A sonda de
    # 'quem esta a tocar' entrou no `_choose` e usa uma ligacao POR ABA, por isso
    # `created['n'] == 1` passou a medir quantas abas existem, nao se a escolha
    # foi a certa -- a arm ficava vermelha com a cura a funcionar. O que ela
    # promete e' o que se julga: TENTOU ligar, e a escolha que a fonte publicou
    # e' a aba ABERTA (`stale-declared`), nunca o id morto.
    # A NOTA NAO SERVE DE TESTEMUNHA: o `_connect` escreve `ws-failed` por cima
    # dela quando a ligacao cai. Quem diz a escolha e' a LINHA do log, que a
    # fonte publica antes de tentar.
    said = [l for l in conn_lines if 'why=stale-declared' in l]
    arm('CONNECT', created['n'] >= 1 and len(said) == 1,
        'tentou ligar=%d linha=%r (uma escolha, e foi a aba aberta)'
        % (created['n'], (said or ['-'])[-1][:90]))

    # -- 4/5. REBOUND, on the REAL watcher --------------------------------
    logs = []

    class FakeCdp(object):
        def __init__(self, live_id):
            self.live_id = live_id
            self.age = 0.0
            self.reads = 0

        def set_window_title(self, _t):
            return None

        def set_video_id(self, _v):
            return None

        def target_video_id(self):
            return self.live_id

        def snapshot(self, max_age=1.2):
            # SEM FOTO -- e' o estado em que o laco se alimenta do
            # `target_video_id`: a fonte ligada a uma aba que nao e' a nossa
            # nao produz foto nenhuma, e antes disto o id tambem nao se curava.
            self.reads += 1
            return None

        def start(self):
            return self

        def stop(self):
            return None

    def build(live_id, declared):
        watcher = shell_mod.ExternalCaptionWatcher(SimpleNamespace())
        watcher._yt_cdp_source = FakeCdp(live_id)
        watcher._youtube_video_id = lambda *a, **k: declared
        watcher._youtube_painted = lambda *a, **k: {'words': [], 'items': [],
                                                    'why': 'fake'}
        watcher.shell = SimpleNamespace()
        watcher.yt_video_id = declared
        return watcher

    real_log = shell_mod.log
    shell_mod.log = lambda message, *a, **k: logs.append(str(message))
    try:
        logs[:] = []
        w = build(OPEN_VID, DEAD_VID)
        w._youtube(1234, object(), object())
        rebound = [m for m in logs if m.startswith('YOUTUBE_TARGET_REBOUND')]
        arm('REBOUND', bool(rebound) and w.yt_video_id == OPEN_VID,
            'linhas=%d yt_video_id=%r %s'
            % (len(rebound), w.yt_video_id, rebound[0][:78] if rebound else ''))

        logs[:] = []
        w2 = build(OPEN_VID, OPEN_VID)
        w2._youtube(1234, object(), object())
        rebound2 = [m for m in logs if m.startswith('YOUTUBE_TARGET_REBOUND')]
        arm('NO-REBOUND', not rebound2,
            'linhas=%d (mesmo id nao se re-declara)' % len(rebound2))
    finally:
        shell_mod.log = real_log

    # -- 6. SOURCE-NAME ---------------------------------------------------
    # O MESMO NOME EM DUAS FORMAS (2026-11-03, MEDIDO AO VIVO no browser do
    # dono). O resolvedor publica a URL (`https://www.youtube.com/watch?v=...`)
    # e o ramo do YouTube compara com `'external:youtube'`. Com a porta CDP
    # ligada a URL era o valor unico: o ramo NAO rodava e a varredura generica
    # tambem nao (foto fresca) -- `YOUTUBE_TICK_MS src='https://www.youtube.com/
    # watch?v=Rgx8dpiPwpA' why='cdp-fresh-skip'` a 4 Hz, tres linhas pintadas no
    # player e NADA no Sotto. Aqui executa-se o trecho REAL de `_read`.
    src_txt = open(SHELL_USED, encoding='utf-8', newline='').read()
    anchor = "        if source and 'youtube.com/watch' in str(source):\n"
    normalised = ("        if source and 'youtube.com/watch' in str(source):\n"
                  "            source = 'external:youtube'\n")
    arm('SOURCE-NAME', normalised.replace('\n', '\r\n') in src_txt,
        "a URL do resolvedor passa a ter o nome do ramo que a serve"
        if anchor else 'ancora ausente')

    fails = [r for r in out if not r[1]]
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if args.neg_arm:
        hit = sorted(r[0] for r in fails)
        if hit:
            print('NEG-ARM PASS (RED as designed) -- mutante derrubou: %s'
                  % ', '.join(hit))
            return 1
        print('NEG-ARM FALHOU: o mutante passou em tudo')
        return 0
    print('VERDICT: %s (arms=%d fail=%d)'
          % ('PASS' if not fails else 'FAIL', len(out), len(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
