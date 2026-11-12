"""A escala do que a especificacao descreve -- medido do disco, nunca de uma lista escrita a mao.

Responde a uma pergunta so: **quantos ficheiros e quantas linhas de produto existem, por superficie**.
Existe porque o `docs/spec/README.md` publica esses numeros e um numero publicado sem o comando que o
produziu apodrece (a regra deste repo: uma afirmacao sobre o mundo carrega o comando).

As quatro decisoes que mudam o resultado, e por isso estao escritas aqui:

1. **extensoes de produto** -- `.py`, `.js`, `.mjs`, `.html`, `.css`, `.json`, `.svg`. Um `.map`, um
   `.lock` e um `.png` nao sao comportamento.
2. **directorios excluidos por NOME, em qualquer profundidade** -- os de `SKIP_DIRS`, mais `models`
   e `runs`, que dentro de `worker/` guardam pesos e artefactos de corrida, nao codigo.
3. **linhas** contadas com `str.splitlines()` (a mesma conta que o resto do repo usa).
4. **enquadramento** -- um ficheiro que nao se deixa ler entra na contagem de ficheiros e NAO em
   linhas, e o total diz quantos foram (`unreadable`), porque uma linha a menos sem aviso e' uma
   medida que mente.

Uso:
    python _main/spec-scale.py            # a tabela, pronta a colar
    python _main/spec-scale.py --json     # as mesmas quatro linhas em JSON
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = frozenset({'.git', 'node_modules', '_legacy', '_cache', '__pycache__', '.venv', 'dist',
                       'build', 'models', 'runs'})
PRODUCT_EXTS = ('.py', '.js', '.mjs', '.html', '.css', '.json', '.svg')
SURFACES = (
    ('app/webview', ('app/webview/**/*.py (a shell e os seus modulos)', ('.py',))),
    ('worker', ('worker/**/*.py (o motor de transcricao)', ('.py',))),
    ('app/panel', ('app/panel/** (a UI web: HTML/CSS/JS + os temas)', PRODUCT_EXTS)),
)


def measure(base: str, exts: tuple) -> dict:
    files = lines = unreadable = 0
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, base)):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if not name.endswith(exts):
                continue
            files += 1
            try:
                with open(os.path.join(dirpath, name), encoding='utf-8', errors='replace') as fh:
                    lines += len(fh.read().splitlines())
            except OSError:
                unreadable += 1
    return {'files': files, 'lines': lines, 'unreadable': unreadable}


def main(argv: list[str]) -> int:
    rows = []
    for base, (label, exts) in SURFACES:
        m = measure(base, exts)
        rows.append({'surface': label, 'base': base, **m})
    total = {'files': sum(r['files'] for r in rows), 'lines': sum(r['lines'] for r in rows),
             'unreadable': sum(r['unreadable'] for r in rows)}
    if '--json' in argv:
        print(json.dumps({'rows': rows, 'total': total}, ensure_ascii=False, indent=1))
        return 0
    print(f'{"superficie":<52} {"ficheiros":>9} {"linhas":>9}')
    for r in rows:
        print(f'{r["surface"]:<52} {r["files"]:>9} {r["lines"]:>9}')
    print(f'{"total de produto lido":<52} {total["files"]:>9} {total["lines"]:>9}')
    if total['unreadable']:
        print(f'nao lidos (contados em ficheiros, fora das linhas): {total["unreadable"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
