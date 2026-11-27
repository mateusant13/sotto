# NO-BUG: uma varredura cujo resultado nao pode mudar sem o directorio mudar estava a repetir-se a cada 10 s; isto e' trabalho de CAPACIDADE e o defeito foi medido no log do dono (2288 linhas BATCH_QUEUE_ORPHANS identicas).
"""O DIRECTORIO QUE NAO MUDOU NAO SE RELE -- executado, nao lido.

DEFEITO MEDIDO, 2026-11-24, no log vivo do dono (`_main/webview-run.log`):

    BATCH_QUEUE_ORPHANS manifests_without_audio=2 dir=I:\\cc-tmp\\sotto-batch-queue   x2288
    THREAD_CPU total=10% top=sotto-batch-executor:5% ...

O executor chama `BatchQueue.refresh()` a cada `poll_s` (10 s, 360 vezes/hora) e
cada chamada fazia `listdir` + `open`+`json.load` por manifesto, com o resultado
sempre igual: 2288 linhas identicas e 4,7 % de um nucleo em media (a shell toda
media 12,6 %). A guarda e' o `st_mtime_ns` do PROPRIO directorio -- que muda
quando um nome entra ou sai -- e custa um `stat`.

O QUE ESTE ORACULO EXECUTA (o modulo REAL, sem dispositivo, sem parakeet):

  A1  a primeira leitura de uma fila nova LE o directorio (`scans=1`).
  A2  a segunda leitura com o directorio inalterado NAO le (`scan_skips=1`,
      `scans` continua 1) e devolve o MESMO retrato.
  A3  um manifesto novo (orfao) faz a leitura seguinte LER (`scans=2`).
  A4  o mesmo conjunto de orfaos NAO se repete no log (uma linha, nao duas).
  A5  o numero que muda (2 -> 3 orfaos) volta a ser dito no instante em que muda.
  A6  `force=True` le sempre, mesmo com o directorio inalterado.
  A7  um payload que chega (nome novo no directorio) faz a lista de orfaos cair
      a zero -- a guarda nao pode esconder a chegada do audio.

BRACO NEGATIVO (`--neg-arm`): M1 desarma a guarda da LISTA DE NOMES numa COPIA
do modulo -> A2 RED; M2 desarma a dedupe da linha -> A4 RED. Devolve 1 quando
APANHA os dois (a convencao da casa: `:expectred ... 1`).

USO
    python _main/batch-queue-scan-oracle.py [--neg-arm]
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, 'app', 'webview', 'batch_queue.py')

ROWS = []


def add(ok, title, detail=''):
    ROWS.append((bool(ok), title, str(detail)[:160]))
    print(('PASS ' if ok else 'FAIL ') + title
          + (('   [' + str(detail)[:160] + ']') if detail and not ok else ''))


def load_module(path, name='bq_scan_under_test'):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arms(path=MODULE):
    mod = load_module(path)
    tmp = tempfile.mkdtemp(prefix='scan-oracle-')
    lines = []
    try:
        q = mod.BatchQueue(path=tmp, log_fn=lines.append)
        add(q.scans == 1 and q.scan_skips == 0,
            'A1 a primeira leitura de uma fila nova LE o directorio',
            'scans=%r skips=%r' % (q.scans, q.scan_skips))
        first = q.refresh()
        add(q.scans == 1 and q.scan_skips == 1,
            'A2 o directorio inalterado NAO se rele',
            'scans=%r skips=%r' % (q.scans, q.scan_skips))
        add(first == q.entries, 'A2-bis o retrato devolvido e o mesmo',
            '%r vs %r' % (len(first), len(q.entries)))

        def manifest(eid):
            with io.open(os.path.join(tmp, eid + '.json'), 'w', encoding='utf-8') as h:
                json.dump({'id': eid, 'state': 'queued', 'created': '2026-11-24'}, h)

        manifest('0001-1-1')
        q.refresh()
        add(q.scans == 2 and any('BATCH_QUEUE_ORPHANS' in l for l in lines),
            'A3 um manifesto novo faz a leitura seguinte LER e dizer o orfao',
            'scans=%r lines=%r' % (q.scans, len(lines)))
        before = sum(1 for l in lines if 'BATCH_QUEUE_ORPHANS' in l)
        manifest('0002-2-2')          # muda o nome dentro do MESMO directorio
        q.refresh()
        after = sum(1 for l in lines if 'BATCH_QUEUE_ORPHANS' in l)
        add(after - before == 1,
            'A5 o numero NOVO e dito UMA vez (a leitura seguinte ja nao mudou nada)',
            'antes=%r depois=%r' % (before, after))
        manifest('0003-3-3')
        q.refresh()
        n3 = sum(1 for l in lines if 'BATCH_QUEUE_ORPHANS' in l)
        q.refresh()
        n3b = sum(1 for l in lines if 'BATCH_QUEUE_ORPHANS' in l)
        add(n3b == n3, 'A4 o MESMO conjunto de orfaos nao se repete', '%r vs %r' % (n3, n3b))
        q.refresh(force=True)   # `force` le' SEMPRE: a dedupe tem de segurar aqui
        n3c = sum(1 for l in lines if 'BATCH_QUEUE_ORPHANS' in l)
        add(n3c == n3, 'A4-bis a dedupe segura mesmo numa leitura forcada',
            '%r vs %r' % (n3, n3c))
        saidos = [l.split('manifests_without_audio=')[1].split()[0]
                  for l in lines if 'BATCH_QUEUE_ORPHANS' in l]
        add(saidos == ['1', '2', '3'],
            'A5-bis a linha diz o numero CERTO em cada mudanca', saidos)
        skips = q.scan_skips
        q.refresh(force=True)
        add(q.scan_skips == skips and q.scans >= 4,
            'A6 `force=True` le sempre', 'scans=%r skips=%r' % (q.scans, q.scan_skips))
        # um payload que chega e' um NOME novo no directorio: a guarda tem de ceder.
        # A TESTEMUNHA E' A LEITURA, NAO O CONTEUDO (medido 2026-11-27). Este braco
        # dizia `all(...) is False or True`, uma tautologia: nunca podia ficar
        # vermelho, e a sua afirmacao era a MESMA do A7-bis. A afirmacao propria
        # deste braco e' "a guarda nao esconde a chegada" -- e o que a mede e' o
        # contador de leituras. `batch_queue.py:280-284` regista porque: a guarda
        # por `st_mtime_ns` FALHOU aqui (NTFS actualiza o carimbo do directorio de
        # forma preguicosa; a leitura seguinte disse `scans=1` e o bloco novo ficou
        # escondido). Uma linha que olhasse so' o conteudo passaria com essa guarda
        # de volta; esta olha o contador, e o mutante M3 e' exactamente essa guarda.
        scans_before_payload = q.scans
        with io.open(os.path.join(tmp, '0001-1-1.f32'), 'wb') as h:
            h.write(b'\x00' * 8)
        got = q.refresh()
        add(q.scans == scans_before_payload + 1,
            'A7 a chegada do payload NAO e escondida pela guarda',
            'scans %r -> %r' % (scans_before_payload, q.scans))
        ids = [e['id'] for e in got]
        add('0001-1-1' in ids,
            'A7-bis o bloco cujo payload chegou ENTRA na fila',
            ids)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def neg_arm():
    src = io.open(MODULE, 'rb').read().decode('utf-8').replace('\r\n', '\n')
    m1 = src.replace("            if not force and stamp == getattr(self, '_scan_stamp', None):",
                     '            if False:', 1)
    m2 = src.replace('if orphans and orphans != getattr(self, \'_orphans_logged\', 0):',
                     'if orphans:', 1)
    # M3 e' a guarda HISTORICA, a que ja' esteve no produto: um carimbo que nao ve'
    # a chegada de um payload. E' o que o A7 mede pelo contador de leituras -- com
    # o mutante aplicado, o `.f32` entra no directorio e o `refresh()` seguinte
    # responde `scan_skips` em vez de ler, ou seja o bloco novo fica escondido.
    m3 = src.replace('            stamp = tuple(names)',
                     "            stamp = tuple(n for n in names if n.endswith('.json'))", 1)
    mutants = (('M1 a guarda da lista de nomes desarmada', m1, 'A2'),
               ('M2 a dedupe da linha desarmada', m2, 'A4'),
               ('M3 a guarda deixa de ver o payload que chega', m3, 'A7'))
    if any(text == src for _title, text, _want in mutants):
        print('NEG-ARM IMPOSSIVEL -- um mutante nao foi encontrado no ficheiro')
        return 0
    tmp = tempfile.mkdtemp(prefix='scan-neg-')
    path = os.path.join(tmp, 'batch_queue.py')
    caught = 0
    try:
        for title, text, want in mutants:
            io.open(path, 'w', encoding='utf-8', newline='\n').write(text)
            ROWS.clear()
            print('=== NEG-ARM: %s numa COPIA' % title)
            arms(path)
            red = [r for r in ROWS if not r[0]]
            hit = any(r[1].startswith(want) for r in red)
            print('NEG-ARM %s %s -- %d arm(s) RED, %s entre elas=%s'
                  % (title.split()[0], 'PASS' if hit else 'FAIL', len(red), want, hit))
            caught += 1 if hit else 0
        print('NEG-ARM %s -- %d/%d mutantes apanhados'
              % ('PASS' if caught == len(mutants) else 'FAIL', caught, len(mutants)))
        return 1 if caught == len(mutants) else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    arms()
    bad = [r for r in ROWS if not r[0]]
    print('\n%d/%d arms green' % (len(ROWS) - len(bad), len(ROWS)))
    print('VERDICT: ' + ('PASS' if not bad else 'FAIL'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
