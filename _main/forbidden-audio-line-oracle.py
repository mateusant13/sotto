#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O erro 'audio device is in use' nao pode voltar a aparecer. Porta fechada.

DONO, 2026-10-17, verbatim: *"o painel ta com erro vermelho. ta falando que 'audio
device is in use' sendo q nao e pra acontecer nunca e nem depender disso"*.

QUE HISTORIA ESTA GUARDA, em ordem:

  1. O worker pintava `state="error"` em CADA degrau que nao abria. `error` esta
     em WORKER_ERROR_STATES, entao a escada working Customers Passing ac点亮ava o
     painel vermelho a cada rotacao. Corrigido em `fbe830b` para
     `device-open-refused`, que nao casa com nada do vocabulario de falha.

  2. MAS O CASO TERMINAL FICOU. Quando a escada acaba, o worker emitia
     `state="error"` com `reason="ladder-exhausted"` e o `detail` CRU — e o
     `0x8889000A` que o dono viu estava EXACTAMENTE ai. `detail` esta em
     STATUS_BODY_FIELDS, portanto era renderizado no painel e depois traduzido por
     `human_audio_error` na frase vermelha. Um evento, tres sítios por onde a frase
     chegava ao vidro do dono.

  3. O que este oráculo afirma, e porque nao basta olhar para o texto:
     o rodapé, o corpo E o `kind` que este evento produz NAO podem conter a frase
     proibida, o codigo hexadecimal, nem a palavra que dispara o vermelho. Isto
     corre as FUNCOES REAIS do shell, extraidas do ficheiro com `ast` e executadas
     num namespace próprio — nao ha copia, nao ha reimplementacao, nao ha drift.

