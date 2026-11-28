#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NO-BUG: catches a malformed caption JSON line escaping WorkerBridge._pump and killing the stdout channel (BRIDGE_PUMP_DIED), with a guard and a mutant arm
"""A MALFORMED LINE MUST NOT KILL THE CAPTION CHANNEL (medido 2026-11-27, audit #4).

O DEFEITO QUE ESTE ORACULO GUARDA. Em `WorkerBridge._pump`, o ramo de `stderr`
embrulha CADA callback (`on_stats`, `on_cost`) no seu proprio `try`, mas o ramo
de `stdout` chamava `self._consume(text, child)` DESABRIGADO dentro do `try` do
laco. Um `TypeError` numa linha JSON VALIDA com um campo do tipo errado escapava
para o `except` de fora, escrevia `BRIDGE_PUMP_DIED` e FECHAVA o stdout. Um pump
morto e' o pai a deixar de ler o filho -- a legenda congela e nao volta, que e' o
sintoma que o dono reportou a 2026-11-26.

AS DUAS DIRECOES, e nenhuma delas e' opcional:

  * ARM `linha-ma-nao-fecha-o-canal` -- sobre o codigo VIVO: tres linhas, a do
    meio levanta, e o resultado tem de ser (a) as duas linhas boas CONSUMIDAS,
    (b) ZERO `BRIDGE_PUMP_DIED`, (c) >=1 `BRIDGE_LINE_FAILED` com o contador.
  * ARM `sem-guarda-o-canal-morre` (o MUTANTE) -- sobre uma copia com a guarda
    removida: a MESMA entrada tem de produzir `BRIDGE_PUMP_DIED` e perder a linha
    seguinte. Sem esta metade o oraculo estaria a testar uma expectativa, nao o
    produto: um verde que nao sabe ficar vermelho nao prova nada.

PORTEIRO `--neg-arm`: corre SO' o mutante e exige que ele fique vermelho (rc 1).
Sem isso, alguem que apagasse a guarda veria o oraculo continuar verde.

rc: 0 PASS, 1 FAIL (a guarda nao segura, ou o mutante nao morre), 3 CANNOT-MEASURE.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")

#: A guarda, exactamente como o produto a escreve. A mutacao remove o `try`/`except`
#: e deixa a chamada nua -- que e' o codigo de ANTES da cura, nao uma invencao.
GUARD_START = "                    try:\n                        self._consume(text, child)"
GUARD_END = "                                    % (self._consume_failures, exc, text[:120]))"


def _load(path):
    import importlib.util
    sys.path.insert(0, os.path.join(REPO, "app", "webview"))
    spec = importlib.util.spec_from_file_location("sw_under_test_%d" % id(path), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_pump(mod, lines, raising_token="BOOM"):
    """Poe um stream falso por `_pump` e devolve (consumidas, mortes, falhas)."""
    bridge_cls = mod.WorkerBridge
    logs, consumed = [], []

    def fake_consume(self, line, child=None):
        if raising_token in line:
            raise TypeError("field of the wrong type")
        consumed.append(line)

    # CONSTRUCAO A SERIO, nao `object.__new__`: o `__init__` deste bridge so
    # monta estado (o processo do worker nasce em start(), nao aqui), logo
    # construir de verdade custa nada e exercita o mesmo objecto que a shell
    # usa -- o que um bypass silencioso deixaria de testar.
    b = bridge_cls(command=sys.executable, worker_path="", log=logs.append)
    b.log = lambda m: logs.append(m)
    b.last_progress_at = 0.0
    b.stderr_tail = []
    b._arm_silence = lambda *a, **k: None
    b._note_progress = lambda *a, **k: None
    b.on_stats = lambda *a, **k: None
    b.on_cost = lambda *a, **k: None
    b._rss_at = 1e18
    b._consume = fake_consume.__get__(b, type(b))
    b._pump(iter([l + "\n" for l in lines]), "stdout", None)
    died = [l for l in logs if "BRIDGE_PUMP_DIED" in l]
    failed = [l for l in logs if "BRIDGE_LINE_FAILED" in l]
    return consumed, died, failed


LINES = [
    '{"kind":"caption","text":"one"}',
    '{"kind":"status","providers_selected":"BOOM"}',
    '{"kind":"caption","text":"three"}',
]


def arm_guard_holds(mod):
    consumed, died, failed = run_pump(mod, LINES)
    bad = []
    if len(consumed) != 2:
        bad.append("consumed=%d (esperado 2: a linha DEPOIS da ma tem de chegar)"
                   % len(consumed))
    if died:
        bad.append("BRIDGE_PUMP_DIED disparou -- o canal morreu (%s)" % died[0][:120])
    if not failed:
        bad.append("nenhum BRIDGE_LINE_FAILED -- a perda nao foi CONTADA")
    return bad


def arm_mutant_dies(mod):
    """O MUTANTE: a mesma entrada sobre o codigo SEM guarda TEM de matar o canal."""
    consumed, died, failed = run_pump(mod, LINES)
    bad = []
    if not died:
        bad.append("o codigo sem guarda NAO morreu -- o braco nao mede o produto "
                   "(consumed=%d)" % len(consumed))
    if len(consumed) != 1:
        bad.append("sem guarda esperava-se 1 linha consumida, veio %d" % len(consumed))
    return bad


def build_mutant(dst):
    """Copia o shell com a guarda REMOVIDA, e devolve o caminho (ou None)."""
    with open(SHELL, "r", encoding="utf-8") as fh:
        raw = fh.read()
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    i = text.find(GUARD_START)
    if i < 0:
        return None, "a guarda nao esta no sitio esperado (o texto mudou)"
    j = text.find(GUARD_END, i)
    if j < 0:
        return None, "o fim da guarda nao foi encontrado"
    j += len(GUARD_END)
    replacement = "                    self._consume(text, child)"
    text = text[:i] + replacement + text[j:]
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return dst, None


# ── O OUTRO IRMAO DO `_pump`: `_wait` e `_spawn` (2026-11-28) ────────────────
#
# MEDIDO no log do dono (`_main/webview-run.log`, sessao pid=47516):
# `01:41:40 BRIDGE_EXIT pid=65764 ... killed=False` -- um filho que o bridge ja'
# nao tratava como vivo -- seguido de `BRIDGE_DEATH` e `restart=5`, e as
# `01:41:56` nasceu `pid=19976` com o `pid=44328` ainda a captar. Tres workers
# sobre a mesma placa dao `device-in-use`, o worker fica mudo, o cao de guarda
# mata-o, o `pending_error` (que so' uma legenda levanta) fica preso e a tela do
# dono mostra `carregando modelo...` para sempre.
#
# A guarda que o `_pump` ja' tinha (`child` EXPLICITO, nao `self.child`) faltava
# nas duas portas ao lado. Estes bracos conduzem o objecto REAL do bridge.


class _FakeChild:
    """Um filho com as tres coisas que a supervisao lhe pede."""

    def __init__(self, pid, rc=None):
        self.pid = pid
        self._rc = rc
        self.stdout = None
        self.stderr = None

    def wait(self, timeout=None):
        return self._rc if self._rc is not None else 0

    def poll(self):
        return self._rc

    def terminate(self):
        pass


def _bare_bridge(mod, logs):
    b = mod.WorkerBridge(command=sys.executable, worker_path="", log=logs.append)
    b.log = logs.append
    b.stderr_tail = []
    b.spawns = 1
    b.captions = 0
    b.statuses = 0
    b.malformed = 0
    b.deaths = 0
    b.pending_error = None
    b.last_error = {"state": "x", "text": "t", "body": ""}
    b.last_no_audio = None
    b._restart_timer = None
    b.capturing = False
    b.stopped = False
    b.killed = False
    b.loaded = True
    return b


def arm_stale_wait_does_not_own_the_bridge(mod):
    """A morte de um filho que o bridge ja' nao possui nao tem veredito."""
    logs, calls = [], []
    b = _bare_bridge(mod, logs)
    b._schedule_restart = lambda *a, **k: calls.append((a, k))
    b._status = lambda *a, **k: None
    stale, live = _FakeChild(1111, rc=1), _FakeChild(2222, rc=None)
    b.child = live
    b._wait(stale)
    bad = []
    if b.child is not live:
        bad.append("self.child largado para pid=%r" % getattr(b.child, "pid", None))
    if calls:
        bad.append("agendou um restart para a morte de OUTRO filho: %r" % (calls,))
    if b.pending_error is not None:
        bad.append("escreveu pending_error (a morte velha virou a do vivo)")
    if b.deaths:
        bad.append("contou deaths=%d para a morte de outro filho" % b.deaths)
    if not any("BRIDGE_EXIT_STALE" in l for l in logs):
        bad.append("sem BRIDGE_EXIT_STALE -- a recusa nao se nomeia")
    if any(l.startswith("BRIDGE_EXIT pid=1111") for l in logs):
        bad.append("tratou a morte velha como BRIDGE_EXIT do filho vivo")
    # E O CAMINHO LEGITIMO CONTINUA A AGIR: a guarda nao pode parir um bridge mudo.
    logs.clear()
    calls.clear()
    b.child = live
    b._wait(live)
    if b.child is not None:
        bad.append("a morte do filho VIVO nao largou self.child")
    if not calls:
        bad.append("a morte do filho VIVO nao agendou restart")
    return bad


