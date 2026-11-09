# NO-BUG: ESCONDER O PAINEL NAO APAGA A LEGENDA AO VIVO (2026-11-05).
"""ESCONDER O PAINEL NAO APAGA A LEGENDA AO VIVO (2026-11-05).

MEDIDO na sessao viva do dono (pid 57600): tres
`CAPTION_WINDOW_BLANKED reason=panel-hidden epoch=3/4/5 wanted=true` em vinte e
um segundos -- 06:04:58, 06:05:03, 06:05:19 -- um por Alt+C. Ele reportou o
sintoma como *"parece que ela do nada para de dar display ou funcionar
aleatoriamente"*: cada ciclo de painel apagava a legenda e ela so' voltava na
proxima linha, e `_blank_caption_window` ainda esvaziava `_external_last_text` e
subia `_source_epoch`, o que atirava fora o dedup do YouTube a cada toque.

A LEI (AGENTS.md, regra 3, verbatim do dono): *"se a legenda ao vivo ta
desativada, nao significa q o modelo ta desativado. e' o DISPLAY que ta
desativado"* -- e o inverso tambem vale: esconder o PAINEL nao e' desligar a
LEGENDA. O painel e' uma janela; a legenda ao vivo e' outra.

O QUE ESTE ORACULO EXECUTA. A funcao `SottoShell.hide_panel` REAL, extraida do
arquivo por AST e executada com os globais do sistema injectados (`hide_window`,
`window_visible`, `log`) sobre um `self` falso com o overlay gravador. Nao e' uma
copia: se a shell mudar a funcao, este passo muda com ela.

BRACO NEGATIVO (`--neg-arm`): devolve o `_blank_caption_window('panel-hidden')`
incondicional numa COPIA do fonte e exige o vermelho do arm A.
"""
from __future__ import annotations

import ast
import io
import json
import sys
import threading
import time
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHELL = REPO / 'app' / 'webview' / 'sotto_webview.py'


def extract_hide_panel(src: str) -> str:
    """O texto-fonte EXATO de `SottoShell.hide_panel`, por AST."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'SottoShell':
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == 'hide_panel':
                    lines = src.splitlines(keepends=True)
                    body = lines[member.lineno - 1:member.end_lineno]
                    indent = ' ' * member.col_offset
                    # O metodo vem indentado dentro da classe; exec'ado no topo
                    # ele precisa de sair do nivel da classe sem perder o corpo.
                    return ''.join(
                        line[len(indent):] if line.startswith(indent) else line
                        for line in body
                    )
    raise SystemExit('SottoShell.hide_panel nao existe no fonte')


class Recorder:
    """O overlay e o `_blank_caption_window`, gravando o que lhes fazem."""

    def __init__(self):
        self.blanks = []
        self.overlay_calls = []
        self.rearms = []

    def blank(self, reason):
        self.blanks.append(reason)

    def rearm(self):
        self.rearms.append(True)


def build_shell(fn_src, recorder):
    logs = []
    namespace = {
        'hide_window': lambda hwnd: recorder.overlay_calls.append(('hide_window', hwnd)),
        'window_visible': lambda hwnd: False,
        'log': lambda msg: logs.append(str(msg)),
        '__builtins__': __builtins__,
    }
    exec(compile(fn_src, '<hide-panel>', 'exec'), namespace)
    hide_panel = namespace['hide_panel']
    published = []
    shell = types.SimpleNamespace(
        hwnd=4242,
        visible=True,
        click_watcher=types.SimpleNamespace(armed=True),
        caption_overlay=types.SimpleNamespace(),
        _blank_caption_window=recorder.blank,
        # O `hide_panel` publica a visibilidade e' por isso que o worker sabe se
        # volta ao caminho do stream (a "stack law"); aqui e' um gravador.
        publish_panel_visibility=lambda reason: published.append(reason),
    )
    shell.published = published
    return shell, hide_panel, logs


def arm_a(src):
    """Com a legenda AO VIVO ligada, esconder o painel nao toca na legenda."""
    rec = Recorder()
    shell, fn, logs = build_shell(extract_hide_panel(src), rec)
    shell._caption_wanted = True
    shell._source_epoch = 7
    fn(shell, 'hotkey')
    kept_line = any('CAPTION_WINDOW_KEPT' in m for m in logs)
    return {
        'ok': not rec.blanks and shell._source_epoch == 7 and kept_line,
        'blanks': list(rec.blanks),
        'epoch': shell._source_epoch,
        'kept_line': kept_line,
        'log': logs[-1] if logs else '',
    }


def arm_b(src):
    """Com a legenda DESLIGADA, esconder o painel limpa o ecra como sempre."""
    rec = Recorder()
    shell, fn, logs = build_shell(extract_hide_panel(src), rec)
    shell._caption_wanted = False
    fn(shell, 'hotkey')
    return {'ok': rec.blanks == ['panel-hidden'], 'blanks': list(rec.blanks)}


def extract_method(src: str, name: str, klass: str = 'SottoShell') -> str:
    """O texto-fonte EXATO de um metodo de `klass`, por AST."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == klass:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == name:
                    lines = src.splitlines(keepends=True)
                    body = lines[member.lineno - 1:member.end_lineno]
                    indent = ' ' * member.col_offset
                    return ''.join(
                        line[len(indent):] if line.startswith(indent) else line
                        for line in body
                    )
    raise SystemExit('%s.%s nao existe no fonte' % (klass, name))


