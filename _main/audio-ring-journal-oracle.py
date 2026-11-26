#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: observabilidade: mede os tectos dos tres journals do ring -- acima do tecto a poda guarda o mais novo e encolhe o ficheiro, abaixo do tecto os bytes nao mudam, _prune nomeia gaps/index/lines e o escritor de lines fecha o seu proprio tecto, e layout.md declara constantes com o valor que o codigo le (sem numeros de linha); sem id no ledger
"""TODO STORE TEM TECTO E O TECTO E' O QUE O CODIGO LE -- o portao (2026-11-26).

O DEFEITO, medido em 2026-11-26: `worker/audio_ring.py::_prune` desce so' nas
PASTAS de dia de `history/audio/`; `index.jsonl` e `lines.jsonl` vivem na RAIZ
do ring, logo nunca eram visitados -- dois ficheiros append-only sem tecto, na
mesma casa que ja' pagou 143 GiB de `target/`. Medido: 115 018 B e 30 019 B, a
crescer a cada segmento e a cada legenda fechada.

E o segundo defeito, o que este oraculo existe para impedir: as declaracoes
viviam em docs com numeros de LINHA que envelheceram (`sotto_webview.py:835`
quando o codigo diz `:845`). Uma declaracao que aponta para a linha errada nao
declara nada, e um manifesto em prosa nao e' um portao.

O QUE ESTE ORACULO JULGA, sobre o codigo REAL e o doc REAL:

  a-trim        acima do tecto, o mais NOVO fica e o ficheiro ENCOLHE;
  b-sob-tecto   abaixo do tecto, bytes identicos (a poda nao toca no que cabe);
  c-ligacao     `_prune` nomeia os tres journals (gaps, index, lines) e o
                escritor de `lines.jsonl` chama o tecto sozinho (o ring pode
                estar desligado e o ficheiro cresceria na mesma);
  d-manifesto   `docs/layout.md` declara, para cada store, o NOME da constante
                que o codigo le -- e essa constante existe no codigo com o mesmo
                numero. Numero de linha nao entra: envelhece.

`--neg-arm`: muta copias (o helper que guarda as linhas erradas, o `_prune` sem
um dos journals, um numero do manifesto trocado) e exige as arms a VERMELHO.
Mutante apanhado = rc 1.
"""
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RING = os.path.join(ROOT, 'worker', 'audio_ring.py')
LAYOUT = os.path.join(ROOT, 'docs', 'layout.md')

