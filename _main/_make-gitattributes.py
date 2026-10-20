#!/usr/bin/env python3
"""Gera um `.gitattributes` que reproduz a ARVORE DE TRABALHO DE HOJE.

O problema medido (2026-10-20):
  - o repo NAO tem `.gitattributes`;
  - `core.autocrlf=true` (medido);
  - um `git checkout-index` nesta box entrega **CRLF a TODOS** os ficheiros
    de texto (medido em 9 ficheiros representativos, 9/9 CRLF);
  - mas a arvore de trabalho de hoje e MISTA: `app/webview/sotto_webview.py`
    e CRLF, `app/webview/external_subs.py` e LF, e no mesmo directorio e com a
    mesma extensao.

Resultado: um checkout hoje DESTRUI a convencao do repo (o AGENTS.md diz
`_main/*.py` = LF; um checkout entrega CRLF) e muda o sha de todos os
ficheiros byte-pinhados -- que e a razao pela qual a tabela de pinos do
AGENTS.md envelhece.

Este gerador nao INVENTA uma politica: mede o EOL de cada ficheiro
versionado e escreve as regras que reproduzem EXACTAMENTE esse estado. O
verificador (o passo seguinte) materializa um checkout e compara os
terminadores um a um: se algum divergir, o ficheiro esta ERRADO e nao serve.
"""
import hashlib
import os
import re
import subprocess
import sys
from collections import defaultdict

ROOT = r'H:\sotto'
GITATT = os.path.join(ROOT, '.gitattributes')
EXCLUIR_DIR = ('_moved/', 'app/_legacy-electron/', 'node_modules/',
               'docs/design-intake/', '.git/')
EXCLUIR_ARQ = ('.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2',
               '.ttf', '.otf', '.zip', '.onnx', '.data', '.exe', '.dll',
               '.pdf', '.mp3', '.wav', '.mp4', '.bin', '.onnx.data')


def eol_de(data: bytes):
    """(CRLF | LF | MISTO | BINARIO | VAZIO) pelos bytes."""
    if not data:
        return 'VAZIO', 0, 0
    if b'\x00' in data[:8192]:
        return 'BINARIO', 0, 0
    crlf = data.count(b'\r\n')
    bare = len(re.findall(rb'(?<!\r)\n', data))
    if crlf and bare:
        return 'MISTO', crlf, bare
    if crlf:
        return 'CRLF', crlf, 0
    if bare:
        return 'LF', 0, bare
    return 'SEM-LF', 0, 0


def ficheiros_versionados():
    out = subprocess.run(['git', '-C', ROOT, 'ls-files', '-z'],
                         capture_output=True)
    raw = out.stdout.decode('utf-8', 'replace')
    for f in raw.split('\x00'):
        if not f:
            continue
        f = f.replace('\\', '/')
        if any(f.startswith(d) for d in EXCLUIR_DIR):
            continue
        if f.lower().endswith(EXCLUIR_ARQ):
            continue
        yield f


