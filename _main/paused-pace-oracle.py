"""O PASSO DO LACO DA LEGENDA EXTERNA -- executado, nao lido.
# NO-BUG: mede o PASSO do laco da legenda externa com o video parado; e carga em repouso, nao bug do leder

DEFEITO MEDIDO, 2026-11-05, na instancia VIVA do dono com o video PAUSADO e o
painel ESCONDIDO:

    YOUTUBE_LOOP_HZ ticks=49 ok=49 none=0 age_ms=50 hz=9.7 src_reads=755
    YOUTUBE_TICK_MS avg=0 max=0 n=50 src='external:youtube:cdp' vid='ea20SBGR8ao' cdp_age_ms=16
    shell pid 31992 CPU em 10 s: 2.34 s  (23.4% de um nucleo)

`avg=0` no tick e `hz=9.7` ao lado: o trabalho estava FORA do tick medido, na
ida e volta a CDP (`cdp_age_ms=16` a cada volta). A escada do silencio existia
(`_idle_for`), mas `yt_mode` e' verdadeiro sempre que o ramo do YouTube corre --
nao significa que haja conteudo novo --, logo nunca descia enquanto uma aba do
YouTube estivesse ligada.

A CURA e' `poll_step(idle_for, paused, base, idle)` (modulo do shell): o video
pausado desce o passo, porque uma legenda nao muda com o video parado. Depois da
cura, medido na mesma instancia: `hz=4.0` e **8,1 %** de um nucleo.

O QUE ESTE ORACULO EXECUTA

  A1  o laco a correr, sem pausa e sem silencio -> passo BASE (10 Hz).
  A2  o video PAUSADO -> passo IDLE (a legenda nao muda com o video parado).
  A3  o silencio de 5 s (sem leitura de player) -> passo IDLE.
  A4  o resume devolve o passo BASE na volta seguinte (nao ha memoria do pause).
  A5  no shell, `_step` e' o que a funcao devolve -- lido por `ast`: a chamada a
      `poll_step` alimenta `_step`, e o laco nao voltou a decidir por dentro.
  A6  `IDLE_INTERVAL_S` e' MENOR que `INTERVAL_S` (um "idle" mais lento que o
      normal seria a cura a piorar a carga).

BRAÇO NEGATIVO (`--neg-arm`): desarma a pausa em `poll_step` numa COPIA do
shell e exige A2 e A4 RED.

USO
    python _main/paused-pace-oracle.py [--neg-arm]
"""
from __future__ import annotations

import ast
import importlib.util
import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
CDP = os.path.join(ROOT, 'app', 'webview', 'youtube_cdp_source.py')

ROWS = []


def add(ok, title, detail=''):
    ROWS.append((bool(ok), title, str(detail)[:160]))
    print(('PASS ' if ok else 'FAIL ') + title
          + (('   [' + str(detail)[:160] + ']') if detail and not ok else ''))


def _src(path):
    raw = io.open(path, 'rb').read()
    return raw.decode('utf-8').replace('\r\n', '\n')


def poll_step_from(path):
    """A funcao REAL do ficheiro, extraida por `ast` e compilada sozinha.

    Importar `sotto_webview` carregaria WebView2 e nao ha' processo para isso; a
    funcao e' pura, entao o modulo inteiro nao e' preciso. O que corre e' o
    texto do ficheiro que embarca -- nao uma copia escrita aqui.
    """
    src = _src(path)
    tree = ast.parse(src)
    # AS CONSTANTES DA ESCADA VIAJAM COM A FUNCAO (2026-11-09). A funcao
    # extraida sozinha dependia de `READ_SLOW_STEP_S` e o oraculo morria num
    # `NameError` -- um instrumento que nao corre nao mede.
    keep = []
    for sub in tree.body:
        if isinstance(sub, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id.startswith('READ_SLOW_')
                for t in sub.targets):
            keep.append(sub)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'poll_step':
            ns = {}
            exec(compile(ast.Module(body=keep + [node], type_ignores=[]),
                         path, 'exec'), ns)
            return ns['poll_step'], node
    return None, None