#: (nome no manifesto, constante, ficheiro onde ela vive)
DECLARED = [
    ('transcricao', 'HISTORY_RETENTION_H', os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')),
    ('log vivo', 'SOTTO_LOG_CAP_MB', os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')),
    ('segmentos do ring', 'DEFAULT_CAP_MB', os.path.join(ROOT, 'worker', 'audio_ring.py')),
    ('journal de falhas', 'GAP_FILE_MAX_BYTES', RING),
    ('indices do ring', 'INDEX_FILE_MAX_BYTES', RING),
    ('ancoras de linha', 'LINES_FILE_MAX_BYTES', RING),
]


def read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arm_trim(ring):
    d = tempfile.mkdtemp(prefix='ring-a-')
    try:
        p = os.path.join(d, 'lines.jsonl')
        with open(p, 'w', encoding='utf-8') as fh:
            for i in range(500):
                fh.write(json.dumps({'t0': i, 'text': 'x' * 120}) + '\n')
        before = os.path.getsize(p)
        logs = []
        n = ring._trim_jsonl_file(p, 8 * 1024, 100, logs.append)
        after = os.path.getsize(p)
        rows = [ln for ln in read(p).splitlines() if ln.strip()]
        last = json.loads(rows[-1])
        ok = (n > 0 and after < before and len(rows) == 100
              and last['t0'] == 499 and logs)
        return ok, 'trimmed=%d before=%d after=%d rows=%d last_t0=%s log=%r' % (
            n, before, after, len(rows), last['t0'], logs[:1])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def arm_under_cap(ring):
    d = tempfile.mkdtemp(prefix='ring-b-')
    try:
        p = os.path.join(d, 'index.jsonl')
        with open(p, 'w', encoding='utf-8') as fh:
            for i in range(10):
                fh.write(json.dumps({'t0': i}) + '\n')
        before = read(p)
        logs = []
        n = ring._trim_jsonl_file(p, 512 * 1024, 2000, logs.append)
        after = read(p)
        ok = n == 0 and before == after and not logs
        return ok, 'trimmed=%d bytes_equal=%s logs=%r' % (n, before == after, logs)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def arm_wiring(src):
    """A poda nomeia os tres journals, e o escritor livre fecha o seu tecto."""
    missing = []
    for name, const in (('gaps.jsonl', 'GAP_FILE_MAX_BYTES'),
                        ('index.jsonl', 'INDEX_FILE_MAX_BYTES'),
                        ('lines.jsonl', 'LINES_FILE_MAX_BYTES')):
        pat = r"_trim_jsonl\(\s*'%s'\s*,\s*%s" % (re.escape(name), const)
        if not re.search(pat, src):
            missing.append('%s/%s fora do _prune' % (name, const))
    if not re.search(r"append_line_anchor[\s\S]{0,2000}?_trim_jsonl_file\(",
                     src):
        missing.append('append_line_anchor nao fecha o tecto do lines.jsonl')
    return (not missing), '; '.join(missing) or '3 journals no _prune + escritor livre'


def _number(expr):
    try:
        return float(eval(expr.strip(), {'__builtins__': {}}, {}))  # noqa: S307
    except Exception:                                              # noqa: BLE001
        return None


def _const_in_code(path, const):
    """O valor NUMERICO que o codigo le para `const`, ou None.

    Tres formas reais nesta casa, e o manifesto tem de aceitar exactamente
    estas -- uma quarta forma que o portao nao conheca e' um numero nao
    declarado, nao um portao que passou:

      NOME = 4320
      NOME = int(os.environ.get('OUTRO') or 4320)
      os.environ.get('NOME', '64')          # chave de ambiente com default
    """
    src = read(path)
    esc = re.escape(const)
    for pat in (r'(?m)^%s\s*=\s*([0-9][0-9_.* /]*)\s*$' % esc,
                r'(?m)^%s\s*=\s*int\(\s*os\.environ\.get\([^)]*\)\s*or\s*'
                r'([0-9][0-9_.*]*)\s*\)' % esc,
                r"os\.environ\.get\(\s*'%s'\s*,\s*'([0-9][0-9_.*]*)'\s*\)" % esc):
        m = re.search(pat, src)
        if m:
            value = _number(m.group(1))
            if value is not None:
                return value
    return None


def arm_manifest(doc):
    """Cada store declara a CONSTANTE, e a constante existe no codigo."""
    problems, seen = [], 0
    for label, const, path in DECLARED:
        row = [ln for ln in doc.splitlines()
               if ln.startswith('|') and ('`%s`' % const) in ln]
        if not row:
            problems.append('%s: `%s` nao declarada' % (label, const))
            continue
        value = _const_in_code(path, const)
        if value is None:
            problems.append('%s: `%s` nao existe em %s'
                            % (label, const, os.path.basename(path)))
            continue
        seen += 1
    return (not problems), '; '.join(problems) or '%d/%d constantes casadas' % (
        seen, len(DECLARED))


def neg_arm(ring_src, doc):
    caught = []
    tmp = tempfile.mkdtemp(prefix='ring-neg-')
    try:
        # M1: a poda passa a guardar as linhas ERRADAS (as antigas).
        bad = ring_src.replace('    keep = rows[-keep_rows:]', '    keep = rows[:keep_rows]')
        if bad == ring_src:
            print('NEG-ARM a-trim ARM-MISSING')
        else:
            p = os.path.join(tmp, 'ring_m1.py')
            with open(p, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(bad)
            ok, _ = arm_trim(load(p, 'ring_m1'))
            caught.append(('a-trim', not ok))
            print('NEG-ARM a-trim %s' % ('CAUGHT' if not ok else 'NOT-CAUGHT'))
        # M2: o _prune esquece o lines.jsonl.
        bad2 = ring_src.replace(
            "        self._trim_jsonl('lines.jsonl', LINES_FILE_MAX_BYTES, LINES_ROWS_KEEP)\n",
            '')
        if bad2 == ring_src:
            print('NEG-ARM c-ligacao ARM-MISSING')
        else:
            ok2, _ = arm_wiring(bad2)
            caught.append(('c-ligacao', not ok2))
            print('NEG-ARM c-ligacao %s' % ('CAUGHT' if not ok2 else 'NOT-CAUGHT'))
        # M3: o manifesto declara uma constante que o codigo nao tem.
        bad3 = doc.replace('`LINES_FILE_MAX_BYTES`', '`LINES_FILE_CAP_BYTES`')
        if bad3 == doc:
            print('NEG-ARM d-manifesto ARM-MISSING')
        else:
            ok3, _ = arm_manifest(bad3)
            caught.append(('d-manifesto', not ok3))
            print('NEG-ARM d-manifesto %s' % ('CAUGHT' if not ok3 else 'NOT-CAUGHT'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return len(caught) == 3 and all(c for _, c in caught)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ring_src = read(RING)
    doc = read(LAYOUT)
    ring = load(RING, 'audio_ring_live')

    arms = [('a-trim', *arm_trim(ring)),
            ('b-sob-tecto', *arm_under_cap(ring)),
            ('c-ligacao', *arm_wiring(ring_src)),
            ('d-manifesto', *arm_manifest(doc))]
    bad = 0
    for name, ok, detail in arms:
        print('[%s] %-12s %s' % ('PASS' if ok else 'FAIL', name, detail))
        if not ok:
            bad += 1

    if '--neg-arm' in argv:
        ok = neg_arm(ring_src, doc)
        print('NEG-ARM VERDICT: %s' % ('PASS' if ok else 'FAIL'))
        return 1 if ok else 0

    print('AUDIO-RING-JOURNAL VERDICT: %s (%d/%d)'
          % ('GREEN' if not bad else 'RED', len(arms) - bad, len(arms)))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