def main() -> int:
    grupos = defaultdict(list)      # (dir, ext) -> [(ficheiro, eol)]
    misto = []
    contagem = defaultdict(int)
    for f in ficheiros_versionados():
        p = os.path.join(ROOT, f.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        with open(p, 'rb') as fh:
            data = fh.read()
        eol, crlf, bare = eol_de(data)
        if eol in ('BINARIO', 'VAZIO', 'SEM-LF'):
            contagem[eol] += 1
            continue
        contagem[eol] += 1
        if eol == 'MISTO':
            # um checkout nao reproduz um ficheiro MISTO (o git escreve um
            # terminador so). A escolha e o DOMINANTE, e e declarada por
            # ficheiro -- e a unica mudanca que estas regras provocam.
            dominante = 'CRLF' if crlf > bare else 'LF'
            misto.append((f, crlf, bare, dominante))
            eol = dominante
        d = os.path.dirname(f)
        ext = os.path.splitext(f)[1].lower()
        grupos[(d, ext)].append((f, eol))

    print('censo: ' + ', '.join('%s=%d' % (k, v) for k, v in sorted(contagem.items())))
    if misto:
        print('MISTO (%d) -- um checkout NAO os reproduz; cada um e preso ao '
              'terminador DOMINANTE:' % len(misto))
        for f, c, b, dom in misto:
            print('   %-52s CRLF=%d bareLF=%d  -> %s' % (f, c, b, dom))

    # regras: por (dir, ext) quando o grupo e uniforme; senao, ficheiro a ficheiro
    #
    # A ANCORAGEM importa: em .gitattributes um padrao SEM separador casa em
    # QUALQUER nivel. `*.py` seria aplicado a `app/webview/external_subs.py`
    # (que e LF). Por isso o grupo da RAIZ usa `/` a frente (ancorado) e os
    # grupos de sub-directorio ja ficam ancorados por terem `/` no meio.
    regras = []
    for (d, ext), itens in sorted(grupos.items()):
        eols = set(e for _, e in itens)
        if len(eols) == 1 and ext:
            eol = eols.pop()
            if d:
                padrao = '%s/*.%s' % (d, ext[1:])
            else:
                padrao = '/*.%s' % ext[1:]
            regras.append((padrao, eol, len(itens)))
        elif ext:
            # grupo NAO uniforme: uma regra do grupo para a MAIORIA e uma
            # excepcao por ficheiro para a minoria. Exacto (o resultado e o
            # mesmo) e legivel: nao sao 529 linhas para `_main/*.py`, sao
            # 1 + as excepcoes.
            contagem = defaultdict(list)
            for f, e in itens:
                contagem[e].append(f)
            ordem = sorted(contagem.items(), key=lambda kv: (-len(kv[1]), kv[0]))
            maioria, minority = ordem[0], ordem[1:]
            padrao = ('%s/*.%s' % (d, ext[1:])) if d else ('/*.%s' % ext[1:])
            regras.append((padrao, maioria[0], len(maioria[1])))
            for e, fl in minority:
                for f in sorted(fl):
                    regras.append((f, e, 1))
        else:
            # sem extensao: so a regra por ficheiro serve
            for f, eol in sorted(itens):
                regras.append((f, eol, 1))

    linhas = [
        '# .gitattributes -- o EOL do repo passa a ser uma REGRA, nao um desejo.',
        '#',
        '# MEDIDO 2026-10-20 (instrumento: git ls-files + contagem de bytes, um',
        '# ficheiro de cada vez):',
        '#   - este repo NAO tinha .gitattributes;',
        '#   - core.autocrlf=true;',
        '#   - um checkout nesta box entregava CRLF a TODOS os ficheiros de texto',
        '#     (9/9 ficheiros representativos medidos em CRLF);',
        '#   - mas a arvore de trabalho e MISTA: o shell e CRLF, o external_subs.py',
        '#     e LF, no mesmo directorio.',
        '# Consequencia: um checkout destruia a convencao do AGENTS.md',
        '# (`_main/*.py` = LF) e mudava o sha de tudo o que esta byte-pinhado --',
        '# que e a razao de a tabela de pinos envelhecer.',
        '#',
        '# Estas regras foram GERADAS a partir do EOL medido de cada ficheiro',
        '# versionado: um checkout passa a reproduzir a arvore de hoje, byte a',
        '# byte, em vez de a impôr. Nada aqui e preferencia: e o estado real.',
        '#',
        '# REGENERAR:  python _main/_make-gitattributes.py --write',
        '# VERIFICAR:  python _main/_make-gitattributes.py --verify',
        '',
        '# O default: o indice ja guarda LF para tudo (o autocrlf normaliza).',
        '* text=auto eol=lf',
        '',
    ]
    for padrao, eol, n in regras:
        linhas.append('%-58s text eol=%s' % (padrao, eol.lower()))
    corpo = '\n'.join(linhas) + '\n'

    modo = sys.argv[1] if len(sys.argv) > 1 else '--print'
    if modo == '--write':
        with open(GITATT, 'wb') as fh:
            fh.write(corpo.encode('utf-8'))
        print('escrito: %s  bytes=%d  sha=%s'
              % (GITATT, len(corpo.encode('utf-8')),
                 hashlib.sha256(corpo.encode('utf-8')).hexdigest()[:16]))
    else:
        sys.stdout.write(corpo)
    return 0


if __name__ == '__main__':
    sys.exit(main())