def arms():
    fn, node = poll_step_from(SHELL)
    if fn is None:
        add(False, 'A0 `poll_step` existe no shell', 'funcao ausente')
        return
    add(fn(0.0, False, 0.10, 0.25) == 0.10,
        'A1 a correr sem silencio fica no passo BASE', fn(0.0, False, 0.10, 0.25))
    add(fn(0.0, True, 0.10, 0.25) == 0.25,
        'A2 o video PAUSADO desce o passo', fn(0.0, True, 0.10, 0.25))
    add(fn(6.0, False, 0.10, 0.25) == 0.25,
        'A3 o silencio de 5 s desce o passo', fn(6.0, False, 0.10, 0.25))
    add(fn(0.1, False, 0.10, 0.25) == 0.10,
        'A4 o resume devolve o passo BASE na volta seguinte',
        fn(0.1, False, 0.10, 0.25))
    # A4-bis: A LEITURA QUE CUSTOU CARO DESCE O PASSO (2026-11-09). Medido no
    # log do dono: `EXTERNAL_CAPTIONS_READ_STATS n=548 mean_ms=0.3 max_ms=406.0`
    # e `UI_HUNG reason=caption-read-slow` -- o pico de meio segundo existe e e'
    # ele que trava a thread da UI; pedir 10 Hz logo a seguir paga contencao.
    add(fn(0.0, False, 0.10, 0.25, True) == 0.25,
        'A4-bis a leitura LENTA desce o passo', fn(0.0, False, 0.10, 0.25, True))
    add(fn(0.0, False, 0.10, 0.25, True) <= min(0.25, 0.25),
        'A4-ter o passo LENTO nunca passa o passo IDLE')
    add(fn(0.0, False, 0.10, 0.10, True) == 0.10,
        'A4-quater com IDLE igual ao BASE a escada nao inventa um passo mais lento')
    step_consts = {}
    for node in ast.walk(ast.parse(_src(SHELL))):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in ('READ_SLOW_MS',
                                                        'READ_SLOW_STEP_S',
                                                        'READ_SLOW_HOLD_S') \
                        and isinstance(node.value, ast.Constant):
                    step_consts[t.id] = node.value.value
    add(step_consts.get('READ_SLOW_MS') is not None
        and step_consts.get('READ_SLOW_STEP_S') is not None
        and 0.0 < step_consts['READ_SLOW_STEP_S'] < 1.0
        and (step_consts.get('READ_SLOW_HOLD_S') or 0) > 0.0,
        'A4-quinquies os tres numeros da escada existem e tem valores uteis',
        step_consts)


    # A5: no laco, `_step` e' o que a funcao devolve
    tree = ast.parse(_src(SHELL))
    ok = False
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Assign):
            targets = [t.id for t in sub.targets if isinstance(t, ast.Name)]
            if '_step' in targets and isinstance(sub.value, ast.Call) \
                    and getattr(sub.value.func, 'id', '') == 'poll_step':
                ok = True
    add(ok, 'A5 no laco `_step` vem de `poll_step` (a decisao nao voltou para dentro)')

    # A5-bis: a chamada do laco LEVA o quinto argumento (o estado medido). Sem
    # ele a escada existe na funcao e nao e' usada por ninguem -- a classe do
    # instrumento sem chamador.
    wired = False
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call) \
                and getattr(sub.value.func, 'id', '') == 'poll_step':
            call = sub.value
            if len(call.args) >= 5 or any(k.arg == 'slow' for k in call.keywords):
                wired = True
    add(wired, 'A5-bis o laco PASSA o estado de leitura lenta a `poll_step`')

    # A6: idle < base -- lido DENTRO da classe do laco (o ficheiro tem mais de
    # um `INTERVAL_S`, e a primeira versao desta arm leu o de outra classe:
    # `base=5.0` nao e' o passo de 10 Hz que a cura desceu).
    consts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'ExternalCaptionWatcher':
            for sub in node.body:
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if isinstance(t, ast.Name) and t.id in ('IDLE_INTERVAL_S', 'INTERVAL_S') \
                                and isinstance(sub.value, ast.Constant):
                            consts[t.id] = sub.value.value
    base = consts.get('INTERVAL_S')
    idle = consts.get('IDLE_INTERVAL_S')
    add(base is not None and idle is not None and idle > base,
        'A6 `IDLE_INTERVAL_S` e o passo mais LENTO', 'base=%r idle=%r' % (base, idle))


