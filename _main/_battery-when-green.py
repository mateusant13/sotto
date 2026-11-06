#!/usr/bin/env python3
"""Roda a bateria do Sotto QUANDO O GATE CENTRAL A DEIXAR -- e registra cada recusa.

PORQUE EXISTE (2026-11-05). O item `bateria verde` esta' aberto ha horas e o
bloqueio mudou de nome duas vezes na mesma sessao: primeiro a ordem de um pane da
herdr (que ja' nao esta' vivo), depois o proprio gate central, medido:
`acquire --kind heavy` recusado com `commit-pct=82.6 >= amber 80.0` porque OUTRA
lane carregou 11,6 GB de modelos de embedding nesta maquina. Nenhuma das duas e'
uma parede permanente, e nenhuma delas se resolve esperando de olhos fixos.

O QUE ESTE FICHEIRO FAZ, e o que ele NAO faz:
  * tenta o lease `heavy` a cada `--every` segundos, ate' `--minutes`;
  * **registra cada recusa COM os numeros que a produziram** -- um bloqueio sem
    numero e' uma impressao, e o dono ja' pagou por uma dessas;
  * quando o lease entra, larga `_main/_audit-verify-all.cmd` por
    `hidden-launch.popen` (nunca uma consola na tela dele) com a saida num
    ficheiro, e solta o lease no fim;
  * **NAO poe `SOTTO_BATTERY_HEAVY`**: os passos `heavy` (que largam a app do
    dono) tem de continuar a SALTAR enquanto a instancia dele estiver viva;
  * devolve 0 se a corrida terminou com `BATTERY-VERDICT`, 3 se o tempo acabou
    antes disso (e diz o ultimo estado do gate), 2 se a corrida nao produziu
    veredicto.

Uso:  python _main/_battery-when-green.py --minutes 45 [--every 60] [--dry-run]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATE = r"I:\!manager\tools\performance-gate.py"
BATTERY = os.path.join(HERE, "_audit-verify-all.cmd")
SUMMARY = os.path.join(HERE, "_audit-verify", "_battery-summary.txt")
LOG = os.path.join(HERE, "_audit-verify", "_battery-when-green.log")
OWNER = "sotto-battery-light-20261105"

# O UNICO CAMINHO QUE LARGA UM FILHO NESTA ARVORE (AGENTS.md, 2026-11-04).
_spec = importlib.util.spec_from_file_location(
    "sotto_hidden_launch", os.path.join(HERE, "hidden-launch.py"))
hidden = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hidden)


def _gate(*args, timeout=90):
    """`performance-gate.py` em modo JSON -- devolve (rc, payload|None, texto).

    O FILHO PASSA PELO LARGADOR DA CASA (`_main/hidden-launch.py`). Medido
    2026-11-05 pelo `console-window-audit`: este sitio levava `creationflags`
    so' (o flag "fraco" da auditoria) e um `subprocess` assim herda a consola do
    pai -- invisivel para quem corre de um terminal, visivel para o dono, que
    corre a app em `pythonw`. O helper poe `CREATE_NO_WINDOW` **e** o
    `STARTUPINFO` com `SW_HIDE`, e e' o unico caminho que larga um filho aqui.
    """
    rc, out, err = hidden.run([sys.executable, GATE] + list(args) + ["--json"],
                              capture=True, timeout=timeout)
    payload = None
    try:
        payload = json.loads((out or "").strip().splitlines()[-1])
    except Exception:                                            # noqa: BLE001
        payload = None
    return rc, payload, (out or "") + (err or "")


def _say(line):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    text = "%s %s" % (stamp, line)
    print(text, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=45.0)
    ap.add_argument("--every", type=float, default=60.0)
    ap.add_argument("--ttl", type=int, default=1800)
    ap.add_argument("--dry-run", action="store_true",
                    help="so' sonda o gate; nao larga a bateria")
    args = ap.parse_args(argv)

    deadline = time.monotonic() + args.minutes * 60.0
    attempt = 0
    last_state = "?"
    while True:
        attempt += 1
        try:
            rc, payload, text = _gate("acquire", "--kind", "heavy",
                                      "--owner", OWNER, "--ttl", str(args.ttl),
                                      "--note", "bateria leve do Sotto")
        except Exception as exc:                                 # noqa: BLE001
            _say("GATE-PROBE-FAILED attempt=%d %r" % (attempt, exc))
            rc, payload, text = 3, None, ""
        if payload is not None:
            last_state = payload.get("state") or last_state
            if payload.get("granted"):
                _say("GATE-GRANTED attempt=%d state=%s ms=%s"
                     % (attempt, payload.get("state"),
                        json.dumps((payload.get("sample") or {}).get("commit_pct"))))
                break
            sample = payload.get("sample") or {}
            _say("GATE-REFUSED attempt=%d state=%s reasons=%s commit_pct=%s "
                 "disk_ms=%s" % (attempt, payload.get("state"),
                                 json.dumps(payload.get("reasons") or []),
                                 sample.get("commit_pct"),
                                 sample.get("disk_latency_ms")))
        else:
            _say("GATE-UNPARSED attempt=%d rc=%s out=%r"
                 % (attempt, rc, (text or "")[-200:]))
        if time.monotonic() >= deadline:
            _say("TIMEOUT-SILENT last_state=%s attempts=%d -- a bateria NAO correu"
                 % (last_state, attempt))
            return 3
        time.sleep(args.every)

    if args.dry_run:
        _say("DRY-RUN: lease concedido; a bateria NAO foi largada (--dry-run)")
        _gate("release", "--owner", OWNER)
        return 0

    env = dict(os.environ)
    env.pop("SOTTO_BATTERY_HEAVY", None)   # os passos que largam a app do dono saltam
    env["SOTTO_STEP_DEADLINE_S"] = env.get("SOTTO_STEP_DEADLINE_S", "240")
    sys.path.insert(0, HERE)
    import importlib
    hidden = importlib.import_module("hidden-launch")

    before = os.path.getmtime(SUMMARY) if os.path.exists(SUMMARY) else None
    started = time.time()
    _say("BATTERY-START cmd=%s owner=%s" % (BATTERY, OWNER))
    log_path = os.path.join(HERE, "_audit-verify", "_battery-when-green.run.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as fh:
        proc = hidden.popen([BATTERY], cwd=ROOT, env=env, stdout=fh,
                            stderr=subprocess.STDOUT, text=True)
        rc = proc.wait()
    took = time.time() - started
    _say("BATTERY-END rc=%d took_s=%.1f" % (rc, took))

    after = os.path.getmtime(SUMMARY) if os.path.exists(SUMMARY) else None
    verdict = None
    if after is not None and (before is None or after >= before):
        try:
            with open(SUMMARY, encoding="utf-8", errors="replace") as fh:
                tail = fh.read()[-4000:]
            for line in tail.splitlines():
                if "BATTERY-VERDICT" in line:
                    verdict = line.strip()
        except OSError:
            verdict = None
    if verdict is None:
        _say("NO-VERDICT summary_mtime_changed=%s -- um sumario velho NAO e' o "
             "desta corrida" % (before != after))
    else:
        _say("VERDICT %s" % verdict)
    _gate("release", "--owner", OWNER)
    return 0 if verdict else 2


if __name__ == "__main__":
    raise SystemExit(main())