def build_idle_shell(fn_src, recorder):
    """O `_caption_idle_hide` REAL, com o blank e o re-arme gravados."""
    logs = []
    namespace = {'log': lambda msg: logs.append(str(msg)),
                 '__builtins__': __builtins__}
    exec(compile(fn_src, '<caption-idle-hide>', 'exec'), namespace)
    shell = types.SimpleNamespace(
        CAPTION_IDLE_HIDE_S=6.0,
        _caption_idle_seq=3,
        _caption_window_shown=True,
        yt_source_paused=False,
        yt_source_ended=False,
        _last_caption_was_player=True,
        _blank_caption_window=recorder.blank,
        _arm_caption_idle_hide=recorder.rearm,
    )
    return shell, namespace['_caption_idle_hide'], logs


def arm_idle(src, paused=False, ended=False, seq=3, shown=True,
             state_seq=None):
    rec = Recorder()
    shell, fn, logs = build_idle_shell(extract_method(src, '_caption_idle_hide'),
                                       rec)
    shell.yt_source_paused = paused
    shell.yt_source_ended = ended
    shell._caption_idle_seq = seq if state_seq is None else state_seq
    shell._caption_window_shown = shown
    fn(shell, seq)
    return {'ok': True, 'blanks': list(rec.blanks), 'rearms': len(rec.rearms),
            'log': logs[-1] if logs else ''}


def run_idle(src):
    paused = arm_idle(src, paused=True)
    ended = arm_idle(src, ended=True)
    idle = arm_idle(src)
    stale = arm_idle(src, paused=True, seq=2, state_seq=3)
    hidden = arm_idle(src, paused=True, shown=False)
    a = (paused['blanks'] == ['youtube-paused-or-ended']
         and paused['rearms'] == 0)
    b = (ended['blanks'] == ['youtube-paused-or-ended']
         and ended['rearms'] == 0)
    c = (len(idle['blanks']) == 1
         and idle['blanks'][0].startswith('no-caption-for-'))
    d = stale['blanks'] == [] and hidden['blanks'] == []
    print('[%s] pausa apaga os pixels e NAO re-arma  blanks=%s rearms=%d'
          % ('PASS' if a else 'FAIL', paused['blanks'], paused['rearms']))
    print('[%s] fim do video apaga os pixels             blanks=%s rearms=%d'
          % ('PASS' if b else 'FAIL', ended['blanks'], ended['rearms']))
    print('[%s] silencio sem pausa continua a apagar      blanks=%s'
          % ('PASS' if c else 'FAIL', idle['blanks']))
    print('[%s] seq velho/janela escondida nao apagam     stale=%s hidden=%s'
          % ('PASS' if d else 'FAIL', stale['blanks'], hidden['blanks']))
    return a and b and c and d