def arm_spawn_refuses_a_second_capturer(mod):
    """Um dispositivo, um captador: `_spawn` recusa com um filho vivo."""
    logs = []
    b = _bare_bridge(mod, logs)
    b.worker_path = os.path.join(REPO, "worker", "sotto_worker.py")
    b.extra_args = []
    b.start_reason = "start"
    b.capture_requested = False
    live = _FakeChild(3333, rc=None)
    b.child = live
    before = b.spawns
    returned = b._spawn()
    bad = []
    if not any("BRIDGE_SPAWN_REFUSED reason=one-capturer-live" in l for l in logs):
        bad.append("sem BRIDGE_SPAWN_REFUSED reason=one-capturer-live")
    if b.spawns != before:
        bad.append("spawns subiu de %d para %d com um captador vivo" % (before, b.spawns))
    if returned is not live:
        bad.append("devolveu %r em vez do filho vivo" % (returned,))
    if b.child is not live:
        bad.append("trocou self.child com um captador vivo")
    return bad


WAIT_GUARD = (
    "        if self.child is not child:\n"
    "            self.log(f'BRIDGE_EXIT_STALE pid={child.pid} rc={rc} '\n"
)
WAIT_GUARD_END = "            return\n        self.last_exit = rc\n"
SPAWN_GUARD_START = "        _live = self.child\n"
SPAWN_GUARD_END = "                return _live\n"