Because importing `sotto_webview.py` runs the app (argparse, the window, the
worker), the functions are lifted out of the real source instead. If someone
renames one, this raises rather than quietly passing on a stale copy.
"""
import ast
import io
import re
import sys

SHELL = r'H:\sotto\app\webview\sotto_webview.py'

# The exact event `worker/sotto_worker.py` emits when the ladder is spent, after
# the 2026-10-17 fix. `detail` is neutral; `denials` carries the raw HRESULTs and
# is NOT in STATUS_BODY_FIELDS, so it never reaches the panel.
LADDER_EXHAUSTED = {
    'type': 'status',
    'state': 'audio-endpoint-unavailable',
    'stage': 'open-stream',
    'reason': 'ladder-exhausted',
    'detail': ('Sotto tried 12 of 12 audio endpoints and none was free '
               'at this moment'),
    'denials': ['CABLE Input [wasapi]: WasapiError: Initialize(SHARED|LOOPBACK) '
                'failed: <no description> (0x8889000A)'],
    'attempt': 12,
    'of': 12,
}

# The event as it was BEFORE the fix, kept so this oracle proves it can still say
# "no" to the old shape. If a future change makes the old event pass, the guard has
# stopped guarding.
LADDER_EXHAUSTED_OLD = dict(LADDER_EXHAUSTED, state='error',
                            detail=LADDER_EXHAUSTED['denials'][0])

FORBIDDEN_SUBSTRINGS = [
    '0x8889000A',
    'audio device is already in use',
    'already in use by another program',
    'Close whatever is holding it',
    'Initialize(SHARED|LOOPBACK)',
    'WasapiError',
]

NEEDED_NAMES = {
    'worker_status_kind', 'worker_status_text', 'worker_status_body',
    'human_audio_error',
}
NEEDED_CONSTS = {
    'FAILURE_WORDS_RE', 'WORKER_ERROR_STATES', 'HEALTHY_DONE_VERDICTS',
    'WORKER_NO_AUDIO_VERDICTS', 'WORKER_NO_AUDIO_STATES',
    'WORKER_WARMUP_STATES',
    'WORKER_CAPTURING_STATES', 'STATUS_BODY_FIELDS', 'STATUS_BODY_MAX',
    'HRESULT_AUDIO_READINGS', 'FALSE_AUDIO_ABSENT_RE', 'CAPTURE_NOT_STARTED',
}

# NOT the real filename. Compiling the lifted unit under `sotto_webview.py`'s own
# name makes every traceback point at a line of the SHELL that has nothing to do
# with the code that raised -- which is how a missing constant turns into a
# confident, completely wrong answer about which function is broken.
LIFTED_NAME = '<lifted from %s>'


def lift(path):
    src = io.open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    pieces, found, consts = [], set(), set()
    for node in tree.body:
        names = []
        if isinstance(node, ast.FunctionDef):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        for n in names:
            if n in NEEDED_NAMES:
                pieces.append(ast.get_source_segment(src, node))
                found.add(n)
            elif n in NEEDED_CONSTS:
                pieces.append(ast.get_source_segment(src, node))
                consts.add(n)
    missing = (NEEDED_NAMES | NEEDED_CONSTS) - found - consts
    if missing:
        raise SystemExit('shell shape changed; update this oracle: missing %s'
                         % sorted(missing))
    return '\n\n'.join(pieces)


def main():
    # The lifted code calls `re` (the FAILURE_WORDS_RE pattern) and nothing else
    # outside its own module. Handing it the real `re` keeps the extracted text
    # byte-identical to the file instead of prepending an import and pretending
    # the source is the same.
    import re as _re
    ns = {'re': _re}
    exec(compile(lift(SHELL), LIFTED_NAME % 'sotto_webview.py', 'exec'), ns)

    bad = 0
    print('FORBIDDEN-AUDIO-LINE ORACLE')
    print('  shell: %s' % SHELL)
    print('  lifted: %d functions, %d constants (the real source, ast)'
          % (len(NEEDED_NAMES), len(NEEDED_CONSTS)))
    print('')

    def check(label, event, must_be_clean=True):
        nonlocal bad
        kind = ns['worker_status_kind'](event.get('state'), event)
        footer = ns['worker_status_text'](
            event.get('state'), event, 'neutral default line')
        body = ns['worker_status_body'](event.get('state'), event)
        blob = '%s\n%s\n%s' % (kind, footer, body)
        hits = [f for f in FORBIDDEN_SUBSTRINGS if f.lower() in blob.lower()]
        red = ns['FAILURE_WORDS_RE'].search(event.get('state') or '') is not None
        clean = (not hits) and not red and kind != 'error'
        if must_be_clean and not clean:
            bad += 1
        print('%s  %s' % ('PASS ' if clean else 'FAIL ', label))
        print('        kind=%s  state_matches_failure_words=%s' % (kind, red))
        print('        footer=%s' % footer)
        print('        body  =%s' % (body[:180] or '<empty>'))
        if hits:
            print('        FORBIDDEN PRESENT: %s' % hits)
        print('')

    # 1. The event as it is emitted today.
    check('today: audio-endpoint-unavailable (must be clean)', LADDER_EXHAUSTED)

    # 2. NEGATIVE ARM: the same payload under the OLD state must still be caught.
    #    This is the line that keeps the guard a guard. Without it, the oracle
    #    would go GREEN the day someone widens the vocabulary, which is precisely
    #    the failure this whole file exists to prevent.
    print('NEG-ARM: the old shape must still be rejected\n')
    ns2 = {'re': _re}
    exec(compile(lift(SHELL), LIFTED_NAME % 'sotto_webview.py (neg-arm)', 'exec'), ns2)
    old_kind = ns2['worker_status_kind'](
        LADDER_EXHAUSTED_OLD.get('state'), LADDER_EXHAUSTED_OLD)
    old_footer = ns2['worker_status_text'](
        LADDER_EXHAUSTED_OLD.get('state'), LADDER_EXHAUSTED_OLD, 'neutral')
    old_blob = '%s %s' % (old_kind, old_footer)
    old_hits = [f for f in FORBIDDEN_SUBSTRINGS if f.lower() in old_blob.lower()]
    neg_ok = (old_kind == 'error') and bool(old_hits)
    if not neg_ok:
        bad += 1
    print('%s  NEG-ARM: old state=error still renders the forbidden sentence'
          % ('PASS ' if neg_ok else 'FAIL '))
    print('        kind=%s  forbidden_found=%s' % (old_kind, old_hits))
    print('')

    print('VERDICT: %s' % ('RED' if bad else 'GREEN'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())