def arm_blank_deferred(src):
    """Um BLANK antes do overlay existir nao pode ler `on` (NameError, 2026-11-09)."""
    fn_src = extract_method(src, '_blank_caption_window')
    logs = []
    namespace = {'log': lambda msg: logs.append(str(msg)),
                 '__builtins__': __builtins__}
    exec(compile(fn_src, '<blank-window>', 'exec'), namespace)
    shell = types.SimpleNamespace(caption_overlay=None,
                                  _caption_show_pending=True)
    try:
        out = namespace['_blank_caption_window'](shell, 'test-deferred')
    except Exception as exc:  # noqa: BLE001 -- o defeito era exactamente isto
        print('[FAIL] blank sem overlay levantou %r' % (exc,))
        return False
    ok = (out is False and shell._caption_show_pending is False
          and any('CAPTION_WINDOW_DEFERRED on=false' in m for m in logs))
    print('[%s] blank sem overlay fica pendente=false e loga  %s'
          % ('PASS' if ok else 'FAIL', logs[-1] if logs else ''))
    return ok


def arm_display_gate(src):
    """O PORTAO DE ECRAN DO `external_caption` (2026-11-09).

    Tres estados, tres decisoes, e o HISTORICO sempre a receber:
      A) dono ligado e a janela APAGADA pelo piso de silencio -> a linha
         seguinte TEM de voltar a empurrar (o `_caption_window_shown` e'
         transitorio; usa-lo como portao matava a legenda para sempre).
      B) dono DESLIGADO -> nada de pixels, mas o evento do historico sai.
      C) pausa/fim do player -> nada de pixels, mas o evento do historico sai.
    """
    fn_src = extract_method(src, 'external_caption')
    ns = {
        'json': json, 'time': time,
        'log': lambda *_a: None,
        'clean_external_text': lambda t: str(t or '').strip(),
        'extends_previous': lambda _o, _n: False,
        '__builtins__': __builtins__,
    }
    exec(compile(fn_src, '<external-caption>', 'exec'), ns)
    fn = ns['external_caption']

    class DisplayShell:
        def __init__(self, wanted=True, paused=False, ended=False):
            self._caption_wanted = wanted
            self._caption_window_shown = False   # apagada pelo piso de silencio
            self.visible = False                 # painel escondido
            self.yt_source_paused = paused
            self.yt_source_ended = ended
            self.external_lines = 0
            self.external_captions_active = False
            self._external_since = time.monotonic()
            self.pushes = []
            self.events = []
            self.asyncs = []
            self._reload_policy = types.SimpleNamespace(
                boundary=lambda **_k: None)

        def note_history_context(self, _meta):
            pass

        @staticmethod
        def _external_context(_source):
            return {}

        def _park_worker_when_settled(self, _source):
            return False

        def emit(self, kind, payload):
            self.events.append((kind, payload))

        def emit_async(self, kind, payload):
            self.asyncs.append((kind, payload))

        def push_caption_to_window(self, text, **_kw):
            self.pushes.append(text)

    def run_case(wanted=True, paused=False, ended=False,
                 source='external:youtube'):
        shell = DisplayShell(wanted=wanted, paused=paused, ended=ended)
        fn(shell, 'hello world', source, final=False,
           instant=True, rows=['hello world'])
        return shell

    a = run_case()
    b = run_case(wanted=False)
    c = run_case(paused=True)
    d = run_case(ended=True)
    # E) A PAUSA DO YOUTUBE NAO CALA OUTRA FONTE (2026-11-09, revisao D2).
    e = run_case(paused=True, source='external:stremio')
    ok_a = len(a.pushes) == 1 and len(a.asyncs) == 1
    ok_b = (not b.pushes) and len(b.asyncs) == 1
    ok_c = (not c.pushes) and len(c.asyncs) == 1
    ok_d = (not d.pushes) and len(d.asyncs) == 1
    ok_e = len(e.pushes) == 1 and len(e.asyncs) == 1
    print('[%s] A dono ligado + janela apagada volta a empurrar  pushes=%d hist=%d'
          % ('PASS' if ok_a else 'FAIL', len(a.pushes), len(a.asyncs)))
    print('[%s] B dono desligado: sem pixels, historico sai      pushes=%d hist=%d'
          % ('PASS' if ok_b else 'FAIL', len(b.pushes), len(b.asyncs)))
    print('[%s] C pausa: sem pixels, historico sai               pushes=%d hist=%d'
          % ('PASS' if ok_c else 'FAIL', len(c.pushes), len(c.asyncs)))
    print('[%s] D fim: sem pixels, historico sai                 pushes=%d hist=%d'
          % ('PASS' if ok_d else 'FAIL', len(d.pushes), len(d.asyncs)))
    print('[%s] E pausa do YouTube nao cala o Stremio           pushes=%d hist=%d'
          % ('PASS' if ok_e else 'FAIL', len(e.pushes), len(e.asyncs)))
    return ok_a and ok_b and ok_c and ok_d and ok_e