def build_guard_mutant(dst):
    """O shell com as DUAS guardas novas removidas -- o codigo de antes da cura."""
    with open(SHELL, "r", encoding="utf-8") as fh:
        raw = fh.read()
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    i = text.find(WAIT_GUARD)
    if i < 0:
        return None, "a guarda do _wait nao esta no sitio esperado"
    j = text.find(WAIT_GUARD_END, i)
    if j < 0:
        return None, "o fim da guarda do _wait nao foi encontrado"
    text = text[:i] + "        self.last_exit = rc\n" + text[j + len(WAIT_GUARD_END):]
    i = text.find(SPAWN_GUARD_START)
    if i < 0:
        return None, "a recusa do _spawn nao esta no sitio esperado"
    j = text.find(SPAWN_GUARD_END, i)
    if j < 0:
        return None, "o fim da recusa do _spawn nao foi encontrado"
    text = text[:i] + text[j + len(SPAWN_GUARD_END):]
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return dst, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neg-arm", action="store_true",
                    help="prova que o braco sabe ficar vermelho (so' o mutante)")
    args = ap.parse_args(argv)

    if not os.path.isfile(SHELL):
        print("VERDICT: CANNOT-MEASURE why=no-shell -- %s ausente" % SHELL)
        return 3

    tmpdir = os.environ.get("TMPDIR") or "I:/cc-tmp"
    os.makedirs(tmpdir, exist_ok=True)
    mutant_path = os.path.join(tmpdir, "_bridge-pump-mutant.py")
    built, why = build_mutant(mutant_path)
    if built is None:
        print("VERDICT: CANNOT-MEASURE why=mutant-build -- %s" % why)
        return 3

    guard_path = os.path.join(tmpdir, "_bridge-guard-mutant.py")
    built_g, why_g = build_guard_mutant(guard_path)
    if built_g is None:
        print("VERDICT: CANNOT-MEASURE why=guard-mutant-build -- %s" % why_g)
        return 3

    if args.neg_arm:
        mod = _load(mutant_path)
        # `arm_mutant_dies` devolve os PROBLEMAS, nao o sucesso: lista vazia
        # significa "o mutante morreu como tinha de morrer", que e' exactamente
        # o que o braco negativo tem de provar -- apanhar = rc 1.
        bad = arm_mutant_dies(mod)
        caught = not bad
        if caught:
            print("NEG-ARM: PASS -- o codigo sem guarda do _pump morre, como tem de morrer")
        else:
            print("NEG-ARM: FAIL -- o mutante NAO derrubou o canal; o braco nao mede nada")
            print("   (%s)" % bad[0])
        mod_g = _load(guard_path)
        for label, arm in (("espera-velha-nao-manda-no-bridge",
                            arm_stale_wait_does_not_own_the_bridge),
                           ("um-dispositivo-um-captador",
                            arm_spawn_refuses_a_second_capturer)):
            # Sem as guardas o braco TEM de encontrar problemas; lista vazia
            # aqui significa um braco que nao mede o produto.
            problems = arm(mod_g)
            got = bool(problems)
            caught = caught and got
            print("  %-4s %-38s -> %s" % ('RED' if got else 'GREEN', label,
                                          problems[0] if problems else 'passou sem guarda'))
        print()
        print("NEG-ARM: %s" % ('PASS -- as tres guardas ficam vermelhas quando removidas'
                                if caught else 'FAIL'))
        return 1 if caught else 0

    ok = True
    mod = _load(SHELL)
    bad = arm_guard_holds(mod)
    if bad:
        ok = False
        print("ARM linha-ma-nao-fecha-o-canal            FAIL  %s" % bad[0])
    else:
        print("ARM linha-ma-nao-fecha-o-canal            PASS  "
              "2 linhas consumidas, 0 BRIDGE_PUMP_DIED, perda contada")

    for label, arm in (("espera-velha-nao-manda-no-bridge",
                        arm_stale_wait_does_not_own_the_bridge),
                       ("um-dispositivo-um-captador", arm_spawn_refuses_a_second_capturer)):
        bad_a = arm(mod)
        if bad_a:
            ok = False
            print("ARM %-38s FAIL  %s" % (label, bad_a[0]))
        else:
            print("ARM %-38s PASS" % label)

    mod_m = _load(mutant_path)
    bad_m = arm_mutant_dies(mod_m)
    if bad_m:
        ok = False
        print("ARM sem-guarda-o-canal-morre              FAIL  %s" % bad_m[0])
    else:
        print("ARM sem-guarda-o-canal-morre              PASS  "
              "com a guarda removida o canal morre -- o braco tem dentes")

    print("VERDICT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
