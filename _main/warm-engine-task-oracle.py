"""O motor quente tinha um `/run` para uma tarefa que NAO EXISTE.

MEDIDO 2026-11-10 nesta arvore:

  * `schtasks /query /tn SottoWarmEngine` -> **rc=1**, "O sistema nao pode encontrar
    o arquivo especificado" -- a tarefa que `_main/warm-engine/warm-engine-task.xml`
    define desde 2026-11-04 nunca foi registada nesta maquina.
  * `_main/webview-run.log`: **11** `WARM_ENGINE_START_TASK task=SottoWarmEngine
    rc=1 out="" err=""` -- uma por arranque -- e ZERO linha de sucesso.
  * o preco: `BRIDGE_LOAD_MS ms=44344 pid=30804 worker_load_s=42.59 load_bg_closed_by=deadline`
    as 21:22:30 de 2026-11-09. O `attach` ao motor quente mede 0,97 s de carga.

Um `/run` numa tarefa ausente devolve 1 e nao faz nada, em silencio. A cura e'
`ensure_warm_engine_task` (registar quando falta -- idempotente, sem admin, pelo
`_main/hidden-launch.py`), e este oraculo mede-a no WINDOWS desta maquina, nao num
fake: cria, consulta, repete, e apaga no fim.

O QUE ELE **NAO** FAZ: nao arranca o motor. `schtasks /run` no XML de verdade carrega
1,9 GB de modelo; isso e' trabalho pesado (gate `I:/!manager/tools/performance-gate.py`)
e o `_main/warm-engine-oracle.py` ja' mede o attach com um motor falso.

  python _main/warm-engine-task-oracle.py           # positivo
  python _main/warm-engine-task-oracle.py --neg-arm # o XML apontado a um ficheiro que falta

O TEXTO DO `schtasks` E' CEGO NESTE HOSPEDEIRO, e o rc nao e'. Medido 2026-11-10 (o
mesmo dia, tres nomes): `SottoWarmEngine` -> **rc=0, out=0 B**; `SottoNaoExisteXYZ`
-> **rc=1, out=0 B**; `Sotto` -> rc=0. Ou seja o **rc discrimina** presenca e o
stdout/stderr saem SEMPRE vazios por um cano, porque o `schtasks` escreve pela
consola e nao por `WriteFile` quando nao ha consola nenhuma. Consequencia para quem
ler o log do dono: `WARM_ENGINE_TASK_CREATED ... out="" err=""` NAO e' uma criacao
que falou pouco -- e' o unico desfecho que este hospedeiro sabe imprimir, e o
veredicto esta' no `rc=`. O SEGUNDO instrumento, independente do `schtasks`, e' o
FICHEIRO que o Windows guarda: `C:\Windows\System32\Tasks\<nome>` (UTF-16, sem
admin). Medido hoje: existe, mtime 2026-11-10 06:33:05, e o XML la' dentro tem
`<Triggers />` vazio, `IgnoreNew`, `PT0S` e `warm-engine-run.cmd` -- exactamente o
que o XML do repo define.

Veredicto: rc=0 PASS / rc=1 FAIL. O `--neg-arm` devolve **1 quando apanha** (a
convencao desta casa: um controlo que nao pode falhar nao e' um controlo).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
SHELL = os.path.join(REPO_ROOT, 'app', 'webview', 'sotto_webview.py')
TASK = 'SottoWarmEngineOracle'
XML = os.path.join('_main', 'warm-engine', 'warm-engine-task.xml')

def _load_hidden_launch():
    """`_main/hidden-launch.py` -- o nome tem HIFEN, logo importa-se por CAMINHO.

    (Um `import hidden_launch` levanta `ModuleNotFoundError`, medido: o modulo nao
    e' importavel por nome. A shell faz exactamente esta spec.)
    """
    path = os.path.join(HERE, 'hidden-launch.py')
    spec = importlib.util.spec_from_file_location('sotto_hidden_launch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hidden_launch = _load_hidden_launch()


def load_shell(neg_arm=False):
    """A shell NAO se importa inteira: 24 mil linhas puxam pywebview/WinForms.

    As duas funcoes que interessam vivem no modulo, mas importar o ficheiro todo
    num oraculo e' pagar 4 s para usar 40 linhas -- e o `webview` nem existe em
    algumas sessoes. Extrai-se a FONTE por `ast` e executa-se num namespace com as
    dependencias (`log`, `os`, `json`, `threading`, `REPO_ROOT`).

    Com `neg_arm`, a fonte extraida e' MUTADA antes do exec: o braco negativo tem de
    julgar o MESMO contrato contra outro codigo. (A primeira versao deste oraculo
    trocava a EXPECTATIVA no braco negativo -- `want='failing'` -- e o mutante
    passava: um controlo que nao pode falhar. Medido.)
    """
    import ast
    import threading

    src = open(SHELL, encoding='utf-8').read()
    if neg_arm:
        # M1: o `/create` perde o `/xml` -- o schtasks recusa (falta `/tr`).
        src = src.replace("'/create', '/tn', task, '/xml', rel, '/f'",
                          "'/create', '/tn', task, '/f'", 1)
        # M2: o veredicto passa a MENTIR: diz `created` sem olhar ao rc.
        src = src.replace("return 'created' if rc2 == 0 else 'failing'",
                          "return 'created'", 1)
    tree = ast.parse(src)
    wanted = {'_hidden_launch', 'ensure_warm_engine_task'}
    consts = {'WARM_ENGINE_TASK', 'WARM_ENGINE_TASK_XML'}
    body = []
    for node in tree.body:
        # As CONSTANTES vem primeiro: os `default=` das duas funcoes leem-nas, e um
        # `def` sem elas e' `NameError` no exec (medido).
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in consts for t in node.targets):
            body.append(node)
        elif isinstance(node, (ast.FunctionDef,)) and node.name in wanted:
            body.append(node)
    got = {n.name for n in body if isinstance(n, ast.FunctionDef)}
    if got != wanted:
        raise SystemExit('ORACLE-BROKEN: funcoes no fonte = %s (faltam %s)'
                         % (sorted(got), sorted(wanted - got)))
    body.sort(key=lambda n: 0 if isinstance(n, ast.Assign) else 1)
    ns = {
        'os': os,
        'json': json,
        'threading': threading,
        'REPO_ROOT': REPO_ROOT,
        'log': lambda *_a, **_k: None,
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), SHELL, 'exec'), ns)
    return ns


def query(task):
    rc, out, err = hidden_launch.run(['schtasks', '/query', '/tn', task], timeout=15)
    return rc, (out or '') + (err or '')


def delete(task):
    rc, out, err = hidden_launch.run(['schtasks', '/delete', '/tn', task, '/f'], timeout=15)
    return rc


def run(neg_arm=False):
    lines = []
    ok = True

    def arm(name, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        lines.append(('PASS' if good else 'FAIL', name, got, want))

    # A TAREFA DE TESTE NAO PODE EXISTIR ANTES: senao o arm 1 mede "ja' estava la".
    delete(TASK)
    rc0, _ = query(TASK)
    arm('A0 a tarefa de teste nao existe antes da medicao', rc0 != 0, True)

    ns = load_shell(neg_arm=neg_arm)

    first = ns['ensure_warm_engine_task'](task=TASK, xml=XML)
    rc1, out1 = query(TASK)
    arm('A1 uma tarefa ausente e REGISTADA', first, 'created')
    arm('A1b e o Windows passa a conhece-la', rc1 == 0, True)

    second = ns['ensure_warm_engine_task'](task=TASK, xml=XML)
    arm('A2 a segunda chamada e idempotente', second, 'present')
    # O XML do repo tem de continuar a ser o que define a tarefa: sem
    # `ExecutionTimeLimit=PT0S` o Windows mata o motor ao terceiro dia (F14) e
    # sem `MultipleInstancesPolicy=IgnoreNew` um segundo `/run` carrega 1,9 GB
    # outra vez (twin lock #1).
    xml_src = open(os.path.join(REPO_ROOT, XML), encoding='utf-8').read()
    arm('A3 o XML fixa PT0S (sem limite de 3 dias)',
        '<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>' in xml_src, True)
    arm('A3b o XML fixa IgnoreNew (segundo /run nao carrega)',
        '<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>' in xml_src, True)
    arm('A4 o XML aponta para o largador do repo',
        '<Command>' in xml_src and 'warm-engine-run.cmd' in xml_src, True)
    # A LINHA DE LOG TEM DE DIZER O ESTADO DO REGISTO: um `rc=1` sozinho, como o
    # que o log do dono guardou 11 vezes, nao distingue "a tarefa nao existe" de
    # "a tarefa existe e recusou arrancar".
    src = open(SHELL, encoding='utf-8').read()
    arm('A5 a linha WARM_ENGINE_START_TASK carrega registered=',
        'registered=%s' in src, True)

    delete(TASK)
    rc2, _ = query(TASK)
    arm('A6 a tarefa de teste e APAGADA no fim (maquina como estava)', rc2 != 0, True)

    for state, name, got, want in lines:
        print('%s %s\n     got=%r want=%r' % (state, name, got, want))
    caught = [n for s, n, _g, _w in lines if s == 'FAIL']
    if neg_arm:
        if ok:
            print('NEG-ARM: FAIL -- o mutante NAO foi apanhado (rc=0)')
            return 0
        print('NEG-ARM: PASS -- %d arm(s) vermelhas: %s' % (len(caught), ', '.join(caught)))
        return 1
    print('VERDICT: %s (rc=%d)' % ('PASS' if ok else 'FAIL', 0 if ok else 1))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--neg-arm', action='store_true')
    a = ap.parse_args(argv)
    return run(neg_arm=a.neg_arm)


if __name__ == '__main__':
    sys.exit(main())