def arm_release_resets(src):
    """O ESPELHO DA PAUSA MORRE QUANDO O PLAYER LARGA A SUPERFICIE (2026-11-09).

    O portao de ecran le' `yt_source_paused`; se a bandeira sobrevivesse ao
    release, a fonte SEGUINTE (Stremio, outra aba) ficava sem pixels para sempre.
    O reset e' UM metodo (`_clear_yt_source_mirrors`), chamado pelo release e
    pela troca de video: uma copia da limpeza esquecia o `ended` (revisao D4).
    """
    clear_src = extract_method(src, '_clear_yt_source_mirrors')
    ns = {'__builtins__': __builtins__}
    exec(compile(clear_src, '<clear-mirrors>', 'exec'), ns)
    clear = ns['_clear_yt_source_mirrors']

    fn_src = extract_method(src, 'on_external_captions_released')
    rel_ns = {'log': lambda *_a: None, '__builtins__': __builtins__}
    exec(compile(fn_src, '<external-released>', 'exec'), rel_ns)
    fn = rel_ns['on_external_captions_released']

    class ReleaseShell:
        def __init__(self):
            self._player_frame_seen = True
            self.yt_source_paused = True
            self.yt_source_ended = True
            self.exiting = threading.Event()
            self._external_parked = False

    shell = ReleaseShell()
    shell._clear_yt_source_mirrors = types.MethodType(clear, shell)
    fn(shell)
    ok = (shell.yt_source_paused is False
          and shell.yt_source_ended is False)
    print('[%s] release limpa o espelho da pausa  paused=%s ended=%s'
          % ('PASS' if ok else 'FAIL', shell.yt_source_paused,
             shell.yt_source_ended))
    return ok


def arm_pause_edge(src):
    """A BORDA DE PAUSA APAGA E A DE VOLTA REPINTA (2026-11-09, revisao D3).

    O blank limpa `ov.text`/`previous` e uma linha ja' FECHADA (`finalized`)
    nao volta pelo `_tick`; sem a borda de retoma o ecra ficava vazio ate' ao
    cue seguinte. O metodo real e' conduzido com uma shell falsa.
    """
    fn_src = extract_method(src, '_yt_pause_edge',
                            klass='ExternalCaptionWatcher')
    ns = {'log': lambda *_a: None, '__builtins__': __builtins__}
    exec(compile(fn_src, '<yt-pause-edge>', 'exec'), ns)
    fn = ns['_yt_pause_edge']

    class EdgeShell:
        def __init__(self, wanted=True):
            self._caption_window_shown = True
            self._caption_wanted = wanted
            self.blanks = []
            self.pushes = []

        def _blank_caption_window(self, reason):
            self.blanks.append(reason)

        def push_caption_to_window(self, text, **kw):
            self.pushes.append((text, kw))

    class EdgeObserver:
        yt_cdp_paused = True
        yt_cdp_ended = False
        last_line = 'hello world'
        last_rows = ['hello world']
        _yt_was_paused = False
        _yt_pause_epoch = 0

        def _yt_cue_payload(self):
            return None

    obs = EdgeObserver()
    sh = EdgeShell()
    obs.shell = sh
    fn(obs, True)
    pause_ok = (sh.blanks == ['youtube-paused'] and not sh.pushes
                and obs._yt_was_paused is True)
    fn(obs, False)
    resume_ok = (len(sh.pushes) == 1 and sh.pushes[0][0] == 'hello world'
                 and sh.pushes[0][1].get('instant') is True)
    obs_off = EdgeObserver()
    obs_off._yt_was_paused = True
    sh_off = EdgeShell(wanted=False)
    obs_off.shell = sh_off
    fn(obs_off, False)
    off_ok = not sh_off.pushes
    ok = pause_ok and resume_ok and off_ok
    print('[%s] borda de pausa apaga e a de volta repinta  blanks=%s '
          'pushes=%d wanted_off_pushes=%d'
          % ('PASS' if ok else 'FAIL', sh.blanks, len(sh.pushes),
             len(sh_off.pushes)))
    return ok


