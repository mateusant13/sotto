# NO-BUG: UM PRODUTOR POR VEZ NO ECRA -- oraculo da LEGENDA (flicker). -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""UM PRODUTOR POR VEZ NO ECRA -- oraculo da LEGENDA (flicker).

A QUEIXA DO DONO (2026-11-02), verbatim: *"as legendas tao flickando. tao
bugadas. ficam sumindo e aperecendo ou trocando a atual e a antiga ao mesmo
tempo"*.

O QUE FOI MEDIDO, e nao suposto. `_main/caption-frame-audit.py` sobre o log
vivo (23:05:00-23:08:13): **59 oscilacoes em 13,2 s**, com os quadros a
alternar A/B/A/B:

    A = ['Estados Unidos voltar, ne?', 'Mas tipo tres v tres, eles lutam']
    B = ['Mas tipo tres v tres, eles lutam com', 'menos,']

As duas vinham de PRODUTORES DIFERENTES: o laco de leitura punha a legenda
PINTADA pelo player (`A`), e o re-render de 60 ms entre leituras recompunha a
linha a partir da FAIXA com o relogio interpolado (`B`). Duas fontes, um ecra:
isso e' a oscilacao, e no corpo do ficheiro eram duas fotos diferentes (nomes
numa leitura, rects na anterior).

AS REGRAS QUE ESTE ORACULO GUARDA:

  1. O re-render da faixa (`yt_live_frame`) e' CONDICIONADO: enquanto a
     pintura esta' a fornecer a linha, ele nao corre (uma fonte so').
  2. A leitura da pintura e' UMA FOTO: `_youtube_painted` le com
     `with_rect=True` e reaproveita o rect de cada filho inalterado; nao ha'
     segunda leitura para os rects.
  3. O `EXTERNAL_CAPTION_DRAWN` e' o unico sitio que pinta (o instrumento de
     auditoria le'). Uma segunda chamada de desenho com outra fonte e' o
     defeito, e aqui ela e' procurada por NOME.
  4. O detector (`caption-frame-audit.audit`) apanha as tres formas conhecidas
     e deixa passar a sequencia limpa -- provado pelo `--neg-arm` dele.

USO:
    python _main/caption-producer-oracle.py
    python _main/caption-producer-oracle.py --neg-arm   # muta o ficheiro e exige RED
