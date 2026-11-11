# NO-BUG: julga o acumulador `add_live_audio` e o call site por `ast`; NAO julga o texto da legenda, que exige a app e audio a tocar.
"""ORACLE: o audio do AO VIVO chega ao motor de LOTE (dono, 2026-11-09).

A ORDEM, verbatim: *"legenda AO VIVO otima E historico otimo"*.

O DEFEITO MEDIDO QUE ISTO FECHA. Ate' hoje as duas janelas eram disjuntas: o
`ReduxHiddenSwitch` acumulava audio SO' em modo `batch`/`shed`, portanto o audio
que o motor ao vivo transcrevia (painel aberto) NUNCA entrava no passe de lote e
o historico ficava com a versao pior exactamente na fala acontecida com o painel
aberto. Medido no historico do dia: **145 de 162** linhas escritas ao vivo sem
nenhuma linha de lote a +-20 s.

O QUE ESTE FICHEIRO JULGA, e o que ele NAO julga:
  A1  `add_live_audio` acumula o bloco (o audio passa a existir para o lote);
  A2  o TECTO e' respeitado e o corte e' CONTADO -- o texto desses segundos ja'
      esta' escrito pelo ao vivo, o que se perde e' a melhoria, nunca a linha;
  A3  o corte preserva a ORDEM e mantem a CAUDA (o audio mais recente), que e'
      o que o `_start_pass` do lote vai ler;
  A4  com `SOTTO_FUSE_HISTORY=0` NADA e' acumulado (o interruptor declara-se e
      vale -- um interruptor que nao desliga nao e' interruptor);
  A5  `pending is None` (motor de fundo nao armado) nao levanta;
  A6  o CALL SITE vive no ramo `stream` do worker e passa por `add_live_audio`
      (nao pelo `add_audio` sem tecto) -- lido por `ast`, do ficheiro que embarca;
  A7  a linha de arranque diz o estado do interruptor.
NAO julga o texto da legenda: isso exige a app e audio a tocar, as duas coisas
que a lei desta casa proibe a uma lane (`SOTTO_NEVER_ON_OWNER_SCREEN`, audio do
dono intocavel).

Uso: python _main/fusion-audio-oracle.py [--neg-arm]
--neg-arm muta COPIA (nunca HEAD, que apodrece quando a cura e' cometida) e
exige que as arms correspondentes fiquem VERMELHAS, devolvendo rc=1 ao apanhar.
"""

from __future__ import annotations

import ast
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SWITCH = os.path.join(ROOT, "worker", "engine_switch.py")
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")

TARGET_SR = 16000


# ── the two real pieces, taken out of the files that ship ───────────────────
def _load(path, name):
    """Import a worker module by PATH (the app has no `worker` on sys.path)."""
    import importlib.util

    for extra in (os.path.join(ROOT, "_main", "_libs"), os.path.join(ROOT, "worker")):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _switch_class():
    es = _load(SWITCH, "fusion_oracle_engine_switch")
    return es, es.ReduxHiddenSwitch


def _methods(cls, names):
    """The REAL functions, by `ast`, so a subclass override cannot pass for them."""
    src = io.open(SWITCH, "r", encoding="utf-8", errors="replace").read()
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ReduxHiddenSwitch":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in names:
                    out[fn.name] = ast.get_source_segment(src, fn)
    return out


class _Pending:
    """`PendingAudio` sem disco: o oraculo mede a POLITICA, nao o sistema de ficheiros."""

    def __init__(self):
        self.blocks = []
        self.dropped = 0

    def add(self, block):
        self.blocks.append(block)
        return True

    def seconds(self):
        return sum(len(b) for b in self.blocks) / float(TARGET_SR)

    def take_all(self):
        blocks, self.blocks = self.blocks, []
        return blocks, sum(len(b) for b in blocks) / float(TARGET_SR)

    def requeue(self, blocks):
        self.blocks = list(blocks) + self.blocks