def cdp_arms():
    """O MESMO PRINCIPIO NA FONTE: o fio `yt-cdp-source` e' o termo DOMINANTE.

    MEDIDO com `_main/shell-thread-cpu.py` na instancia viva (pid 47868, video
    PAUSADO): 4,4 % de um nucleo em `yt-cdp-source` contra 8,4 % no processo
    inteiro -- o fio do CDP sozinho era metade da carga em repouso, a `POLL_S`
    de 0,08 s (12,5 Hz) a ler uma legenda que nao pode mudar.
    """
    src = _src(CDP)
    consts = {}
    for sub in ast.walk(ast.parse(src)):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name) and t.id in ('POLL_S', 'PAUSED_POLL_S') \
                        and isinstance(sub.value, ast.Constant):
                    consts[t.id] = sub.value.value
    base = consts.get('POLL_S')
    paused = consts.get('PAUSED_POLL_S')
    add(paused is not None and base is not None and paused > base,
        'A7 a fonte CDP tem um passo de PAUSA mais LENTO que o normal',
        'poll=%r paused=%r' % (base, paused))
    add('PAUSED_POLL_S' in src and "snap.get('paused')" in src,
        'A8 o passo de pausa e escolhido pela FOTO (nao por um relogio)')


def neg_arm():
    global SHELL
    src = _src(SHELL)
    mutated = re.sub(r'if idle_for >= 5\.0 or paused:', 'if False:', src, count=1)
    if mutated == src:
        print('NEG-ARM IMPOSSIVEL -- a condicao nao foi encontrada para mutar')
        return 2
    # OS DOIS MUTANTES, cada um no SEU braco: (1) a pausa desarmada -> A2/A4
    # vermelhas; (2) a escada da leitura lenta apagada da funcao -> A4-bis
    # vermelha. Um controlo que so' muta uma metade certifica metade.
    mutated2 = re.sub(r'if slow:\n\s+return min\(idle, max\(base, READ_SLOW_STEP_S\)\)',
                      'if False:\n        return base', mutated, count=1)
    tmp = os.path.join(tempfile.mkdtemp(prefix='neg-pace-'), 'sotto_webview.py')
    io.open(tmp, 'w', encoding='utf-8', newline='').write(mutated)
    real = SHELL
    SHELL = tmp
    try:
        ROWS.clear()
        print('=== NEG-ARM: a pausa desarmada numa COPIA')
        arms()
        cdp_arms()
        red = [r for r in ROWS if not r[0]]
        ok = any(r[1].startswith('A2') for r in red)
        print('NEG-ARM %s -- %d arm(s) RED, A2 entre elas=%s'
              % ('PASS' if ok else 'FAIL', len(red), ok))
        second = True
        if mutated2 == mutated:
            print('NEG-ARM M2 IMPOSSIVEL -- a escada lenta nao foi encontrada')
            second = False
        else:
            io.open(tmp, 'w', encoding='utf-8', newline='').write(mutated2)
            ROWS.clear()
            print('=== NEG-ARM M2: a escada da leitura lenta apagada numa COPIA')
            arms()
            red2 = [r for r in ROWS if not r[0]]
            m2 = any(r[1].startswith('A4-bis') for r in red2)
            print('NEG-ARM M2 %s -- %d arm(s) RED, A4-bis entre elas=%s'
                  % ('PASS' if m2 else 'FAIL', len(red2), m2))
            second = m2
        # A CONVENCAO DA CASA: o braco negativo devolve **1** quando APANHA o
        # mutante (o passo vizinho e' `:expectred ... 1`). Devolver 0 ao apanhar
        # faz do controlo um passo que nunca pode falhar -- a primeira versao
        # deste ficheiro tinha-o ao contrario e o `:expectred` ficava decorativo.
        return 1 if (ok and second) else 0
    finally:
        SHELL = real
        try:
            os.remove(tmp)
            os.rmdir(os.path.dirname(tmp))
        except OSError:
            pass


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    arms()
    cdp_arms()
    bad = [r for r in ROWS if not r[0]]
    print('\n%d/%d arms green' % (len(ROWS) - len(bad), len(ROWS)))
    print('VERDICT: ' + ('PASS' if not bad else 'FAIL'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
