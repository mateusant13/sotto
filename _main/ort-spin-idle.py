#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: o spin-wait do onnxruntime era um imposto FIXO em repouso; custo de CPU medido e curado no fonte, nao um id do `_main/bug-ledger.json`.
"""O POOL DO ONNXRUNTIME NAO PODE GIRAR EM REPOUSO -- medido no codigo REAL do worker.

O DEFEITO (MEDIDO 2026-11-08, nesta maquina, com o worker vivo)

A arvore do dono era a maior pressao de stutter do censo do watcher (4 DMs na
mesma hora, sempre o mesmo pid). A atribuicao por FIO -- que o `watcher profile`
nao consegue fazer (`psutil.Process.threads()` devolve 0 tid) e o instrumento da
casa faz -- deu:

    pid 7144 (o WORKER, 2,3 GB): 57,4% de um nucleo
      19,8%  tid 47092  session-29-intra-op-0
      19,3%       ---   (sem nome)
       8,0%  tid 54216  session-30-intra-op-0
       4,3%  tid 62608  session-28-intra-op-0

Tres sessoes (`encoder`, `decoder`, `joint`) com 4 fios intra-op cada, e OS FIOS
DO POOL A GIRAR entre chamadas: e' o `allow_spinning` por omissao do ORT. Medido
isolado, sem dispositivo e sem audio (so' construir as tres sessoes e ficar
parado):

    SPIN ON  (padrao do ORT)   ocioso = 16,1% de um nucleo   fios=17
    SPIN OFF (a cura)          ocioso =  0,0% de um nucleo   fios=17

E o preco do passivo, medido no mesmo dia (300 chamadas seguidas num grafo
40x64): **40,0 us -> 73,4 us por chamada (+33,5 us)**. Num chunk de 560 ms com
~300 chamadas isso e' ~10 ms -- 1,8 % da janela, contra 16 % de um nucleo que
nunca mais se devolve.

O QUE ESTE ORACULO JULGA (executa o `session_options` e as sessoes REAIS)

  A1 `tres-sessoes-constroem` -- `session_options()` do worker, aplicado aos tres
     grafos que ele embarca (`encoder`, `decoder`, `joint`), constroi as sessoes.
     Sem isto as outras arms nao teriam objecto a medir.
  A2 `ocioso-dentro-do-tecto` -- com as tres sessoes VIVAS e ninguem a chamar,
     o processo gasta <= `IDLE_BUDGET_PCT` (3 %) de um nucleo na janela. Com o
     defeito mede 16,1 %; a arm falha por 5x.
  A3 `as-duas-chaves` -- o `SessionOptions` DEVOLVIDO pelo `session_options()`
     carrega `session.intra_op.allow_spinning` E `session.inter_op.allow_spinning`
     a `0`. Lida por `get_session_config_entry`, nao por texto no fonte: um
     comentario que diga a cura nao passa por aqui.
  A4 `omp-passivo` -- o processo do oraculo, com o ambiente limpo, corre o
     cabecalho do worker (o `os.environ.setdefault("OMP_WAIT_POLICY", ...)`) e o
     valor tem de ficar `PASSIVE`; com a variavel ja' definida, o `setdefault`
     NAO pode sobrepor-se ao que o dono pediu. Controlo em dois sentidos.

`--neg-arm`: escreve uma COPIA de `worker/sotto_worker.py` sem as duas chaves e
sem o `setdefault`, e exige `A3` e `A4` VERMELHAS na copia (rc=1 quando apanha).

Uso:
  python _main/ort-spin-idle.py [--seconds N] [--json]
  python _main/ort-spin-idle.py --neg-arm
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
MODELS = os.path.join(ROOT, 'worker', 'models')

#: Tecto do ocioso, em % de UM nucleo. O defeito medido dava 16,1 %; a cura da'
#: 0,0 %. Tres por cento e' folga para o import e para um tick de scheduler, e
#: AINDA assim recusa o defeito por 5x.
IDLE_BUDGET_PCT = 3.0

GRAPHS = ('encoder.onnx', 'decoder.onnx', 'joint.onnx')

#: Onde o modelo que o worker embarca vive. `config.json` manda; o nome por
#: omissao e' o do export int4 que este repo carrega.
DEFAULT_DIR = 'nemotron-3.5-asr-ptbr-onnx-int4'


def _model_dir():
    """O directorio dos tres grafos, ou '' quando os pesos nao estao no disco."""
    cfg = os.path.join(MODELS, DEFAULT_DIR)
    if all(os.path.exists(os.path.join(cfg, g)) for g in GRAPHS):
        return cfg
    for name in sorted(os.listdir(MODELS)) if os.path.isdir(MODELS) else []:
        cand = os.path.join(MODELS, name)
        if all(os.path.exists(os.path.join(cand, g)) for g in GRAPHS):
            return cand
    return ''


def _load_cpu(path=None):
    """O modulo do worker, carregado PELO CAMINHO.

    Um `import sotto_worker` por nome so' resolve com o directorio no `sys.path`,
    e um import que falha em silencio e' a classe que esta casa ja' curou com o
    `>>` do player: carrega-se pelo caminho, e o que falta e' um erro visivel.
    """
    import importlib.util
    src = path or WORKER
    # O worker importa irmaos POR NOME (`punctuation_model`, `engine_switch`, ...),
    # logo o directorio DELE tem de estar no caminho -- e tem de ser o directorio
    # do ficheiro que se carrega, nao o da copia mutante (que e' temporaria).
    for d in (os.path.dirname(os.path.abspath(WORKER)), os.path.dirname(os.path.abspath(src))):
        if d not in sys.path:
            sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location('sotto_worker_under_test', src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['sotto_worker_under_test'] = mod
    spec.loader.exec_module(mod)
    return mod


def _build(mod, model_dir, spinning_off=True):
    """As tres sessoes REAIS, com o `session_options` do proprio worker."""
    import onnxruntime as ort
    threads = int(os.environ.get('OMP_NUM_THREADS', '4'))
    sessions = []
    for g in GRAPHS:
        so = mod.session_options(ort, '', threads, encoder=(g == 'encoder.onnx'))
        sessions.append(ort.InferenceSession(os.path.join(model_dir, g), so,
                                             providers=['CPUExecutionProvider']))
    return sessions


def _idle_cpu(seconds):
    """% de UM nucleo gasto pelo ESTE processo na janela (relogio, nao confianca)."""
    import psutil
    me = psutil.Process()
    a = me.cpu_times()
    time.sleep(seconds)
    b = me.cpu_times()
    used = (b.user + b.system) - (a.user + a.system)
    return used / float(seconds) * 100.0


def _keys_of(sessions):
    """As duas chaves lidas do SessionOptions que construiu as sessoes."""
    got = {}
    for key in ('session.intra_op.allow_spinning', 'session.inter_op.allow_spinning'):
        try:
            got[key] = str(sessions[0].get_session_options().get_session_config_entry(key))
        except Exception as exc:                                 # noqa: BLE001
            got[key] = 'ERROR:%s' % (exc,)
    return got


def _hidden():
    """O largador da casa, importado PELO CAMINHO (o modulo tem hifen no nome)."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hidden-launch.py')
    spec = importlib.util.spec_from_file_location('hidden_launch', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _omp_effect(mod_path, preset=None):
    """O `OMP_WAIT_POLICY` que o cabecalho do worker deixa no ambiente.

    Executado num SUBPROCESSO com o ambiente limpo (ou com a variavel ja' posta),
    e lido do filho: e' o efeito, nao o texto do fonte.
    """
    code = (
        'import io, os, sys\n'
        'if %r is not None:\n'
        '    os.environ["OMP_WAIT_POLICY"] = %r\n'
        'else:\n'
        '    os.environ.pop("OMP_WAIT_POLICY", None)\n'
        'src = io.open(%r, encoding="utf-8").read().splitlines()\n'
        'head = []\n'
        'for line in src:\n'
        '    if line.startswith("HERE = "):\n'
        '        break\n'
        '    head.append(line)\n'
        'g = {"os": os}\n'
        'exec(compile(chr(10).join(head), "worker-head", "exec"), g)\n'
        'print(os.environ.get("OMP_WAIT_POLICY", ""))\n'
        % (preset, preset, mod_path)
    )
    env = dict(os.environ)
    env.pop('OMP_WAIT_POLICY', None)
    env['PYTHONIOENCODING'] = 'utf-8'
    # O LARGADOR DA CASA (`_main/hidden-launch.py`), nunca um Popen solto: um
    # `creationflags` sozinho e' o WEAK-FLAG que o censo AST recusa com razao --
    # CREATE_NO_WINDOW nao cobre a consola que o pai passa ao filho.
    rc, out, err = _hidden().run([sys.executable, '-c', code], capture=True,
                                 env=env, timeout=120)
    if rc != 0:
        raise RuntimeError('o filho do OMP morreu: rc=%s stderr=%r' % (rc, (err or '')[-300:]))
    # A ULTIMA linha e' o valor -- e VAZIA e' um valor legitimo: significa que
    # o cabecalho do worker nao escreveu a variavel, que e' exactamente o
    # mutante do braco negativo. Filtrar linhas vazias aqui escondia o mutante.
    raw = (out or '').replace('\r', '').splitlines()
    if not raw:
        raise RuntimeError('o filho do OMP nao imprimiu linha nenhuma: rc=%s' % rc)
    return raw[-1].strip()


def judge(model_dir, seconds, worker_path=None):
    """Devolve (ok, linhas). Cada linha nomeia o braco e o numero medido."""
    lines = []
    ok = True
    mod = _load_cpu(worker_path)
    try:
        sessions = _build(mod, model_dir)
    except Exception as exc:                                     # noqa: BLE001
        return False, ['A1 tres-sessoes-constroem      RED   %r' % (exc,)]
    lines.append('A1 tres-sessoes-constroem      GREEN sessoes=%d fios=%d'
                 % (len(sessions), len(__import__('psutil').Process().threads())))

    # A2 -- o ocioso. Mede o PROCESSO com as sessoes vivas e ninguem a chamar.
    idle = _idle_cpu(seconds)
    a2 = idle <= IDLE_BUDGET_PCT
    ok = ok and a2
    lines.append('A2 ocioso-dentro-do-tecto     %s ocioso=%.1f%% tecto=%.1f%% de 1 nucleo'
                 % ('GREEN' if a2 else 'RED  ', idle, IDLE_BUDGET_PCT))

    keys = _keys_of(sessions)
    a3 = all(v == '0' for v in keys.values())
    ok = ok and a3
    lines.append('A3 as-duas-chaves             %s %s'
                 % ('GREEN' if a3 else 'RED  ',
                    ', '.join('%s=%s' % (k.split('.')[1], v) for k, v in keys.items())))

    auto = _omp_effect(worker_path or WORKER, preset=None)
    forced = _omp_effect(worker_path or WORKER, preset='ACTIVE')
    a4 = auto == 'PASSIVE' and forced == 'ACTIVE'
    ok = ok and a4
    lines.append('A4 omp-passivo                %s automatico=%r com-a-variavel=%r'
                 % ('GREEN' if a4 else 'RED  ', auto, forced))
    return ok, lines


def neg_arm(model_dir, seconds):
    """Muta uma COPIA do worker (sem as duas chaves, sem o setdefault) e exige RED."""
    tmp = tempfile.mkdtemp(prefix='sotto-ort-spin-')
    try:
        dst = os.path.join(tmp, 'sotto_worker.py')
        text = io.open(WORKER, encoding='utf-8', newline='').read()
        # M1: as duas chaves do SessionOptions
        before = text
        text = text.replace('session.intra_op.allow_spinning', 'session.__mutated_1')
        text = text.replace('session.inter_op.allow_spinning', 'session.__mutated_2')
        # M2: o setdefault do OMP_WAIT_POLICY
        text = text.replace('os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")',
                            'pass')
        if text == before:
            print('NEG-ARM IMPOSSIVEL: nenhuma mutacao pegou no fonte')
            return 2
        io.open(dst, 'w', encoding='utf-8', newline='').write(text)
        ok, lines = judge(model_dir, seconds, worker_path=dst)
        for line in lines:
            print(line)
        caught = (not ok)
        print('NEG-ARM: %s -- mutacoes=2 (chaves do ORT, setdefault do OMP)'
              % ('PASS' if caught else 'MISS -- o mutante passou'))
        return 1 if caught else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description='o pool do ORT nao gira em repouso')
    ap.add_argument('--seconds', type=float, default=6.0,
                    help='janela da medicao de ocioso (por omissao 6 s)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--neg-arm', action='store_true')
    a = ap.parse_args(argv)

    model_dir = _model_dir()
    if not model_dir:
        print('CANNOT-MEASURE: os pesos do worker nao estao em %s' % MODELS)
        return 2

    if a.neg_arm:
        return neg_arm(model_dir, a.seconds)

    ok, lines = judge(model_dir, a.seconds)
    for line in lines:
        print(line)
    if a.json:
        print(json.dumps({'ok': ok, 'lines': lines}, ensure_ascii=False))
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
