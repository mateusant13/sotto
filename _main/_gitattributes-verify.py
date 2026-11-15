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
                         capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0)).stdout.decode('utf-8', 'replace')
    for f in raw.split('\x00'):
        if not f:
            continue
        f = f.replace('\\', '/')
        if any(f.startswith(d) for d in EXCLUIR_DIR):
            continue
        yield f


def status_porcelain():
    out = subprocess.run(['git', '-C', ROOT, 'status', '--porcelain'],
                         capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0)).stdout
    return out


def julgar(f: str, hoje_eol: str, checkout_eol: str, worktree_bytes: bytes):
    """A DECISAO, pura: (tipo, detalhe) para um ficheiro.

    Existe separada do checkout porque um portao cujo juiz so' corre dentro do
    unico caminho que ele julga nao tem braco negativo possivel -- e esta casa
    ja' pagou varias vezes por um `--neg-arm` que provava a aritmetica de um
    `any()` em vez do juiz. Aqui o braco negativo alimenta a funcao REAL com
    uma fotografia falsa, sem tocar no `.gitattributes` vivo.
    """
    if checkout_eol == 'NAO SAIU':
        return 'DIVERGE', 'NAO SAIU'
    if checkout_eol == hoje_eol:
        return 'IGUAL', hoje_eol
    if hoje_eol == 'MISTO':
        b = worktree_bytes
        crlf = b.count(b'\r\n')
        bare = len(re.findall(rb'(?<!\r)\n', b))
        dom_real = 'CRLF' if crlf > bare else 'LF'
        if checkout_eol == dom_real:
            return 'MISTO', dom_real
        return 'DIVERGE', 'MISTO -> %s (esperava %s)' % (checkout_eol, dom_real)
    return 'DIVERGE', checkout_eol


def selftest() -> int:
    """O braco negativo do JUIZ: uma fotografia falsa tem de ser recusada."""
    casos = [
        # (nome, hoje, checkout, bytes do worktree, tipo esperado, detalhe esperado)
        ('uniforme igual', 'CRLF', 'CRLF', b'a\r\nb\r\n', 'IGUAL', 'CRLF'),
        ('uniforme divergente', 'CRLF', 'LF', b'a\r\nb\r\n', 'DIVERGE', 'LF'),
        ('LF que virou CRLF', 'LF', 'CRLF', b'a\nb\n', 'DIVERGE', 'CRLF'),
        ('misto no dominante', 'MISTO', 'CRLF', b'a\r\nb\r\nc\r\nd\n', 'MISTO', 'CRLF'),
        ('misto FORA do dominante', 'MISTO', 'LF', b'a\r\nb\r\nc\r\nd\n', 'DIVERGE',
         'MISTO -> LF (esperava CRLF)'),
        ('nao saiu', 'CRLF', 'NAO SAIU', b'a\r\n', 'DIVERGE', 'NAO SAIU'),
    ]
    falhas = 0
    for nome, hoje_eol, check, w, tipo_esp, det_esp in casos:
        tipo, det = julgar('x.py', hoje_eol, check, w)
        ok = (tipo, det) == (tipo_esp, det_esp)
        if not ok:
            falhas += 1
        print('  %-26s %s  %s/%s' % (nome, 'ok' if ok else 'FALHA', tipo, det))
    if falhas:
        print('SELFTEST: FAIL -- %d/%d casos' % (falhas, len(casos)))
        return 1
    print('SELFTEST: PASS -- %d/%d casos, e o caso 5 e o mutante que o juiz'
          ' tem de recusar' % (len(casos), len(casos)))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-status', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()

    if args.selftest:
        return selftest()

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
                            '--force', '--prefix=' + tmp.replace('\\', '/') + '/'],
                           input=payload.encode('utf-8'),
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
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
            with open(os.path.join(ROOT, f.replace('/', os.sep)), 'rb') as fh:
                w = fh.read()
            veredito = julgar(f, e, e2, w)
            if veredito[0] == 'IGUAL':
                iguais += 1
            elif veredito[0] == 'MISTO':
                normalizados.append((f, veredito[1]))
            else:
                divergentes.append((f, e, veredito[1]))

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
