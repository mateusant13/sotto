#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""O BANCO DE FIOS DO NEMOTRON AO VIVO -- que custo tem cortar as pecas pequenas.

POR QUE EXISTE (medido 2026-11-09, aprovado pelo watcher): o tripwire nomeou
TRES sessoes ORT a 398,8 %c no worker (`session-9-intra-op-0 121,8%`,
`session-10-intra-op-0 80,1%`, `session-8-intra-op-0 64,2%`). As tres sao o
MESMO modelo -- encoder + decoder + joint -- e as tres nasciam com o mesmo
`intra_op_num_threads`, ou seja 4x3 = 12 fios (~1200 %c de teto) para
descodificar UM fluxo. O `inter_op` ja' era 1.

O QUE ESTE BANCO MEDE, e no caminho de PRODUCAO: `worker/sotto_worker.py` com
`SOTTO_FILE_TAP` (o mesmo laco ao vivo, a mesma sessao, sem abrir dispositivo de
audio -- o audio do dono nao se toca). Cada braco muda UMA variavel, o piso dos
grafos pequenos, e le do proprio `WORKER_STATS`:

    * `infer_wall_s` / `chunks`  -> ms de computacao POR CHUNK, contra o
      orcamento do chunk de **560 ms** (`chunk_samples=8960` a 16 kHz);
    * pico de CPU do processo (`%c`) e RSS, medidos de fora por psutil;
    * `WORKER_THREAD_PLAN` (a linha nova) para provar que o braco mudou o que
      diz mudar -- um banco que compara dois bracos iguais mede contencao.

BRACOS: `--small 4` (o estado de ANTES: todas as sessoes com 4 fios) e
`--small 1` (a cura proposta). `--small 2` fica disponivel como meio-termo.

USO
    python _main/nemotron-thread-bench.py --small 4 --small 1 --seconds 45
    python _main/nemotron-thread-bench.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WAV = HERE / "live-sample-cable-input-90s.wav"
WORKER = REPO / "worker" / "sotto_worker.py"
CREATE_NO_WINDOW = 0x08000000


def one(small: int, seconds: float, threads: int = 4) -> dict:
    env = dict(os.environ)
    env["SOTTO_FILE_TAP"] = str(WAV)
    env["SOTTO_SMALL_GRAPH_THREADS"] = str(small)
    env["OMP_NUM_THREADS"] = str(threads)
    env["TMPDIR"] = r"I:\cc-tmp"
    env.pop("SOTTO_OWNER_AUDIO_OK", None)
    out = HERE / "_cache" / ("nemotron-thread-bench-small%d.jsonl" % small)
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with open(out, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(WORKER)],
            cwd=str(REPO / "worker"), env=env,
            stdout=fh, stderr=open(str(out) + ".err", "w", encoding="utf-8",
                                   errors="replace"),
            creationflags=CREATE_NO_WINDOW)
        import psutil

        child = psutil.Process(proc.pid)
        peak_cpu = peak_rss = 0.0
        plan = ""
        while proc.poll() is None and (time.perf_counter() - started) < seconds:
            try:
                peak_cpu = max(peak_cpu, child.cpu_percent(interval=0.25))
                peak_rss = max(peak_rss, child.memory_info().rss / 1e6)
            except psutil.Error:
                break
        # O FILHO TEM DE MORRER EM QUALQUER SAIDA. Sem isto um braco que
        # estoure a meio deixa um `sotto_worker.py` a segurar 1,9 GB ate' o
        # dono notar -- a mesma classe de fuga que o `shell-orphans` nomeia.
        try:
            proc.terminate()
            proc.wait(timeout=20)
        except Exception:                                   # noqa: BLE001
            try:
                proc.kill()
                proc.wait(timeout=10)
            except Exception:                               # noqa: BLE001
                pass
        finally:
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:                           # noqa: BLE001
                    pass
    try:
        if proc.stderr is not None:
            proc.stderr.close()
        err = (out.parent / (out.name + ".err")).read_text(encoding="utf-8",
                                                           errors="replace")
    except Exception:                                       # noqa: BLE001
        err = ""
    for line in err.splitlines():
        if "WORKER_THREAD_PLAN" in line:
            plan = line.strip()
            break
    stats = []
    chunks = font = 0
    for line in err.splitlines():
        if "WORKER_STATS" not in line or "infer_wall_s=" not in line:
            continue
        fields = {}
        for token in line.split():
            if "=" in token:
                k, v = token.split("=", 1)
                fields[k] = v
        stats.append(fields)
        for key in ("chunks", "infer_wall_s"):
            try:
                val = float(fields.get(key, 0) or 0)
            except ValueError:
                continue
            if key == "chunks":
                chunks = int(val) if val else chunks
            else:
                font = val or font
    per_chunk_ms = (font / chunks * 1000.0) if chunks else None
    return {
        "small": small, "threads": threads,
        "plan": plan, "chunks": chunks, "infer_wall_s": font,
        "ms_per_chunk": round(per_chunk_ms, 1) if per_chunk_ms else None,
        "budget_ms": 560.0,
        "headroom": (round(560.0 / per_chunk_ms, 2) if per_chunk_ms else None),
        "peak_cpu_pct": round(peak_cpu, 1), "peak_rss_mb": round(peak_rss, 1),
        "stats_lines": len(stats), "jsonl": str(out),
        "err_tail": err.strip()[-200:],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--small", type=int, action="append", default=None)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--caged", action="store_true",
                    help="ja' corre dentro do Job Object do watcher")
    args = ap.parse_args(argv)
    arms = args.small or [4, 1]
    if not WAV.exists():
        print("sem fixture: %s" % WAV)
        return 2
    # O TETO NA LARGADA, nao depois: este banco carrega 1,9 GB de modelo DUAS
    # vezes e foi ELE o maior produtor de pressao do stutter de 2026-11-09
    # (python.exe(56092), io 88,5 MB/s, sem Job Object nenhum ate' a raiz).
    # `SOTTO_BENCH_NOCAGE=1` devolve o modo sem tecto, e a linha `caged:` diz
    # sob que regime a corrida aconteceu -- sem isso um numero nao vale.
    if not args.caged and os.environ.get("SOTTO_BENCH_NOCAGE") != "1":
        cmd = [sys.executable, "-m", "watcher", "run", "--cpu", "40", "--",
               sys.executable, str(Path(__file__).resolve()), "--caged"]
        for a in argv or []:
            cmd.append(a)
        env = dict(os.environ)
        env["PYTHONPATH"] = r"I:\!watcher" + (os.pathsep + env["PYTHONPATH"]
                                               if env.get("PYTHONPATH") else "")
        env["TMPDIR"] = r"I:\cc-tmp"
        print("caged: ON (python -m watcher run --cpu 40)", flush=True)
        return subprocess.call(cmd, env=env, creationflags=CREATE_NO_WINDOW)
    print("caged: %s" % ("ON" if args.caged else "OFF"), flush=True)

    rows = []
    for small in arms:
        row = one(small, args.seconds, args.threads)
        rows.append(row)
        print("ARM small=%d chunks=%s ms_chunk=%s headroom=%s peak_cpu=%s rss=%s | %s"
              % (row["small"], row["chunks"], row["ms_per_chunk"], row["headroom"],
                 row["peak_cpu_pct"], row["peak_rss_mb"], row["plan"] or "(sem plano)"),
              flush=True)
    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