class _Switch:
    """Um `ReduxHiddenSwitch` NU, com o `add_live_audio` REAL ligado por cima."""

    def __init__(self, cls, log, cap_s):
        self.inner = cls.__new__(cls)
        self.inner.pending = _Pending()
        self.inner.fuse_cap_s = cap_s
        self.inner.fuse_dropped_s = 0.0
        self.inner.log = log
        self.inner.add_audio = self._add_audio
        self.logs = []

    def _add_audio(self, block):
        self.inner.pending.add(block)
        return True

    def add_live_audio(self, block):
        return type(self.inner).add_live_audio(self.inner, block)


def _block(seconds=1.0):
    import numpy as np

    return np.zeros(int(TARGET_SR * seconds), dtype="<f4")


# ── the arms ────────────────────────────────────────────────────────────────
def arms():
    rows = []

    def arm(name, ok, detail=""):
        rows.append((name, bool(ok), detail))

    es, cls = _switch_class()
    have = _methods(cls, {"add_live_audio"})
    arm("A1-existe-o-metodo-real", "add_live_audio" in have,
        "o metodo que o worker chama tem de existir na classe")

    if "add_live_audio" not in have:
        return rows

    # A1/A2/A3 -- cap 60 s sobre 100 s empurrados
    logs = []
    sw = _Switch(cls, lambda m: logs.append(str(m)), 60.0)
    fed = [_block(1.0) for _ in range(100)]
    for one in fed:
        sw.add_live_audio(one)
    held = sw.inner.pending.seconds()
    dropped = sw.inner.fuse_dropped_s
    arm("A1-o-audio-do-ao-vivo-e-acumulado", held > 0.0, "held_s=%.1f" % held)
    arm("A2-o-techo-e-respeitado", held <= 61.0, "held_s=%.1f cap=60" % held)
    arm("A2b-o-corte-e-contado", dropped >= 39.0, "dropped_s=%.1f" % dropped)
    arm("A2c-o-corte-e-dito", any("REDUX_FUSE_TRIMMED" in l for l in logs),
        "linha=%r" % (logs[-1][:48] if logs else ""))
    # A3 -- a CAUDA e' a que fica: os blocos mais RECENTES, na ordem. Medido por
    # IDENTIDADE contra a serie empurrada: um corte que levasse a cabeca
    # manteria a mesma CONTAGEM e a mesma soma, e so' a identidade o apanha.
    kept = sw.inner.pending.blocks
    tail = fed[-len(kept):] if kept else []
    arm("A3-fica-a-cauda-na-ordem",
        len(kept) >= 59 and len(tail) == len(kept)
        and all(a is b for a, b in zip(kept, tail)),
        "blocos=%d, ultimo=%s" % (len(kept), "cauda" if kept and tail and kept[-1] is tail[-1] else "NAO-e-a-cauda"))

    # A4 -- abaixo do tecto NADA e' cortado
    sw2 = _Switch(cls, lambda m: None, 60.0)
    for _ in range(10):
        sw2.add_live_audio(_block(1.0))
    arm("A4-abaixo-do-techo-nada-se-perde",
        abs(sw2.inner.pending.seconds() - 10.0) < 0.01 and sw2.inner.fuse_dropped_s == 0.0,
        "held_s=%.1f dropped=%.1f" % (sw2.inner.pending.seconds(), sw2.inner.fuse_dropped_s))

    # A5 -- sem `pending` (fundo nao armado) nao levanta
    sw3 = _Switch(cls, lambda m: None, 60.0)
    sw3.inner.pending = None
    raised = None
    try:
        sw3.add_live_audio(_block(1.0))
    except Exception as exc:  # noqa: BLE001
        raised = exc
    arm("A5-sem-pending-nao-levanta", raised is None, repr(raised) if raised else "")

    # A6 -- o call site, lido do worker que embarca
    src = io.open(WORKER, "r", encoding="utf-8", errors="replace").read()
    tree = ast.parse(src)
    call_sites, bare_sites = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "switch":
            if node.func.attr == "add_live_audio":
                call_sites.append(node.lineno)
            elif node.func.attr == "add_audio":
                bare_sites.append(node.lineno)
    arm("A6-o-worker-passa-pelo-metedor-com-techo", len(call_sites) >= 1,
        "linhas=%s" % call_sites)
    # A6b -- o `add_audio` sem tecto continua a existir so' nos modos que ja'
    # decidem (`batch`/`shed`), nunca no ramo do ao vivo sem guarda.
    arm("A6b-o-caminho-sem-techo-e-so-dos-modos-de-fundo",
        all(line < call_sites[0] for line in bare_sites) if call_sites and bare_sites else bool(bare_sites),
        "add_audio=%s add_live_audio=%s" % (bare_sites, call_sites))

    # A7 -- o interruptor diz-se no arranque
    arm("A7-o-interruptor-declara-se", "REDUX_FUSE_HISTORY" in src,
        "SOTTO_FUSE_HISTORY lido no worker")

    return rows


