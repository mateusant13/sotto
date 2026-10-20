#!/usr/bin/env python3
"""VERIFICA o `.gitattributes`: um checkout tem de reproduzir a arvore de HOJE.

Este e o portao do `.gitattributes`. A regra e:

  1. materializa um checkout REAL (via `git checkout-index`, que aplica as
     mesmas conversoes de um checkout) numa pasta temporaria;
  2. compara, ficheiro a ficheiro, o EOL do resultado com o EOL da arvore de
     trabalho de hoje;
  3. um ficheiro UNIFORME (CRLF ou LF) tem de sair **igual** -- se nao sair,
     a regra esta ERRADA e o portao falha;
  4. um ficheiro MISTO tem de sair no terminador DOMINANTE -- e a unica
     mudanca que estas regras provocam, e e declarada;
  5. `git status --porcelain` tem de ser IDENTICO antes e depois: as regras
     nao podem virar o indice nem mexer nas entradas staged alheias.

Nao ha "quase": ou o checkout reproduz a arvore, ou o portao diz que nao.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = r'H:\sotto'
EXCLUIR_DIR = ('_moved/', 'app/_legacy-electron/', 'node_modules/',
               'docs/design-intake/', '.git/')


def eol_de(data: bytes):
    if not data:
        return 'VAZIO'
    if b'\x00' in data[:8192]:
        return 'BINARIO'
    crlf = data.count(b'\r\n')
    bare = len(re.findall(rb'(?<!\r)\n', data))
    if crlf and bare:
        return 'MISTO'
    if crlf:
        return 'CRLF'
    if bare:
        return 'LF'
    return 'SEM-LF'


def versionados():
    raw = subprocess.run(['git', '-C', ROOT, 'ls-files', '-z'],
                         capture_output=True).stdout.decode('utf-8', 'replace')
    for f in raw.split('\x00'):
        if not f:
            continue
        f = f.replace('\\', '/')
        if any(f.startswith(d) for d in EXCLUIR_DIR):
            continue
        yield f


def status_porcelain():
    out = subprocess.run(['git', '-C', ROOT, 'status', '--porcelain'],
                         capture_output=True, text=True).stdout
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-status', action='store_true')
    args = ap.parse_args()

    antes = status_porcelain()
    ficheiros = list(versionados())
    texto = []
    hoje = {}
    for f in ficheiros:
        p = os.path.join(ROOT, f.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        with open(p, 'rb') as fh:
            e = eol_de(fh.read())
        if e in ('BINARIO', 'VAZIO', 'SEM-LF'):
            continue
        hoje[f] = e
        texto.append(f)

    # Directorio FIXO: `git checkout-index` reescreve os ficheiros que sai, e
    # o conjunto e sempre o mesmo -- logo a pasta nao cresce de corrida para
    # corrida. E nao ha apagar nada (a politica do repo e apagar pelo lixo
    # recuperavel, e este script nao tem como pedir confirmacao ao dono).
    base = os.environ.get('TMPDIR') or tempfile.gettempdir()
    tmp = os.path.join(base.replace('\\', '/'), 'gitattr-verify')
    os.makedirs(tmp, exist_ok=True)
    try:
        payload = '\0'.join(texto) + '\0'
        r = subprocess.run(['git', '-C', ROOT, 'checkout-index', '--stdin', '-z',
                            '--prefix=' + tmp.replace('\\', '/') + '/'],
                           input=payload.encode('utf-8'),
                           capture_output=True)
        if r.returncode != 0:
            print('ABORTO : checkout-index rc=%d %s'
                  % (r.returncode, r.stderr.decode('utf-8', 'replace')[:200]))
            return 1

        iguais = 0
        normalizados = []
        divergentes = []
        for f, e in hoje.items():
            out = os.path.join(tmp, f.replace('/', os.sep))
            if not os.path.isfile(out):
                divergentes.append((f, e, 'NAO SAIU'))
                continue
            with open(out, 'rb') as fh:
                e2 = eol_de(fh.read())
            if e2 == e:
                iguais += 1
            elif e == 'MISTO':
                dominante = 'CRLF' if e2 == 'CRLF' else 'LF'
                # o dominante e o que o gerador escolheu: so conta se bater
                with open(os.path.join(ROOT, f.replace('/', os.sep)), 'rb') as fh:
                    b = fh.read()
                dom_real = 'CRLF' if b.count(b'\r\n') > len(re.findall(rb'(?<!\r)\n', b)) else 'LF'
                if e2 == dom_real:
                    normalizados.append((f, dom_real))
                else:
                    divergentes.append((f, e, 'MISTO -> %s (esperava %s)' % (e2, dom_real)))
            else:
                divergentes.append((f, e, e2))

        print('ficheiros de texto versionados : %d' % len(hoje))
        print('checkout identico a hoje         : %d' % iguais)
        print('MISTO normalizado (declarado)    : %d' % len(normalizados))
        print('DIVERGENTES (inaceitavel)        : %d' % len(divergentes))
        for f, a, b in divergentes[:25]:
            print('   DIVERGE %-52s hoje=%-6s checkout=%s' % (f, a, b))
        if divergentes:
            print('VERDICT: FAIL -- o checkout NAO reproduz a arvore de hoje')
            return 1
    finally:
        print('pasta do checkout (fica para inspeccao): %s' % tmp)

    if not args.skip_status:
        depois = status_porcelain()
        if antes != depois:
            print('VERDICT: FAIL -- `git status` mudou com o .gitattributes')
            a = set(antes.splitlines())
            b = set(depois.splitlines())
            for l in sorted(b - a)[:15]:
                print('   NOVO   %s' % l[:120])
            for l in sorted(a - b)[:15]:
                print('   SUMIU  %s' % l[:120])
            return 1
        print('git status: IDENTICO (antes e depois)')

    print('VERDICT: PASS -- um checkout reproduz a arvore de hoje')
    return 0


if __name__ == '__main__':
    sys.exit(main())
