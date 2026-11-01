#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# BLOCKS: BUG-20261023-01
"""SEAM-COVERAGE ORACLE -- controlo positivo E negativo por invocador real.

A LEI (Superharness, `runs/workflow-quality-loop-findings.md`, 2026-10-23, §"The
missing control"): a cobertura que conta nao e "quantos testes ha", e

    invocadores enumerados com controlo positivo a passar e controlo negativo a
    falhar NO INVOCADOR REAL  /  invocadores enumerados

e *"any unproved invoker blocks a risky landing"*. Um teste de um helper prova o
helper; nao prova que todos os chamadores chegam ao helper nem que honram o
resultado. A nota diz tambem porque isto importa neste repo em particular: um
censo que se pode desactualizar *"can itself create a false green"*, logo o
inventario tem de ser verificado por mecanismo, nao por confianca.

O QUE ESTE PORTAO FECHA. `_main/input-path-oracle.py` prova 10 bracos e apanha
10 mutantes -- mas "um mutante qualquer deixou o portao vermelho" nao diz QUAL
invocador ficou desprotegido. Uma primeira passagem deste trabalho provava 6
bracos e deixava TRES invocadores SEM controlo nenhum: o encerramento (`stop`),
o canal entre threads, e um segundo tipo de hook (teclado). O inventario
(`_main/seam-inventory.json`) enumerou nove, e este portao exige, para cada um:

  POSITIVO  o braco nomeado existe no codigo REAL e passa;
  NEGATIVO  o mutante nomeado, aplicado ao codigo real, deixa AQUELE braco
            vermelho (nao "algum" braco: aquele).

Sem estes dois, o invocador conta como NAO PROVADO e a cobertura nunca chega a
100 %. E a cobertura e impressa com a populacao ao lado.

    python _main/seam-coverage-oracle.py            # rc=0 verde, rc=2 vermelho
    python _main/seam-coverage-oracle.py --neg-arm  # rc=1 POR DESENHO

NAO lanca nada: importa a shell em processo (sem construir janela nem instalar
hook), le o inventario e o oraculo, e escreve os mutantes ao lado da shell por um
momento (prefixo `_inputpath-neg-`), apagando-os sempre no fim.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
INVENTORY = os.path.join(HERE, 'seam-inventory.json')
ORACLE_PATH = os.path.join(HERE, 'input-path-oracle.py')

ARM_ID = re.compile(r'^(C\d+[a-z]?)')


def _load(path, name):
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_inventory(path=INVENTORY):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def arm_map(oracle, mod, text):
    """{id do braco: ok} a partir dos rotulos que o oraculo imprime."""
    out = {}
    for label, ok, _got in oracle.arms(mod, text):
        m = ARM_ID.match(label)
        if m:
            out[m.group(1)] = bool(ok)
    return out


def prove(oracle, inv, real_arms, text):
    """(ok, why) para UM invocador: positivo no real, negativo naquele braco."""
    arm = inv.get('positive_arm')
    mutant = inv.get('negative_mutant')
    if arm not in real_arms:
        return False, 'o braco %r nao existe no oraculo' % (arm,)
    if not real_arms[arm]:
        return False, 'o controlo POSITIVO (%s) esta VERMELHO no codigo real' % arm
    names = {m[0] for m in oracle.MUTANTS}
    if mutant not in names:
        return False, 'o mutante %r nao existe no oraculo' % (mutant,)
    _name, _why, old, new = next(m for m in oracle.MUTANTS if m[0] == mutant)
    try:
        path = oracle.build_mutant(text, mutant, old, new)
    except RuntimeError as exc:
        return False, 'o mutante %r nao pode ser construido: %s' % (mutant, exc)
    try:
        mmod = oracle.load_module(path, '_seamcov_%s' % mutant.replace('-', '_'))
        mut_arms = arm_map(oracle, mmod, oracle._read(path))
    except Exception as exc:  # noqa: BLE001 -- ilegal tambem e apanhado
        return False, 'o mutante %r nao importa: %r' % (mutant, exc)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if mut_arms.get(arm) is None:
        return False, 'o mutante %r deixou o braco %s ausente' % (mutant, arm)
    if mut_arms[arm]:
        return False, ('o mutante %r NAO derruba o braco %s -- o controlo '
                       'negativo deste invocador nao o exercita' % (mutant, arm))
    return True, 'positivo %s verde, negativo %s derruba-o' % (arm, mutant)


def run_checks(inventory, oracle):
    text = oracle._read(oracle.SHELL)
    real_mod = oracle.load_module(oracle.SHELL, '_seamcov_real')
    real_arms = arm_map(oracle, real_mod, text)
    results = []
    for inv in inventory.get('invokers') or []:
        ok, why = prove(oracle, inv, real_arms, text)
        results.append((inv.get('id'), inv.get('boundary'), ok, why))
    return results, real_arms


def verdict(results, inventory, real_arms):
    total = len(results)
    proved = sum(1 for r in results if r[2])
    if total == 0:
        print('RED    o inventario nao enumera invocador nenhum: cobertura 0/0 '
              'e uma afirmacao vazia')
        return False
    for inv_id, boundary, ok, why in results:
        print('%-4s %-52s %s' % (inv_id, (boundary or '')[:52],
                                 'PROVED' if ok else '** UNPROVED **'))
        if not ok:
            print('       %s' % why)
    print('coverage: %d/%d invocador(es) com controlo positivo E negativo '
          '(populacao: %s)' % (proved, total, inventory.get('seam', '?')))
    print('bracos no oraculo: %d | verdes no codigo real: %d'
          % (len(real_arms), sum(1 for v in real_arms.values() if v)))
    return proved == total


def neg_arm(inventory, oracle):
    """3 mutantes do INVENTARIO (nao do codigo): cada um tem de ficar vermelho."""
    base = inventory
    mutants = []

    def unknown_arm(inv):
        bad = json.loads(json.dumps(inv))
        bad['invokers'][0]['positive_arm'] = 'C99'
        return bad
    mutants.append(('M1 um invocador aponta para um braco inexistente', unknown_arm))

    def wrong_mutant(inv):
        bad = json.loads(json.dumps(inv))
        # I3 (esconder) aponta para o mutante do ARRANQUE: nao derruba o C3.
        target = next(e for e in bad['invokers'] if e['id'] == 'I3')
        target['negative_mutant'] = 'arranque-instala'
        return bad
    mutants.append(('M2 o negativo de um invocador nao exercita o braco dele',
                    wrong_mutant))

    def empty(inv):
        bad = json.loads(json.dumps(inv))
        bad['invokers'] = []
        return bad
    mutants.append(('M3 o inventario fica vazio (cobertura 0/0)', empty))

    caught = 0
    for name, make in mutants:
        try:
            results, arms = run_checks(make(base), oracle)
            ok = verdict(results, make(base), arms)
        except Exception as exc:  # noqa: BLE001
            ok = False
            print('       (o mutante rebentou: %r)' % (exc,))
        if not ok:
            print('NEG-ARM %-56s RED as expected' % name)
            caught += 1
        else:
            print('NEG-ARM %-56s ** INERT **' % name)
    print('NEG-ARM %d of %d mutant(s) caught' % (caught, len(mutants)))
    if caught == len(mutants):
        print('NEG-ARM PASS')
        return 1
    print('VERDICT: FAIL -- %d inventario(s) mutante(s) passaram'
          % (len(mutants) - caught))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta o INVENTARIO: os tres tem de ficar VERMELHOS')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    oracle = _load(ORACLE_PATH, 'seamcov_oracle')
    inventory = load_inventory()
    try:
        if args.neg_arm:
            return neg_arm(inventory, oracle)
        results, real_arms = run_checks(inventory, oracle)
        ok = verdict(results, inventory, real_arms)
        print('SEAM-COVERAGE VERDICT %s' % ('PASS' if ok else 'FAIL'))
        return 0 if ok else 2
    finally:
        try:
            oracle.clean_mutants()
        except Exception:  # noqa: BLE001
            pass


if __name__ == '__main__':
    sys.exit(main())