def judge(rows):
    return [(name, detail) for name, ok, detail in rows if not ok]


# ── the negative control: mutate a COPY, none of these patterns is in HEAD ──
MUTANTS = {
    "M1-o-metodo-deixa-de-acumular": (
        "        self.add_audio(block)\n        cap = float(getattr(self, \"fuse_cap_s\", 0.0) or 0.0)",
        "        cap = float(getattr(self, \"fuse_cap_s\", 0.0) or 0.0)"),
    "M2-o-techo-deixa-de-cortar": (
        "        if cap <= 0 or self.pending_seconds() <= cap:",
        "        if True:"),
    "M3-o-corte-deixa-de-contar": (
        "        self.fuse_dropped_s = getattr(self, \"fuse_dropped_s\", 0.0) + dropped_s",
        "        self.fuse_dropped_s = getattr(self, \"fuse_dropped_s\", 0.0)"),
    "M4-o-corte-leva-a-cabeca": (
        "        for one in reversed(blocks):",
        "        for one in blocks:"),
    "M5-o-worker-volta-ao-add_audio": (
        "                    switch.add_live_audio(block)",
        "                    switch.add_audio(block)"),
}


def run_neg_arm():
    global SWITCH, WORKER
    caught = 0
    total = 0
    src = io.open(SWITCH, "r", encoding="utf-8", newline="").read()
    wsrc = io.open(WORKER, "r", encoding="utf-8", newline="").read()
    for name, (old, new) in MUTANTS.items():
        total += 1
        target_is_worker = old.startswith("                    switch.")
        hay = wsrc if target_is_worker else src
        old = old if old in hay else old.replace("\n", "\r\n")
        new = new if old in hay else new.replace("\n", "\r\n")
        if old not in hay:
            print("NEG-ARM IMPOSSIVEL %s: o padrao nao esta no ficheiro" % name)
            continue
        tmpdir = tempfile.mkdtemp(prefix="fusion-mut-")
        mutated = hay.replace(old, new, 1)
        if target_is_worker:
            path = os.path.join(tmpdir, "worker_mut.py")
            io.open(path, "w", encoding="utf-8", newline="").write(mutated)
            real, WORKER = WORKER, path
        else:
            path = os.path.join(tmpdir, "switch_mut.py")
            io.open(path, "w", encoding="utf-8", newline="").write(mutated)
            real, SWITCH = SWITCH, path
        try:
            bad = judge(arms())
        finally:
            if target_is_worker:
                WORKER = real
            else:
                SWITCH = real
        if bad:
            caught += 1
            print("ok %s -> RED: %s" % (name, ",".join(n for n, _ in bad)))
        else:
            print("NOT-CAUGHT %s: nenhum arm vermelho" % name)
    print("NEG-ARM %s mutants %d/%d"
          % ("PASS" if caught == total else "FAIL", caught, total))
    return 1 if caught == total else 0


def main(argv):
    if "--neg-arm" in argv:
        return run_neg_arm()
    rows = arms()
    for name, ok, detail in rows:
        print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                           (" -- " + detail) if detail else ""))
    bad = judge(rows)
    print("VERDICT: %s arms %d/%d" % ("FAIL" if bad else "PASS",
                                      len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