"""
from __future__ import annotations

import argparse
import importlib.util as _iu
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
CAPTIONS = os.path.join(ROOT, 'app', 'webview', 'youtube_captions.py')


def read(path):
    return io.open(path, encoding='utf-8', errors='replace').read()


def arms():
    """[(nome, ok, nota)] -- lidos do FONTE, porque a regra e' de fluxo."""
    shell = read(SHELL)
    captions = read(CAPTIONS)
    out = []

    # 1. O re-render da faixa e' condicionado pela pintura.
    guarded = ('painted_now = (time.monotonic()' in shell
               and 'if yt_mode and not painted_now:' in shell)
    out.append(('live-frame-is-gated', guarded,
                'gated=%s' % guarded))

    # 2. A pintura e' marcada como produtora da tela.
    marked = 'yt_live_paint_at = time.monotonic()' in shell
    out.append(('paint-marks-the-screen', marked, 'marked=%s' % marked))

    # 3. UMA leitura com rects; a leitura barata nao vira fonte de linhas.
    one_photo = ('painted_words(uia, UIA, hwnd=hwnd,' in shell
                 and 'with_rect=True' in shell
                 and 'with_rect=False)' not in shell)
    out.append(('one-photo-with-rects', one_photo, 'one_photo=%s' % one_photo))

    # 4. O RECT NAO ATRAVESSA LEITURAS (2026-11-03). O oposto desta arm foi
    # MEDIDO contra a legenda viva: o reaproveitamento por indice punha a
    # geometria de OUTRA foto na linha nova, e a rotacao do player juntava duas
    # linhas dele numa so' nossa, com a ordem trocada.
    no_carry = ('prev.get("text") == name' not in captions
                and 'reuse=None' not in captions)
    out.append(('rect-does-not-cross-reads', no_carry, 'no_carry=%s' % no_carry))

    # 5-bis. A CAIXA TEM DUAS LINHAS (2026-11-03). Tres linhas pintadas tem de
    # dar as DUAS ULTIMAS -- e' o que o roll-up do player mostra.
    try:
        sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
        import youtube_window as _yw
        items = [{'text': 'a b', 'left': 0, 'top': 100, 'right': 9, 'bottom': 120},
                 {'text': 'c d', 'left': 0, 'top': 130, 'right': 9, 'bottom': 150},
                 {'text': 'e f', 'left': 0, 'top': 160, 'right': 9, 'bottom': 180}]
        got = _yw.painted_rows(['a b', 'c d', 'e f'], items)
        capped = got == ['c d', 'e f']
    except Exception as exc:  # noqa: BLE001
        capped = False
        got = repr(exc)
    out.append(('rows-capped-at-2', capped, 'rows=%r' % (got,)))

    # 5. Histerese das linhas: crescer passa, encolher espera.
    settle = ('ROWS_SETTLE_S' in shell and 'def _yt_rows_settle' in shell
              and 'rows[-1].startswith(shown[-1])' in shell)
    out.append(('row-hysteresis', settle, 'settle=%s' % settle))

    # 6. UM PASSO DO PLAYER NAO ESPERA (2026-11-03). Executa a funcao REAL do
    # ficheiro: escrever, rolar e largar o fim passam no mesmo tick; uma permuta
    # nao passa. Sem esta arm, a histerese de 280 ms volta a segurar o roll-up
    # do player -- medido: 47 de 53 mudancas nunca chegaram ao ecra.
    step_ok, step_note = _player_step_arm(shell)
    out.append(('player-step-passes', step_ok, step_note))

    # 7. AS LINHAS DO PLAYER SAO AS DELE (2026-11-03). Dois defeitos medidos
    # contra a legenda viva, os dois executados na funcao real: o marcador de
    # fala no MEIO da nossa linha (duas linhas dele agrupadas) parte a linha;
    # e o mesmo filho lido duas vezes nao vira palavra repetida.
    rows_ok, rows_note = _rows_arm()
    out.append(('rows-are-the-players', rows_ok, rows_note))

    # 8. SEM FONTE, O ECRA LIMPA-SE (2026-11-03). A pintura parada durante
    # minutos deixava o ultimo quadro CONGELADO no ecra (medido 46 s de idade).
    # A regra 1:1 nao e' "mostrar o que ele mostrou", e' "mostrar o que ele
    # mostra": sem fonte, limpa-se uma vez.
    return out




def _player_step_arm(shell):
    """Executa `_yt_rows_is_player_step` do FICHEIRO, nos quatro passos."""
    try:
        start = shell.index('    def _yt_rows_is_player_step')
        end = shell.index('    def _yt_rows_settle')
    except ValueError:
        return False, 'funcao ausente do shell'
    ns = {}
    try:
        exec(compile('class T:' + chr(10) + shell[start:end], 'shell', 'exec'),
             ns)
        step = ns['T']()._yt_rows_is_player_step
    except Exception as exc:  # noqa: BLE001
        return False, 'nao executou: %r' % (exc,)
    cases = [
        ('escrever', ['a b', 'c d'], ['a b', 'c'], True),
        ('rolar', ['b', 'c d'], ['a', 'b'], True),
        ('largar-fim', ['a b'], ['a b', 'c'], True),
        ('permuta', ['c d', 'a b'], ['a b', 'c d'], True),
        ('cabeca-nova', ['x', 'y'], ['a', 'b', 'c'], False),
    ]
    bad = [name for name, rows, shown, want in cases
           if bool(step(rows, shown)) is not want]
    return not bad, 'casos errados=%r' % (bad,)


def _rows_arm():
    """Executa `rows_from_items` nos dois defeitos medidos."""
    try:
        sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
        import youtube_window as _yw
    except Exception as exc:  # noqa: BLE001
        return False, 'import falhou: %r' % (exc,)

    def item(text, left, top, height=20, width=40):
        return {'text': text, 'left': left, 'top': top,
                'right': left + width, 'bottom': top + height}

    merged = [item('da', 10, 0), item('galera', 60, 0),
              item('>>', 120, 0), item('o', 150, 0), item('brasil', 180, 0)]
    doubled = [item('nao', 10, 0), item('nao', 10, 0)]
    try:
        got_merge = _yw.rows_from_items(merged)
        got_dup = _yw.rows_from_items(doubled)
    except Exception as exc:  # noqa: BLE001
        return False, 'nao executou: %r' % (exc,)
    ok = (got_merge == ['da galera', '>> o brasil'] and got_dup == ['nao'])
    return ok, 'merge=%r dup=%r' % (got_merge, got_dup)