def run(src):
    a = arm_a(src)
    b = arm_b(src)
    print('[%s] A legenda AO VIVO sobrevive ao Alt+C  blanks=%s epoch=%s kept=%s'
          % ('PASS' if a['ok'] else 'FAIL', a['blanks'], a['epoch'], a['kept_line']))
    print('       %s' % a['log'])
    print('[%s] com a legenda DESLIGADA o ecra limpa  blanks=%s'
          % ('PASS' if b['ok'] else 'FAIL', b['blanks']))
    return a['ok'] and b['ok']


def main(argv):
    src = io.open(SHELL, encoding='utf-8').read()
    if '--neg-arm' not in argv:
        ok = run(src)
        ok = run_idle(src) and ok
        ok = arm_blank_deferred(src) and ok
        ok = arm_display_gate(src) and ok
        ok = arm_release_resets(src) and ok
        ok = arm_pause_edge(src) and ok
        print('caption-kept-on-hide-oracle: %s' % ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1

    # O MUTANTE: o `_blank_caption_window('panel-hidden')` volta a ser a unica
    # coisa que a funcao faz, como era antes da cura.
    import re
    # A ANCORA E' O SITIO, NAO A FORMA. A primeira versao deste braco mutou o
    # PRIMEIRO `if not getattr(` do ficheiro -- que nao e' esta guarda -- e deu
    # `0/1 recusado` sobre um fonte que ela nao tocou. Agora o alvo e' a linha da
    # guarda dentro do `hide_panel` e mais nada.
    guard = "if getattr(self, '_caption_wanted', False):"
    if src.count(guard) != 1:
        print('NEG-ARM IMPOSSIVEL: a guarda aparece %d vez(es) no fonte' % src.count(guard))
        return 2
    mutated = src.replace(guard, "if False:  # mutante: a guarda desarmada", 1)
    if mutated == src:
        print('NEG-ARM IMPOSSIVEL: a ancora da guarda nao esta no fonte')
        return 2
    run(mutated)
    caught_hide = not arm_a(mutated)['ok']

    # 2) A PAUSA VOLTA A RE-ARMAR (a guarda de 2026-11-03 de volta): o mutante
    # devolve o ramo antigo e o braco da pausa TEM de cair.
    old_head = ("            if (getattr(self, 'yt_source_paused', False)\n"
                "                    or getattr(self, 'yt_source_ended', False)):")
    new_head = ("            if (getattr(self, 'yt_source_paused', False)\n"
                "                    and getattr(self, '_last_caption_was_player', False)):\n"
                "                self._arm_caption_idle_hide()\n"
                "                return\n"
                + old_head)
    if src.count(old_head) != 1:
        print('NEG-ARM IMPOSSIVEL: a guarda da pausa aparece %d vez(es)'
              % src.count(old_head))
        return 2
    mutated2 = src.replace(old_head, new_head, 1)
    caught_pause = not (arm_idle(mutated2, paused=True)['blanks']
                        == ['youtube-paused-or-ended']
                        and arm_idle(mutated2, paused=True)['rearms'] == 0)

    # 3) O `on` FANTASMA VOLTA (o NameError do blank sem overlay).
    fix = "            self._caption_show_pending = False"
    if src.count(fix) != 1:
        print('NEG-ARM IMPOSSIVEL: a linha do pendente aparece %d vez(es)'
              % src.count(fix))
        return 2
    mutated3 = src.replace(fix, "            self._caption_show_pending = bool(on)",
                           1)
    caught_deferred = not arm_blank_deferred(mutated3)

    # 4) O PORTAO DE ECRAN VOLTA A `_caption_window_shown` (o estado transitorio
    # que matava a legenda depois do primeiro blank). O braco A TEM de cair.
    gate = "_caption_on = bool(getattr(self, '_caption_wanted', False))"
    if src.count(gate) != 1:
        print('NEG-ARM IMPOSSIVEL: o portao de ecran aparece %d vez(es)'
              % src.count(gate))
        return 2
    mutated4 = src.replace(
        gate,
        "_caption_on = bool(getattr(self, '_caption_window_shown', False))",
        1)
    caught_display = not arm_display_gate(mutated4)

    # 5) A PAUSA DEIXA DE BLOQUEAR OS PIXELS (o desenho congelado de 2026-11-06
    # volta como comportamento). Os bracos C e D TEM de cair.
    pause_guard = ("        if (str(source or '').startswith('external:youtube')\n"
                   "                and (getattr(self, 'yt_source_paused', False)\n"
                   "                     or getattr(self, 'yt_source_ended', False))):")
    if src.count(pause_guard) != 1:
        print('NEG-ARM IMPOSSIVEL: o portao da pausa aparece %d vez(es)'
              % src.count(pause_guard))
        return 2
    mutated5 = src.replace(
        pause_guard,
        "        if False:  # mutante: a pausa nao bloqueia os pixels",
        1)
    caught_pause_pixels = not arm_display_gate(mutated5)

    # 6) O ESPELHO DA PAUSA SOBREVIVE AO RELEASE (a bandeira presa bloqueava a
    # fonte seguinte). O braco do release TEM de cair.
    reset = ("        self.yt_source_paused = False\n"
             "        self.yt_source_ended = False")
    if src.count(reset) != 1:
        print('NEG-ARM IMPOSSIVEL: o reset do espelho aparece %d vez(es)'
              % src.count(reset))
        return 2
    mutated6 = src.replace(
        reset,
        "        self._player_frame_seen = self._player_frame_seen  # mutante",
        1)
    caught_release = not arm_release_resets(mutated6)

    # 7) O PORTAO DA PAUSA PERDE O ESCOPO DA FONTE (revisao D2): a pausa do
    # YouTube volta a calar o Stremio. O braco E TEM de cair.
    scoped = ("        if (str(source or '').startswith('external:youtube')\n"
              "                and (getattr(self, 'yt_source_paused', False)\n"
              "                     or getattr(self, 'yt_source_ended', False))):")
    if src.count(scoped) != 1:
        print('NEG-ARM IMPOSSIVEL: o escopo do portao aparece %d vez(es)'
              % src.count(scoped))
        return 2
    mutated7 = src.replace(
        scoped,
        "        if (getattr(self, 'yt_source_paused', False)\n"
        "                or getattr(self, 'yt_source_ended', False)):",
        1)
    caught_scope = not arm_display_gate(mutated7)

    # 8) A BORDA DE VOLTA DEIXA DE REPINTAR (revisao D3): o ecra fica vazio
    # depois da pausa. O braco da borda TEM de cair.
    resume = "        elif was and not now_paused:"
    if src.count(resume) != 1:
        print('NEG-ARM IMPOSSIVEL: a borda de volta aparece %d vez(es)'
              % src.count(resume))
        return 2
    mutated8 = src.replace(
        resume,
        "        elif False:  # mutante: a volta nao repinta",
        1)
    caught_resume = not arm_pause_edge(mutated8)

    caught = (caught_hide and caught_pause and caught_deferred
              and caught_display and caught_pause_pixels and caught_release
              and caught_scope and caught_resume)
    print('NEG-ARM: %s -- hide=%s pausa=%s deferred=%s display=%s '
          'pausa-pixels=%s release=%s escopo=%s retoma=%s'
          % ('PASS' if caught else 'FAIL',
             'CAUGHT' if caught_hide else 'NOT-CAUGHT',
             'CAUGHT' if caught_pause else 'NOT-CAUGHT',
             'CAUGHT' if caught_deferred else 'NOT-CAUGHT',
             'CAUGHT' if caught_display else 'NOT-CAUGHT',
             'CAUGHT' if caught_pause_pixels else 'NOT-CAUGHT',
             'CAUGHT' if caught_release else 'NOT-CAUGHT',
             'CAUGHT' if caught_scope else 'NOT-CAUGHT',
             'CAUGHT' if caught_resume else 'NOT-CAUGHT'))
    return 1 if caught else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