def neg_arm():
    """UMA MUTACAO POR ARM: cada regra tem de derrubar A SUA arm.

    Um oraculo que so' passa nao e' um detector: e' uma lista de desejos. Aqui
    cada mutacao desliga UMA regra no ficheiro e exige a arm correspondente RED.
    """
    shell = read(SHELL)
    captions = read(CAPTIONS)
    results = []

    # M1: o re-render da faixa deixa de ser condicionado pela pintura.
    m1 = shell.replace('if yt_mode and not painted_now:', 'if yt_mode:', 1)
    results.append(('gate-removed', 'live-frame-is-gated',
                    'if yt_mode and not painted_now:' not in m1))

    # M2: o rect volta a atravessar leituras.
    m2 = captions.replace('        if not with_rect:',
                          '        prev = (reuse or [None] * 99)[k] if reuse else None'
                          + chr(10) + '        if prev is not None and prev.get("text") == name:'
                          + chr(10) + '            out.append(prev); continue'
                          + chr(10) + '        if not with_rect:', 1)
    results.append(('rect-carry-back', 'rect-does-not-cross-reads',
                    not ('prev.get("text") == name' not in m2)))

    # M3: a rolagem do player volta a esperar.
    m3 = shell.replace('        if count <= len(shown) and rows[:-1] == shown[1:count]:'
                       + chr(10) + '            return True',
                       '        if count <= len(shown) and rows[:-1] == shown[1:count]:'
                       + chr(10) + '            return False', 1)
    step_ok, step_note = _player_step_arm(m3)
    results.append(('roll-waits-again', 'player-step-passes', not step_ok))

    # M4: o marcador de fala no meio da linha volta a colar as duas.
    window = read(os.path.join(ROOT, 'app', 'webview', 'youtube_window.py'))
    m4 = window.replace('if starts and current:', 'if False and current:', 1)
    rows_ok = _rows_arm_from(m4)
    results.append(('marker-merge-back', 'rows-are-the-players', not rows_ok))


    bad = 0
    for name, arm, red in results:
        print('NEG-ARM %-20s %s  (arm %s)' % (name, 'PASS' if red else 'FAIL', arm))
        if not red:
            bad += 1
    print('NEG-ARM VERDICT: %s (%d/%d)' % ('PASS' if bad == 0 else 'FAIL',
                                           len(results) - bad, len(results)))
    # A CONVENCAO DA BATERIA (2026-11-03): um `red-as-expected` declara rc=1.
    # "Apanhei todos os mutantes" E' o resultado VERMELHO que o `:expectred`
    # exige, senao o passo passa como se fosse um oraculo normal e o mutante
    # nunca e' recusado. rc=0 quando um mutante escapa (o passo fica vermelho
    # de verdade, e com a frase FAIL no log).
    return 1 if bad == 0 else 0


def _rows_arm_from(source):
    """`_rows_arm` sobre um FONTE mutado, num modulo proprio."""
    tmpdir = tempfile.mkdtemp(prefix='sotto-neg-rows-')
    path = os.path.join(tmpdir, 'youtube_window.py')
    try:
        io.open(path, 'w', encoding='utf-8', newline='').write(source)
        spec = __import__('importlib.util', fromlist=['util']).spec_from_file_location(
            'ytw_mutant', path)
        module = __import__('importlib.util', fromlist=['util']).module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001
        return True
    finally:
        try:
            os.remove(path)
            os.rmdir(tmpdir)
        except OSError:
            pass

    def item(text, left, top, height=20, width=40):
        return {'text': text, 'left': left, 'top': top,
                'right': left + width, 'bottom': top + height}

    merged = [item('da', 10, 0), item('galera', 60, 0),
              item('>>', 120, 0), item('o', 150, 0), item('brasil', 180, 0)]
    try:
        return module.rows_from_items(merged) == ['da galera', '>> o brasil']
    except Exception:  # noqa: BLE001
        return False

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    bad = 0
    results = arms()
    for name, ok, note in results:
        print('%-26s %s  %s' % (name, 'GREEN' if ok else 'RED', note))
        if not ok:
            bad += 1
    print('VERDICT: %s (%d/%d arms)' % ('PASS' if bad == 0 else 'FAIL',
                                        len(results) - bad, len(results)))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
